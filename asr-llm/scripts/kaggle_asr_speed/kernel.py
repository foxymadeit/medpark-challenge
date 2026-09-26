"""Kaggle T4: the batched Whisper decoder (asr_llm/asr_batched.py) against the one-at-a-time
decoder the ASR bake-off measured (coflaz/liminal-asr-bakeoff, 26 Sep 2026), on one GPU.

Same bench, same sets, same scorer as the bake-off (asr_train.zeroshot), so the character
error rates compare row for row; then 60 minutes of Medpark audio timed per batch size.
Gate for shipping: error within 0.5 points of the bake-off on every scored recording, and an
hour transcribed in 7 minutes or less.

Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_asr_speed
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

REPO = Path("/tmp/repo")
ASR = REPO / "asr-llm"
WORK = Path("/kaggle/working")
OUT = WORK / "out"
T0 = time.time()
WHISPER = {"large-v3": "models/whisper"}
BATCHES = [8, 16]
os.environ.setdefault("BENCH_N", "60")
STEPS = ["setup", "smoke"] + [f"whisper:b{b}" for b in BATCHES[:1]] + [f"hour:b{b}" for b in BATCHES]
STATE = {"step": "setup", "done": 0, "last": time.time(), "warnings": []}
PEAK: dict[str, float] = {}


def log(msg: str) -> None:
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd: str, env: dict | None = None) -> None:
    log(f"$ {cmd}")
    subprocess.run(cmd, shell=True, check=True, cwd=ASR if ASR.exists() else None, env=env)


def gpu_line() -> str:
    return subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                          shell=True, capture_output=True, text=True).stdout.strip().replace("\n", " | ")


def heartbeat() -> None:
    while True:
        time.sleep(60)
        spent = (time.time() - T0) / 60
        left = (spent / STATE["done"] if STATE["done"] else 20) * (len(STEPS) - STATE["done"])
        problems = []
        if time.time() - STATE["last"] > 60 * 60:
            problems.append(f"no step finished for {(time.time() - STATE['last']) / 60:.0f} min")
        if shutil.disk_usage(WORK).free / 1e9 < 5:
            problems.append("under 5 GB free")
        if spent > 10.5 * 60:
            problems.append("past 10.5 h; Kaggle stops at 12 h")
        try:
            used = sum(int(x.split(",")[1]) for x in gpu_line().split(" | ") if "," in x) / 1024
            PEAK[STATE["step"]] = max(PEAK.get(STATE["step"], 0.0), used)
        except ValueError:
            pass
        log(f"[heartbeat] {100 * STATE['done'] / len(STEPS):.0f}% done, about {left:.0f} min left | {STATE['step']} | "
            f"GPU {gpu_line() or 'n/a'} | " + ("OK" if not problems else "WARNING: " + "; ".join(problems)))


def step(name: str, fn, *args) -> None:
    STATE["step"] = name
    log(f"== {name}")
    try:
        fn(*args)
    except Exception:
        (OUT / f"{name.replace(':', '_').replace('+', '_')}.error.txt").write_text(traceback.format_exc())
        STATE["warnings"].append(f"{name} failed")
        traceback.print_exc()
    finally:
        STATE["done"] += 1
        STATE["last"] = time.time()


def whisper_env(model: str, merge: bool, joint: bool = False, batch: int = 1) -> dict:
    env = {**os.environ, "MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16",
           "MOM_ASR_MODEL_DIR": str(ASR / WHISPER[model]), "MOM_CS_MERGE": str(merge).lower(),
           "MOM_CORRECT_TERMS": "false", "MOM_ASR_BATCH_SIZE": str(batch), "CUDA_VISIBLE_DEVICES": "0"}  # scored raw here; the corrector is measured separately below
    if joint:
        env["MOM_ASR_JOINT_LANGUAGES"] = '["ro", "ru"]'
    return env


def team_clips() -> str:
    """The team's code-switched readings (dataset coflaz/liminal-team-recordings), scored like the gold."""
    clips = []
    for name, stem in (("team1", "team_rec1_cristina_all"), ("team2", "team_rec2_no_cristina")):
        audio = next(Path("/kaggle/input").rglob(f"{stem}.m4a"), None)
        ref = next(Path("/kaggle/input").rglob(f"{stem}.ref.txt"), None)
        if audio and ref:
            clips.append(f"--clip {name}={audio},{ref}")
        else:
            STATE["warnings"].append(f"{stem} not attached")
    return " ".join(clips)


BENCH = f"{sys.executable} -m asr_train.zeroshot --work {WORK} --sets gold --audio data/Medpark_audio.m4a " \
        f"--clip synthetic=data/syntethic_record.m4a,data/recording_scripts/medical_round.md {team_clips()}"


def run_whisper(batch: int) -> None:
    sh(f"{BENCH} --models whisper", env=whisper_env("large-v3", False, batch=batch))
    (OUT / "result_whisper.json").rename(OUT / f"result_whisper-b{batch}.json")
    for f in OUT.glob("hyp_whisper_*.json"):
        f.rename(OUT / f.name.replace("hyp_whisper_", f"hyp_whisper-b{batch}_"))


def time_hour(batch: int) -> None:
    code = ("import json,time,pathlib;from asr_llm.pipeline import transcribe_audio;"
            f"w=pathlib.Path('{WORK}/data/medpark_60min.wav');t=time.perf_counter();tr,tm=transcribe_audio(w);"
            "s=time.perf_counter()-t;"
            f"pathlib.Path('{OUT}/result_hour-b{batch}.json').write_text(json.dumps("
            "{'seconds':round(s,1),'rtfx':round(3600/s,1),'stages':{k:round(v,1) for k,v in tm.items()},'segments':len(tr.segments)}))")
    sh(f"{sys.executable} -c \"{code}\"", env=whisper_env("large-v3", False, batch=batch))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        def setup():
            sh(f"git clone -q --depth 1 -b liminal https://github.com/foxymadeit/medpark-challenge {REPO}")
            sh("pip install -q huggingface_hub soundfile pyarrow")
            sh(f"pip install -q -e '{ASR}[asr]' wordfreq && python scripts/fetch_whisper.py large-v3")
        step("setup", setup)

        def smoke():  # batched decoding end to end on the synthetic round before anything long
            sh(f"{sys.executable} -m asr_llm.cli data/syntethic_record.m4a --skip-llm --out {OUT}/smoke.json "
               f"--transcript-out {OUT}/smoke_transcript.json", env=whisper_env("large-v3", False, batch=BATCHES[0]))
            log("smoke test passed: " + json.loads((OUT / "smoke_transcript.json").read_text())["text"][:200])
        step("smoke", smoke)
        step(f"whisper:b{BATCHES[0]}", run_whisper, BATCHES[0])
        for b in BATCHES:
            step(f"hour:b{b}", time_hour, b)
    finally:
        report = {"minutes": round((time.time() - T0) / 60, 1), "warnings": STATE["warnings"],
                  "peak_gpu_gb": {k: round(v, 1) for k, v in PEAK.items()}, "results": {}}
        for f in sorted(OUT.glob("result_*.json")):
            report["results"][f.stem] = json.loads(f.read_text(encoding="utf-8"))
        (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
        log(f"report written; warnings: {STATE['warnings'] or 'none'}")
        shutil.rmtree(ASR / "models", ignore_errors=True)


if __name__ == "__main__":
    main()
