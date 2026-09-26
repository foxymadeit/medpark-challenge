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
import unicodedata
from datetime import timedelta
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
    # 2 x 12 = the same 24 utterances per update as 6 x 4, which ran a T4 out of memory in the first steps.
    p.add_argument("--batch", type=int, default=int(_env("BATCH", "2")))
    p.add_argument("--accum", type=int, default=int(_env("ACCUM", "12")))
    p.add_argument("--val-every", type=int, default=int(_env("VAL_EVERY", "500")), help="Optimizer steps between dev checks and checkpoints.")
    p.add_argument("--devices", type=int, default=int(_env("DEVICES", "0")), help="GPUs to use; 0 = all visible.")
    p.add_argument("--precision", default=_env("PRECISION", "auto"), help="auto | bf16-mixed | 16-mixed | 32.")
    p.add_argument("--workers", type=int, default=int(_env("WORKERS", "4")))
    # The TDT loss holds batch x frames x tokens x 8193 vocab floats (three copies): ~5 GB for one pair of
    # 20 s clips, on top of ~10 GB of weights, grads and AdamW state. 12 s cuts that ~6x; both T4s hit OOM at 20.
    p.add_argument("--max-duration", type=float, default=float(_env("MAX_DURATION", "12")))
    # Full fine-tune of 627M params needs ~12.5 GB for weights, grads and AdamW state alone: a T4 ran out
    # at the first optimizer step. Frozen layers get no grads and no optimizer state.
    p.add_argument("--freeze-layers", type=int, default=int(_env("FREEZE_LAYERS", "12")),
                   help="Keep the subsampling and this many lower encoder layers (of 24) as they are.")
    p.add_argument("--exclude-sources", default=_env("EXCLUDE_SOURCES", "rompar"),
                   help="Comma-separated manifest sources left out of training. rompar: its transcripts do not "
                        "match its audio (every model, 0.72+ CER on it vs 0.02-0.04 on FLEURS).")
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


def dataset_configs(train: str, dev: str, batch: int, workers: int, pin_memory: bool, max_duration: float = 12.0) -> tuple[dict, dict]:
    common = {"sample_rate": 16000, "num_workers": workers, "pin_memory": pin_memory, "use_start_end_token": False}
    train_ds = {**common, "manifest_filepath": train, "batch_size": batch, "shuffle": True, "max_duration": max_duration, "min_duration": 0.5}
    val_ds = {**common, "manifest_filepath": dev, "batch_size": batch, "shuffle": False, "max_duration": max_duration}
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


# Cedilla s/t are the legacy spelling; the tokenizer only has the comma-below letters, so ţ became ⁇.
_RO_LETTERS = str.maketrans("şţŞŢ", "șțȘȚ")


def clean_label(text: str) -> str:
    return unicodedata.normalize("NFC", text).translate(_RO_LETTERS)


def absolute_manifest(data: Path, out: Path, name: str, rank: str = "0", exclude: frozenset = frozenset()) -> Path:
    """Manifests store paths relative to the dataset folder; NeMo wants absolute ones."""
    # One copy per DDP process, so no rank reads a file another rank is still writing.
    rows = [r for r in read_jsonl(data / f"{name}.jsonl") if r.get("source") not in exclude]
    for row in rows:
        row["audio_filepath"] = str((data / row["audio_filepath"]).resolve())
        row["text"] = clean_label(row["text"])
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
    rank = os.environ.get("LOCAL_RANK", "0")
    if rank != "0":  # Lightning re-runs this module per extra GPU; rank 0 already checked the data
        return train_model(args, data, rank)
    report = check_manifests(data)
    print(json.dumps(report, indent=1), flush=True)
    if args.check:
        return
    # A broken data build should cost seconds of GPU quota, not a failed 11 h session.
    bad = {k: v for k, v in report.items() if "error" in v or v["missing_audio"] or not v["rows"]}
    if bad:
        raise SystemExit(f"manifests not usable: {bad}")
    train_model(args, data, rank)


def train_model(args: argparse.Namespace, data: Path, rank: str) -> None:
    import lightning.pytorch as pl
    import torch
    from lightning.pytorch.callbacks import LearningRateMonitor, ModelCheckpoint
    from lightning.pytorch.strategies import DDPStrategy
    from omegaconf import open_dict

    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    out = args.out.expanduser().resolve()
    ckpt_dir = out / "ckpt"
    resume = resolve_resume(args.resume, ckpt_dir)
    exclude = frozenset(s for s in args.exclude_sources.split(",") if s)
    train = absolute_manifest(data, out, "train", rank, exclude)
    dev = absolute_manifest(data, out, "dev", rank, exclude)

    n_gpus = torch.cuda.device_count()
    kwargs = trainer_kwargs(args, n_gpus, bf16_ok=n_gpus > 0 and torch.cuda.is_bf16_supported())
    print({"data": str(data), "out": str(out), "resume": resume, "excluded": sorted(exclude), **kwargs}, flush=True)
    if kwargs["strategy"] == "ddp":  # a rank that dies (OOM) frees the others in 10 min, not NCCL's default 30
        kwargs["strategy"] = DDPStrategy(timeout=timedelta(minutes=10))

    model = load_base(args.base_model)
    if args.freeze_layers:
        model.encoder.pre_encode.requires_grad_(False)
        for layer in model.encoder.layers[: args.freeze_layers]:
            layer.requires_grad_(False)
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print({"trainable_params_m": round(trainable / 1e6), "frozen_layers": args.freeze_layers}, flush=True)
    trainer = pl.Trainer(
        **kwargs,
        logger=pl.loggers.CSVLogger(str(out), name="logs"),
        callbacks=[
            # last.ckpt only, written right after each dev check. A checkpoint with AdamW state is
            # ~7.5 GB and Kaggle keeps ~20 GB of output: top-k copies would fill the disk mid-run.
            # ponytail: no best-by-val_wer copy; the CSV log has val_wer per check if one is ever needed.
            ModelCheckpoint(dirpath=str(ckpt_dir), save_last=True, save_top_k=0, save_on_train_epoch_end=False),
            LearningRateMonitor(logging_interval="step"),
            session_budget(args.max_hours),
        ],
    )
    model.set_trainer(trainer)

    train_ds, val_ds = dataset_configs(str(train), str(dev), args.batch, args.workers, n_gpus > 0, args.max_duration)
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
        (ckpt_dir / "last.ckpt").unlink(missing_ok=True)  # final.ckpt supersedes it; frees 7.5 GB for the .nemo
        model.save_to(str(out / NEMO_NAME))
        print("saved", out / NEMO_NAME, flush=True)


if __name__ == "__main__":
    main()
