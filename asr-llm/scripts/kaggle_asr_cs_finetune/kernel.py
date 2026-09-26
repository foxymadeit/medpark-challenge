"""Kaggle T4: fine-tune Parakeet-TDT-0.6B-v3 on spliced RO/RU/EN code-switched speech, in one session,
then score it on the gold file and the public sets the same way the bake-off does.

Why Parakeet v3 and not SpeD-RoASR: SpeD's tokenizer has the 31 Romanian letters only, so it cannot
learn to write a Russian word in Cyrillic without a new tokenizer and far more than a few GPU hours.
Parakeet v3 already writes all three languages and picks the language itself.

Data (asr_train.build_data, the team's builder): Common Voice RO / RU / EN, FLEURS, CS-FLEURS ru-en,
plus a speech collage: a phrase of one language cut into a sentence of another, the donor taken from
the same speaker whenever the bank has that speaker in both languages (70% of those cases), since a
voice change at every switch teaches the model the wrong cue (arXiv:2606.19381).

Telemetry: a heartbeat every 60 s (step, % done, minutes left, GPU, OK/WARNING), a smoke run of every
stage on a tiny set first, out/report.json at the end (on failure too).
Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_asr_cs_finetune
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

BRANCH = "samoilov-asr-llm"
REPO = Path("/tmp/repo")
ASR = REPO / "asr-llm"
WORK = Path("/kaggle/working")
OUT = WORK / "out"
T0 = time.time()
TRAIN_HOURS = 2.0
STEPS = ["setup", "smoke", "data", "finetune", "score"]
STATE = {"step": "setup", "done": 0, "last": time.time(), "warnings": []}


def log(msg: str) -> None:
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd: str) -> None:
    log(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True, cwd=ASR if ASR.exists() else None)


def heartbeat() -> None:
    expected = {"setup": 10, "smoke": 15, "data": 75, "finetune": TRAIN_HOURS * 60 + 10, "score": 25}
    while True:
        time.sleep(60)
        left = sum(expected[s] for s in STEPS[STATE["done"]:]) - (time.time() - STATE["last"]) / 60
        problems = []
        if time.time() - STATE["last"] > (expected.get(STATE["step"], 60) + 45) * 60:
            problems.append(f"{STATE['step']} is {((time.time() - STATE['last']) / 60):.0f} min in, longer than planned")
        if shutil.disk_usage(WORK).free / 1e9 < 5 or shutil.disk_usage("/tmp").free / 1e9 < 10:
            problems.append("low disk")
        if (time.time() - T0) / 3600 > 10.5:
            problems.append("past 10.5 h; Kaggle stops at 12 h")
        gpu = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                             shell=True, capture_output=True, text=True).stdout.strip().replace("\n", " | ")
        log(f"[heartbeat] {100 * STATE['done'] / len(STEPS):.0f}% done, about {max(left, 0):.0f} min left | {STATE['step']} | "
            f"GPU {gpu or 'n/a'} | " + ("OK" if not problems else "WARNING: " + "; ".join(problems)))


def step(name: str, fn) -> bool:
    STATE["step"], STATE["last"] = name, time.time()
    log(f"== {name}")
    try:
        fn()
        return True
    except Exception:
        (OUT / f"{name}.error.txt").write_text(traceback.format_exc())
        STATE["warnings"].append(f"{name} failed")
        traceback.print_exc()
        return False
    finally:
        STATE["done"] += 1


def setup() -> None:
    subprocess.run(f"git clone -q --depth 1 -b {BRANCH} https://github.com/foxymadeit/medpark-challenge {REPO}", shell=True, check=True)
    sh("pip install -q 'nemo_toolkit[asr]' uroman huggingface_hub soundfile pyarrow librosa")


def smoke() -> None:  # every stage on a tiny set, so a broken stage costs minutes, not hours
    sh(f"{sys.executable} -m asr_train.build_data --out /tmp/smoke --sources fleurs --collage-hours 0.1 --per-lang 60 --raw-dir /tmp/raw")
    sh(f"{sys.executable} -m asr_train.finetune --data-dir /tmp/smoke --out /tmp/ft-smoke --max-steps 10 --val-every 5 --batch 2 --accum 1")
    shutil.rmtree("/tmp/ft-smoke", ignore_errors=True)
    shutil.rmtree("/tmp/smoke", ignore_errors=True)


def data() -> None:
    sh(f"{sys.executable} -m asr_train.build_data --out /tmp/asrdata --raw-dir /tmp/raw --prune-raw "
       "--sources cv_ro,cv_ru,cv_en,fleurs,csfleurs_ru_en --collage-hours 10 --per-lang 3000")
    for name in ("stats.json", "hours.json"):
        if (Path("/tmp/asrdata") / name).exists():
            shutil.copy(Path("/tmp/asrdata") / name, OUT / f"data_{name}")


def finetune() -> None:
    sh(f"{sys.executable} -m asr_train.finetune --data-dir /tmp/asrdata --out {WORK}/ft --max-hours {TRAIN_HOURS} "
       "--max-steps 4000 --val-every 400")


def score() -> None:
    nemo = sorted((WORK / "ft").rglob("*.nemo"), key=lambda p: p.stat().st_mtime)
    if not nemo:
        raise FileNotFoundError("no .nemo written by the fine-tune")
    sh(f"{sys.executable} -m asr_train.zeroshot --work {WORK}/bench --audio data/Medpark_audio.m4a "
       "--sets gold,rompar_md,fleurs_ro,fleurs_ru,fleurs_en,cs_ru_en,cs_ro_en --n 60 --models parakeet "
       f"--model-path parakeet={nemo[-1]} --clip synthetic=data/syntethic_record.m4a,data/recording_scripts/medical_round.md")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        ok = step("setup", setup) and step("smoke", smoke)
        if ok and step("data", data) and step("finetune", finetune):
            step("score", score)
    finally:
        report = {"minutes": round((time.time() - T0) / 60, 1), "warnings": STATE["warnings"], "train_hours": TRAIN_HOURS}
        for f in sorted((WORK / "bench" / "out").glob("result_*.json")):
            report[f.stem] = json.loads(f.read_text(encoding="utf-8"))
        (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
        log(f"report written; warnings: {STATE['warnings'] or 'none'}")


if __name__ == "__main__":
    main()
