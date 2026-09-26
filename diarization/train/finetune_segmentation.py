"""Fine-tune pyannote segmentation-3.0, the model that marks who is talking
in each 17 ms frame, then export the ONNX file diarizer.neural.Segmenter
loads (input "x", output "y").

This is the model behind most missed speech on far-field meetings; the
Hugging Face diarizers work cut DER by a quarter on new languages by
fine-tuning only this part. Runs on Kaggle with pyannote.audio 4.0 (torch 2.10)
(train/kaggle, DATA_PROFILE=segmentation).

  python train/finetune_segmentation.py --database db.yml --protocol MOM.SpeakerDiarization.far \\
      --checkpoint ckpt/pytorch_model.bin --reference models/segmentation-3.0.onnx --out out/
"""

import argparse
import json
import time
from pathlib import Path

import lightning.pytorch as pl
import numpy as np
import onnxruntime as ort
import torch
from lightning.pytorch.callbacks import ModelCheckpoint
from pyannote.audio import Model
from pyannote.audio.tasks import SpeakerDiarization
from pyannote.database import FileFinder, registry


def export(model, path):
    model = model.eval().cpu()
    torch.onnx.export(model, torch.zeros(1, 1, 160000), str(path), input_names=["x"], output_names=["y"],
                      dynamic_axes={"x": {0: "N", 2: "T"}, "y": {0: "N", 1: "F"}}, opset_version=13,
                      dynamo=False)  # the classic exporter, as used for the shipped model
    return path


def onnx_out(path, audio):
    return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]).run(None, {"x": audio})[0]


def same_as_reference(model, reference, tmp):
    """The mirror checkpoint must behave exactly like the ONNX we ship,
    or it is not the model we think it is."""
    audio = (np.random.default_rng(0).standard_normal((1, 1, 80000)) * 0.1).astype(np.float32)
    a, b = onnx_out(export(model, tmp), audio), onnx_out(reference, audio)
    diff = float(np.abs(a - b).max())
    print(f"[check] checkpoint vs shipped ONNX: max difference {diff:.2e}, "
          f"frame labels agree {np.mean(a.argmax(-1) == b.argmax(-1)):.4f}", flush=True)
    return diff < 1e-3


class Progress(pl.Callback):
    """Plain log lines and the progress file the Kaggle heartbeat reads."""

    def __init__(self, progress, every=50):
        self.progress, self.every, self.t0 = progress, every, time.time()

    def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx):
        step, total = trainer.global_step, trainer.estimated_stepping_batches
        if step % self.every:
            return
        loss = outputs["loss"] if isinstance(outputs, dict) else outputs
        loss = float(loss) if loss is not None else float("nan")
        took = time.time() - self.t0
        eta = took / max(step, 1) * (total - step) / 60
        print(f"[train] epoch {trainer.current_epoch + 1}/{trainer.max_epochs} step {step}/{total} "
              f"({100 * step / max(total, 1):.0f}%) | loss {loss:.4f} | {step / took:.2f} steps/s, ETA {eta:.0f} min",
              flush=True)
        if self.progress:
            Path(self.progress).write_text(json.dumps({
                "epoch": trainer.current_epoch + 1, "epochs": trainer.max_epochs, "step": step, "total": total,
                "loss": loss, "eta_min": round(eta, 1), "elapsed_min": round(took / 60, 1),
                "updated": time.time(), "warn": "" if np.isfinite(loss) else f"loss is {loss} at step {step}"}))

    def on_validation_end(self, trainer, pl_module):
        m = {k: round(float(v), 4) for k, v in trainer.callback_metrics.items() if v.numel() == 1}
        print(f"[val] epoch {trainer.current_epoch + 1}: {m}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--database", required=True)
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--checkpoint", required=True, help="pytorch_model.bin of segmentation-3.0")
    ap.add_argument("--reference", required=True, help="the segmentation ONNX shipped in models/")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--progress")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"torch {torch.__version__}, GPU {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none'}",
          flush=True)
    model = Model.from_pretrained(a.checkpoint)
    if not same_as_reference(model, a.reference, out / "stock.onnx"):
        raise SystemExit("the downloaded checkpoint does not match the shipped segmentation model")
    model.train()  # the check exported in eval mode, and Lightning 2 keeps whatever mode it finds

    registry.load_database(a.database)
    protocol = registry.get_protocol(a.protocol, preprocessors={"audio": FileFinder()})
    spec = model.specifications
    task = SpeakerDiarization(protocol, duration=spec.duration, max_speakers_per_chunk=len(spec.classes),
                              max_speakers_per_frame=spec.powerset_max_classes, batch_size=a.batch, num_workers=4)
    model.task = task
    model.configure_optimizers = lambda: torch.optim.Adam(model.parameters(), lr=a.lr)
    model.prepare_data()
    model.setup()
    monitor, mode = task.val_monitor
    best = ModelCheckpoint(dirpath=out / "ckpt", filename="best", monitor=monitor, mode=mode, save_top_k=1)
    trainer = pl.Trainer(accelerator="gpu", devices=1, max_epochs=a.epochs, fast_dev_run=a.smoke,
                         gradient_clip_val=0.5, enable_progress_bar=False, log_every_n_steps=20,
                         callbacks=[best, Progress(a.progress)])
    trainer.fit(model)

    export(model, out / "segmentation-ft.last.onnx")
    if best.best_model_path:
        print(f"[best] {monitor} = {float(best.best_model_score):.4f} at {best.best_model_path}", flush=True)
        export(Model.from_pretrained(best.best_model_path), out / "segmentation-ft.onnx")
    else:
        export(model, out / "segmentation-ft.onnx")
    y = onnx_out(out / "segmentation-ft.onnx", np.zeros((1, 1, 80000), np.float32))
    print(f"wrote {out / 'segmentation-ft.onnx'}: output {tuple(y.shape)}", flush=True)


if __name__ == "__main__":
    main()
