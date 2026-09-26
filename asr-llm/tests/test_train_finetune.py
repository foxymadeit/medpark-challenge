import json
import os

import pytest

from asr_train.finetune import (
    absolute_manifest,
    check_manifests,
    main,
    optim_config,
    parse_args,
    resolve_resume,
    trainer_kwargs,
)


def _dataset(root):
    (root / "audio").mkdir(parents=True)
    (root / "audio" / "a.flac").write_bytes(b"")
    rows = {"train": [{"audio_filepath": "audio/a.flac", "duration": 1800.0, "text": "x"}] * 2,
            "dev": [{"audio_filepath": "audio/gone.flac", "duration": 3.0, "text": "y"}]}
    for name, part in rows.items():
        (root / f"{name}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in part))
    return root


def test_hardware_profiles():
    args = parse_args(["--data-dir", "d"])
    two_t4 = trainer_kwargs(args, n_gpus=2, bf16_ok=False)
    assert (two_t4["devices"], two_t4["strategy"], two_t4["precision"]) == (2, "ddp", "16-mixed")
    one_ampere = trainer_kwargs(args, n_gpus=1, bf16_ok=True)
    assert (one_ampere["devices"], one_ampere["strategy"], one_ampere["precision"]) == (1, "auto", "bf16-mixed")
    cpu = trainer_kwargs(args, n_gpus=0, bf16_ok=False)
    assert (cpu["accelerator"], cpu["devices"], cpu["precision"]) == ("cpu", 1, "32")
    assert two_t4["val_check_interval"] == 500 * 4  # batches = 500 optimizer steps at accum 4
    with pytest.raises(ValueError, match="only 1 GPU"):
        trainer_kwargs(parse_args(["--data-dir", "d", "--devices", "2"]), n_gpus=1, bf16_ok=True)


def test_env_fallbacks_keep_old_launch_lines(monkeypatch):
    monkeypatch.setenv("DATA_DIR", "/data")
    monkeypatch.setenv("MAX_STEPS", "7")
    args = parse_args([])
    assert str(args.data_dir) == "/data" and args.max_steps == 7
    monkeypatch.delenv("DATA_DIR")
    with pytest.raises(SystemExit):
        parse_args([])


def test_warmup_fits_a_short_run():
    assert optim_config(3e-5, 500, 5000)["sched"]["warmup_steps"] == 500
    assert optim_config(3e-5, 500, 50)["sched"]["warmup_steps"] == 5


def test_manifest_paths_become_absolute_per_rank(tmp_path):
    data = _dataset(tmp_path / "ds")
    dest = absolute_manifest(data, tmp_path / "out", "train", rank="1")
    assert dest.name == "train.rank1.jsonl"
    row = json.loads(dest.read_text().splitlines()[0])
    assert row["audio_filepath"] == str((data / "audio/a.flac").resolve())


def test_check_reports_hours_and_missing_audio(tmp_path):
    report = check_manifests(_dataset(tmp_path))
    assert report["train"]["hours"] == 1.0 and report["train"]["missing_audio"] == 0
    assert report["dev"]["missing_audio"] == 1 and report["dev"]["first_missing"] == ["audio/gone.flac"]
    assert report["train"]["hours_by_source"] == {"?": 1.0}


def test_training_refuses_missing_audio(tmp_path):
    with pytest.raises(SystemExit, match="manifests not usable"):
        main(["--data-dir", str(_dataset(tmp_path / "ds")), "--out", str(tmp_path / "out")])


def test_resume_auto_picks_the_newest(tmp_path):
    assert resolve_resume(None, tmp_path) is None
    assert resolve_resume("auto", tmp_path) is None  # nothing yet: fresh start
    last, final = tmp_path / "last.ckpt", tmp_path / "final.ckpt"
    final.write_bytes(b"")
    last.write_bytes(b"")
    os.utime(final, (1, 1))  # a stale final.ckpt from an earlier session
    assert resolve_resume("auto", tmp_path) == str(last)
    with pytest.raises(FileNotFoundError):
        resolve_resume(str(tmp_path / "nope.ckpt"), tmp_path)
