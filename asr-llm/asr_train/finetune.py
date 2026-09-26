"""Fine-tune nvidia/parakeet-tdt-0.6b-v3 on the build_data manifests.

Full fine-tune, not adapters: adapter training on TDT is reported to go NaN, and the
multilingual tokenizer is kept as is (it already covers Latin and Cyrillic), so the
decoder and joint network keep their weights.

Hardware is read at start: every visible GPU with DDP when there are several, bf16
where the GPU has it (T4 does not: fp16 there; the TDT loss is computed in fp32 inside
NeMo), fp32 on CPU (a smoke test only; 0.6B does not train on CPU).

    python -m asr_train.finetune --data-dir data/asrdata --check          # manifests + audio, no NeMo
    python -m asr_train.finetune --data-dir data/asrdata --out runs/ft
    python -m asr_train.finetune --data-dir data/asrdata --out runs/ft --resume auto \\
        --base-model models/parakeet-tdt-0.6b-v3.nemo                     # offline: local base weights

Every flag falls back to an env var of the same name upper-cased (DATA_DIR, OUT_DIR,
MAX_STEPS, LR, BATCH, ACCUM, MAX_HOURS, RESUME, ...), so older launch lines still work.
Lightning's DDP re-runs this module on every extra GPU with the same arguments.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .common import read_jsonl, write_jsonl

BASE_MODEL = "nvidia/parakeet-tdt-0.6b-v3"
NEMO_NAME = "parakeet-tdt-0.6b-v3-medpark.nemo"


def _env(name: str, default=None):
    return os.environ.get(name, default)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", type=Path, default=_env("DATA_DIR"), help="Folder with train.jsonl, dev.jsonl, audio/.")
    p.add_argument("--out", type=Path, default=Path(_env("OUT_DIR", "runs/ft")))
    p.add_argument("--base-model", default=_env("BASE_MODEL", BASE_MODEL), help="Hub id, or a local .nemo file (offline).")
    p.add_argument("--resume", default=_env("RESUME"), help="A .ckpt to continue from, or 'auto' = newest in <out>/ckpt.")
    p.add_argument("--max-steps", type=int, default=int(_env("MAX_STEPS", "5000")))
    p.add_argument("--max-hours", type=float, default=float(_env("MAX_HOURS", "11")), help="Wall-clock budget of this session.")
    p.add_argument("--lr", type=float, default=float(_env("LR", "3e-5")))
    p.add_argument("--warmup", type=int, default=int(_env("WARMUP", "500")))
    p.add_argument("--batch", type=int, default=int(_env("BATCH", "6")))
    p.add_argument("--accum", type=int, default=int(_env("ACCUM", "4")))
    p.add_argument("--val-every", type=int, default=int(_env("VAL_EVERY", "500")), help="Optimizer steps between dev checks and checkpoints.")
    p.add_argument("--devices", type=int, default=int(_env("DEVICES", "0")), help="GPUs to use; 0 = all visible.")
    p.add_argument("--precision", default=_env("PRECISION", "auto"), help="auto | bf16-mixed | 16-mixed | 32.")
    p.add_argument("--workers", type=int, default=int(_env("WORKERS", "4")))
    p.add_argument("--check", action="store_true", help="Only check manifests and audio files, then exit.")
    args = p.parse_args(argv)
    if args.data_dir is None:
        p.error("--data-dir (or DATA_DIR) is required")
    return args


# ---------------------------------------------------------------- pure helpers

def pick_precision(requested: str, accelerator: str, bf16_ok: bool) -> str:
    if requested != "auto":
        return requested
    if accelerator == "cpu":
        return "32"
    return "bf16-mixed" if bf16_ok else "16-mixed"


def trainer_kwargs(args: argparse.Namespace, n_gpus: int, bf16_ok: bool) -> dict:
    """Everything the Trainer gets except loggers and callbacks."""
    if args.devices > n_gpus:
        raise ValueError(f"--devices {args.devices} but only {n_gpus} GPU(s) visible")
    accelerator = "gpu" if n_gpus else "cpu"
    devices = args.devices or n_gpus or 1
    return {
        "accelerator": accelerator,
        "devices": devices,
        "strategy": "ddp" if accelerator == "gpu" and devices > 1 else "auto",
        "precision": pick_precision(args.precision, accelerator, bf16_ok),
        "max_steps": args.max_steps,
        "accumulate_grad_batches": args.accum,
        "gradient_clip_val": 1.0,
        # Counted in batches, across epochs (check_val_every_n_epoch=None): one dev check per val_every optimizer steps.
        "val_check_interval": args.val_every * args.accum,
        "check_val_every_n_epoch": None,
        "log_every_n_steps": 25,
        "enable_progress_bar": False,
    }


def dataset_configs(train: str, dev: str, batch: int, workers: int, pin_memory: bool) -> tuple[dict, dict]:
    common = {"sample_rate": 16000, "num_workers": workers, "pin_memory": pin_memory, "use_start_end_token": False}
    train_ds = {**common, "manifest_filepath": train, "batch_size": batch, "shuffle": True, "max_duration": 20.0, "min_duration": 0.5}
    val_ds = {**common, "manifest_filepath": dev, "batch_size": batch, "shuffle": False}
    return train_ds, val_ds


def optim_config(lr: float, warmup: int, max_steps: int) -> dict:
    return {
        "name": "adamw",
        "lr": lr,
        "betas": [0.9, 0.98],
        "weight_decay": 1e-3,
        # A short smoke run must not spend all its steps warming up.
        "sched": {"name": "CosineAnnealing", "warmup_steps": min(warmup, max(1, max_steps // 10)), "min_lr": 1e-6},
    }


def absolute_manifest(data: Path, out: Path, name: str, rank: str = "0") -> Path:
    """Manifests store paths relative to the dataset folder; NeMo wants absolute ones."""
    # One copy per DDP process, so no rank reads a file another rank is still writing.
    rows = read_jsonl(data / f"{name}.jsonl")
    for row in rows:
        row["audio_filepath"] = str((data / row["audio_filepath"]).resolve())
    dest = out / f"{name}.rank{rank}.jsonl"
    write_jsonl(dest, rows)
    return dest


def _sum_by(rows: list[dict], key: str) -> dict:
    out: dict = {}
    for r in rows:
        out[r.get(key, "?")] = out.get(r.get(key, "?"), 0.0) + r["duration"]
    return out


def check_manifests(data: Path) -> dict:
    report = {}
    for name in ("train", "dev"):
        path = data / f"{name}.jsonl"
        if not path.exists():
            report[name] = {"error": f"{path} missing"}
            continue
        rows = read_jsonl(path)
        files = {r["audio_filepath"] for r in rows}
        missing = sorted(f for f in files if not (data / f).exists())
        report[name] = {
            "rows": len(rows),
            "files": len(files),
            "hours": round(sum(r["duration"] for r in rows) / 3600, 2),
            "hours_by_source": {k: round(v / 3600, 2) for k, v in sorted(_sum_by(rows, "source").items())},
            "missing_audio": len(missing),
            "first_missing": missing[:3],
        }
    return report


def resolve_resume(resume: str | None, ckpt_dir: Path) -> str | None:
    """'auto' = the newer of final.ckpt / last.ckpt in ckpt_dir, or a fresh start if neither exists."""
    if not resume:
        return None
    if resume != "auto":
        if not Path(resume).exists():
            raise FileNotFoundError(f"--resume {resume} does not exist")
        return resume
    found = [p for p in (ckpt_dir / "final.ckpt", ckpt_dir / "last.ckpt") if p.exists()]
    return str(max(found, key=lambda p: p.stat().st_mtime)) if found else None


# ---------------------------------------------------------------- training

def session_budget(hours: float):
    """Stop after `hours` of wall time in *this* session.

    Not Trainer(max_time=...): Lightning's Timer saves its elapsed time in the checkpoint,
    so a resumed run whose first session used the whole budget would stop at once.
    """
    import lightning.pytorch as pl

    class SessionBudget(pl.Callback):
        def __init__(self) -> None:
            self.deadline = time.monotonic() + hours * 3600

        def on_train_batch_end(self, trainer, *args) -> None:
            late = time.monotonic() > self.deadline
            if trainer.strategy.reduce_boolean_decision(late, all=False):  # any rank late -> all stop together
                trainer.should_stop = True

    return SessionBudget()


def load_base(name: str):
    from nemo.collections.asr.models import ASRModel

    if name.endswith(".nemo") or Path(name).exists():
        return ASRModel.restore_from(str(Path(name).expanduser()))
    return ASRModel.from_pretrained(name)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    data = args.data_dir.expanduser().resolve()
    report = check_manifests(data)
    print(json.dumps(report, indent=1), flush=True)
    if args.check:
        return
    # A broken data build should cost seconds of GPU quota, not a failed 11 h session.
    bad = {k: v for k, v in report.items() if "error" in v or v["missing_audio"] or not v["rows"]}
    if bad:
        raise SystemExit(f"manifests not usable: {bad}")

    import lightning.pytorch as pl
    import torch
    from lightning.pytorch.callbacks import LearningRateMonitor, ModelCheckpoint
    from omegaconf import open_dict

    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    out = args.out.expanduser().resolve()
    ckpt_dir = out / "ckpt"
    resume = resolve_resume(args.resume, ckpt_dir)
    rank = os.environ.get("LOCAL_RANK", "0")
    train = absolute_manifest(data, out, "train", rank)
    dev = absolute_manifest(data, out, "dev", rank)

    n_gpus = torch.cuda.device_count()
    kwargs = trainer_kwargs(args, n_gpus, bf16_ok=n_gpus > 0 and torch.cuda.is_bf16_supported())
    print({"data": str(data), "out": str(out), "resume": resume, **kwargs}, flush=True)

    model = load_base(args.base_model)
    trainer = pl.Trainer(
        **kwargs,
        logger=pl.loggers.CSVLogger(str(out), name="logs"),
        callbacks=[
            # Saved right after each dev check (not on a step count, which fires before that
            # step's validation and would rank checkpoints by a stale val_wer).
            ModelCheckpoint(
                dirpath=str(ckpt_dir),
                filename="step{step}-wer{val_wer:.4f}",
                auto_insert_metric_name=False,
                save_last=True,
                save_top_k=2,
                monitor="val_wer",
                mode="min",
                save_on_train_epoch_end=False,
            ),
            LearningRateMonitor(logging_interval="step"),
            session_budget(args.max_hours),
        ],
    )
    model.set_trainer(trainer)

    train_ds, val_ds = dataset_configs(str(train), str(dev), args.batch, args.workers, pin_memory=n_gpus > 0)
    with open_dict(model.cfg):
        model.cfg.train_ds = train_ds
        model.cfg.validation_ds = val_ds
        model.cfg.optim = optim_config(args.lr, args.warmup, args.max_steps)
    model.setup_training_data(model.cfg.train_ds)
    model.setup_validation_data(model.cfg.validation_ds)
    model.setup_optimization(model.cfg.optim)

    trainer.fit(model, ckpt_path=resume)
    # Up to val_every steps may have passed since last.ckpt; keep them for the next session. All ranks call this.
    trainer.save_checkpoint(str(ckpt_dir / "final.ckpt"))
    if trainer.is_global_zero:
        model.save_to(str(out / NEMO_NAME))
        print("saved", out / NEMO_NAME, flush=True)


if __name__ == "__main__":
    main()
