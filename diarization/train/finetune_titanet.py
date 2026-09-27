"""Fine-tune TitaNet-small on meeting speakers, then export it for sherpa-onnx.

Runs on a GPU machine (Kaggle/Colab T4, or a teammate's CUDA box), not on
the Intel Mac, because NeMo needs a current PyTorch. It trains on public
data only (AMI and other open corpora); hospital audio never leaves the
hospital. Not yet run end to end: check the first epoch's loss before
leaving it alone.

  pip install "nemo_toolkit[asr]" onnx
  python finetune_titanet.py --train ami_train.jsonl --val ami_val.jsonl --epochs 10

Follows NeMo's own speaker fine-tuning recipe: take the pretrained
titanet_small config, size the classifier to our training speakers, build
the model, then load every pretrained weight except the old classifier
(`decoder.final`). The export carries the same metadata keys as the stock
sherpa-onnx model, so the file drops into diarization/models/.
"""

import argparse
import json
import math
import time
from pathlib import Path

import lightning.pytorch as pl
import nemo
import nemo.collections.asr as nemo_asr
import onnx
import torch
from omegaconf import OmegaConf, open_dict


def add_meta(filename, meta):
    model = onnx.load(filename)
    for k, v in meta.items():
        p = model.metadata_props.add()
        p.key, p.value = k, str(v)
    onnx.save(model, filename)


class Progress(pl.Callback):
    """Plain log lines instead of a progress bar, readable in Kaggle's log:
    every 50 steps (loss, speed, ETA, GPU memory), after each validation, and
    a saved .nemo after each epoch so a late crash still leaves a model. Also
    writes the latest numbers to a JSON file the Kaggle heartbeat reads, and
    warns when the loss stops being a number or rises between epochs."""

    def __init__(self, save, progress=None, every=50):
        self.save, self.progress, self.every, self.t0 = save, progress, every, time.time()
        self.losses, self.prev_epoch_loss, self.bad, self.warn = [], None, 0, ""

    @staticmethod
    def metrics(trainer):
        return ", ".join(f"{k} {float(v):.4g}" for k, v in trainer.callback_metrics.items() if v.numel() == 1)

    def write(self, trainer, loss, eta):
        if self.progress:
            Path(self.progress).write_text(json.dumps({
                "epoch": trainer.current_epoch + 1, "epochs": trainer.max_epochs, "step": trainer.global_step,
                "total": trainer.estimated_stepping_batches, "loss": loss, "eta_min": round(eta, 1),
                "elapsed_min": round((time.time() - self.t0) / 60, 1), "updated": time.time(), "warn": self.warn}))

    def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx):
        loss = outputs["loss"] if isinstance(outputs, dict) else outputs
        loss = float(loss) if loss is not None else float("nan")
        if math.isfinite(loss):
            self.losses.append(loss)
            self.bad = 0
        else:
            self.bad += 1
            if self.bad in (1, 20):
                self.warn = f"loss is {loss} at step {trainer.global_step} ({self.bad} bad steps in a row)"
                print(f"[WARN] {self.warn}", flush=True)
        step = trainer.global_step
        if step % self.every:
            return
        took, total = time.time() - self.t0, trainer.estimated_stepping_batches
        eta = took / max(step, 1) * (total - step) / 60
        recent = sum(self.losses[-self.every:]) / max(len(self.losses[-self.every:]), 1)
        print(f"[train] epoch {trainer.current_epoch + 1}/{trainer.max_epochs} step {step}/{total} "
              f"({100 * step / max(total, 1):.0f}%) | loss {recent:.3f} | {self.metrics(trainer)} | "
              f"{step / took:.2f} steps/s, ETA {eta:.0f} min | GPU peak {torch.cuda.max_memory_allocated() / 1e9:.1f} GB",
              flush=True)
        self.write(trainer, recent, eta)

    def on_validation_end(self, trainer, pl_module):
        print(f"[val] epoch {trainer.current_epoch + 1}: {self.metrics(trainer)}", flush=True)

    def on_train_epoch_end(self, trainer, pl_module):
        mean = sum(self.losses) / max(len(self.losses), 1)
        trend = ""
        if self.prev_epoch_loss is not None:
            change = (mean - self.prev_epoch_loss) / self.prev_epoch_loss
            trend = f", {'down' if change < 0 else 'UP'} {abs(change):.0%} from the last epoch"
            if change > 0.02:
                self.warn = f"epoch {trainer.current_epoch + 1} loss rose {change:.0%}"
                print(f"[WARN] {self.warn}", flush=True)
        print(f"[epoch] {trainer.current_epoch + 1}/{trainer.max_epochs} mean loss {mean:.3f}{trend}", flush=True)
        self.prev_epoch_loss, self.losses = mean, []
        pl_module.save_to(str(self.save))
        print(f"[save] epoch {trainer.current_epoch + 1} -> {self.save} "
              f"({(time.time() - self.t0) / 60:.1f} min in)", flush=True)


class KeepFrozen(pl.Callback):
    """Frozen blocks stay in eval mode, so their batch-norm statistics do not
    drift toward the new data while the top of the network adapts."""

    def __init__(self, modules):
        self.modules = modules

    def on_train_epoch_start(self, trainer, pl_module):
        for m in self.modules:
            m.eval()


