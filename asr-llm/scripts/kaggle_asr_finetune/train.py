"""Fine-tune nvidia/parakeet-tdt-0.6b-v3 on the medpark-asr-data manifests (2x T4, fp16, DDP).

Full fine-tune, not adapters: adapter training on TDT is reported to go NaN, and the
multilingual tokenizer is kept as is (it already covers Latin and Cyrillic), so the
decoder and joint network keep their weights.

Environment knobs: MAX_STEPS, LR, BATCH, ACCUM, MAX_HOURS, DATA_DIR, OUT_DIR, RESUME.
Launched by kernel.py; Lightning's DDP re-runs this file on the second GPU.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DATA = Path(os.environ.get("DATA_DIR", "/kaggle/input/medpark-asr-data/asrdata"))
OUT = Path(os.environ.get("OUT_DIR", "/kaggle/working/ft"))
MAX_STEPS = int(os.environ.get("MAX_STEPS", "5000"))
LR = float(os.environ.get("LR", "3e-5"))
BATCH = int(os.environ.get("BATCH", "6"))
ACCUM = int(os.environ.get("ACCUM", "4"))
MAX_HOURS = float(os.environ.get("MAX_HOURS", "11"))


def absolute_manifest(name: str) -> str:
    """Manifests store paths relative to the dataset folder; NeMo wants absolute ones."""
    # One copy per DDP process, so no rank reads a file another rank is still writing.
    dest = OUT / f"{name}.rank{os.environ.get('LOCAL_RANK', '0')}.jsonl"
    OUT.mkdir(parents=True, exist_ok=True)
    with open(DATA / f"{name}.jsonl", encoding="utf-8") as src, open(dest, "w", encoding="utf-8") as out:
        for line in src:
            row = json.loads(line)
            row["audio_filepath"] = str(DATA / row["audio_filepath"])
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(dest)


def main() -> None:
    import lightning.pytorch as pl
    from lightning.pytorch.callbacks import LearningRateMonitor, ModelCheckpoint
    from nemo.collections.asr.models import ASRModel
    from omegaconf import open_dict

    train, dev = absolute_manifest("train"), absolute_manifest("dev")
    model = ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v3")

    trainer = pl.Trainer(
        devices=-1,
        accelerator="gpu",
        strategy="ddp",
        precision="16-mixed",  # T4 has no bf16; the TDT loss is computed in fp32 inside NeMo
        max_steps=MAX_STEPS,
        max_time={"hours": MAX_HOURS},  # always leave time to save inside the 12 h session
        accumulate_grad_batches=ACCUM,
        gradient_clip_val=1.0,
        val_check_interval=500 * ACCUM,
        check_val_every_n_epoch=None,
        log_every_n_steps=25,
        logger=pl.loggers.CSVLogger(str(OUT), name="logs"),
        callbacks=[
            ModelCheckpoint(dirpath=str(OUT / "ckpt"), every_n_train_steps=500, save_last=True, save_top_k=2, monitor="val_wer", mode="min"),
            LearningRateMonitor(logging_interval="step"),
        ],
        enable_progress_bar=False,
    )
    model.set_trainer(trainer)

    common = {"sample_rate": 16000, "num_workers": 4, "pin_memory": True, "use_start_end_token": False}
    with open_dict(model.cfg):
        model.cfg.train_ds = {**common, "manifest_filepath": train, "batch_size": BATCH, "shuffle": True, "max_duration": 20.0, "min_duration": 0.5}
        model.cfg.validation_ds = {**common, "manifest_filepath": dev, "batch_size": BATCH, "shuffle": False}
        model.cfg.optim = {
            "name": "adamw",
            "lr": LR,
            "betas": [0.9, 0.98],
            "weight_decay": 1e-3,
            "sched": {"name": "CosineAnnealing", "warmup_steps": 500, "min_lr": 1e-6},
        }
    model.setup_training_data(model.cfg.train_ds)
    model.setup_validation_data(model.cfg.validation_ds)
    model.setup_optimization(model.cfg.optim)

    resume = os.environ.get("RESUME") or None
    trainer.fit(model, ckpt_path=resume)
    if trainer.is_global_zero:
        model.save_to(str(OUT / "parakeet-tdt-0.6b-v3-medpark.nemo"))
        print("saved", OUT / "parakeet-tdt-0.6b-v3-medpark.nemo", flush=True)


if __name__ == "__main__":
    main()