class EpochExport(pl.Callback):
    """An ONNX file after every epoch, so the best epoch can be picked on
    held-out meetings instead of trusting the last one."""

    def __init__(self, out, meta, frozen):
        self.out, self.meta, self.frozen = Path(out), meta, frozen

    def on_train_epoch_end(self, trainer, pl_module):
        path = self.out.with_suffix(f".e{trainer.current_epoch + 1}.onnx")
        grads = {n: p.requires_grad for n, p in pl_module.named_parameters()}
        pl_module.eval()
        pl_module.export(str(path))  # NeMo's export turns every requires_grad off
        add_meta(str(path), self.meta)
        for n, p in pl_module.named_parameters():
            p.requires_grad = grads[n]
        pl_module.train()
        for m in self.frozen:
            m.eval()
        print(f"[save] epoch {trainer.current_epoch + 1} -> {path}", flush=True)


def meta(cfg, labels):
    """The metadata keys sherpa-onnx reads from a NeMo speaker model."""
    pre = cfg.preprocessor
    return {
        "framework": "nemo",
        "language": "multilingual meetings (fine-tuned)",
        "url": "https://catalog.ngc.nvidia.com/orgs/nvidia/teams/nemo/models/titanet_small",
        "comment": f"TitaNet-small fine-tuned on {len(labels)} meeting speakers",
        "sample_rate": pre.sample_rate,
        "output_dim": cfg.decoder.emb_sizes,
        "feature_normalize_type": pre.normalize,
        "window_size_ms": int(float(pre.window_size) * 1000),
        "window_stride_ms": int(float(pre.window_stride) * 1000),
        "window_type": pre.window,
        "feat_dim": pre.features,
    }


def freeze_below(model, keep):
    """Freeze the encoder except its last `keep` blocks; the decoder always trains."""
    blocks = list(model.encoder.encoder)
    frozen = blocks[:len(blocks) - keep] if keep > 0 else blocks
    for b in frozen:
        for p in b.parameters():
            p.requires_grad = False
    n = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[freeze] {len(frozen)} of {len(blocks)} encoder blocks frozen; {n / 1e6:.2f} M parameters train", flush=True)
    return frozen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True)
    ap.add_argument("--val", required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--out", default="nemo_en_titanet_small_ft.onnx")
    ap.add_argument("--smoke", action="store_true", help="one batch, to test the config and export in a minute")
    ap.add_argument("--progress", help="JSON file to keep updated with step, loss and ETA")
    ap.add_argument("--rir-manifest", help="room impulse responses to convolve training pieces with")
    ap.add_argument("--noise-manifest", help="noises to mix into training pieces")
    ap.add_argument("--aug-prob", type=float, default=0.3, help="chance of each augmentation per piece")
    ap.add_argument("--freeze-keep", type=int, default=-1,
                    help="train only the last N encoder blocks plus the decoder (-1 trains everything)")
    ap.add_argument("--grad-clip", type=float, default=None)
    ap.add_argument("--export-every-epoch", action="store_true")
    a = ap.parse_args()
    gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none"
    print(f"torch {torch.__version__}, CUDA {torch.version.cuda}, GPU {gpu}, NeMo {nemo.__version__}, "
          f"Lightning {pl.__version__}", flush=True)

    labels = sorted({json.loads(line)["label"] for line in open(a.train)})
    cfg = nemo_asr.models.EncDecSpeakerLabelModel.from_pretrained("titanet_small", return_config=True)
    with open_dict(cfg):
        for split, path, shuffle in (("train_ds", a.train, True), ("validation_ds", a.val, False)):
            cfg[split].manifest_filepath = path
            cfg[split].labels = labels
            cfg[split].batch_size = a.batch
            cfg[split].shuffle = shuffle
            cfg[split].pop("augmentor", None)  # points at noise files on NVIDIA's own cluster
        aug = {}
        if a.noise_manifest:
            aug["noise"] = {"manifest_path": a.noise_manifest, "prob": a.aug_prob, "min_snr_db": 5, "max_snr_db": 20}
        if a.rir_manifest:
            aug["impulse"] = {"manifest_path": a.rir_manifest, "prob": a.aug_prob}
        if aug:
            cfg.train_ds.augmentor = aug
        cfg.decoder.num_classes = len(labels)
        cfg.optim.lr = a.lr

    # smoke: two tiny epochs, so anything that breaks at an epoch boundary shows up in minutes
    short = dict(max_epochs=2, limit_train_batches=2, limit_val_batches=1, num_sanity_val_steps=0) if a.smoke else {}
    trainer = pl.Trainer(**{"max_epochs": a.epochs, **short}, accelerator="gpu", devices=1, precision="16-mixed",
                         gradient_clip_val=a.grad_clip, log_every_n_steps=1, enable_progress_bar=False,
                         callbacks=[])
    model = nemo_asr.models.EncDecSpeakerLabelModel(cfg=cfg, trainer=trainer)
    model.maybe_init_from_pretrained_checkpoint(OmegaConf.create({
        "init_from_pretrained_model": {"titanet": {"name": "titanet_small", "exclude": ["decoder.final"]}}}))
    frozen = freeze_below(model, a.freeze_keep) if a.freeze_keep >= 0 else []
    callbacks = [Progress(Path(a.out).with_suffix(".last.nemo"), a.progress)]
    if frozen:
        callbacks.append(KeepFrozen(frozen))
    if a.export_every_epoch:
        callbacks.append(EpochExport(a.out, meta(cfg, labels), frozen))
    trainer.callbacks.extend(callbacks)
    trainer.fit(model)

    model.eval()
    model.export(a.out)
    add_meta(a.out, meta(cfg, labels))
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
