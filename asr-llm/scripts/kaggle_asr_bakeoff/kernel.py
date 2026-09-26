"""Kaggle T4: which ASR setup the product ships. A wrapper around asr_train.zeroshot
(same test sets, same scorer) that adds what the zero-shot bench leaves out:

- the product's Whisper pipeline four ways: large-v3 and large-v3-turbo, each with the
  word-level language merge off and on (asr_llm.asr.merge_words);
- the glossary term corrector (asr_llm/correct.py) applied afterwards to every engine's
  output, scored before and after, so it ships only if it helps;
- one-hour timing for the Whisper setups (60 min of Medpark audio).

No dataset needed: the Medpark recording, the gold and the synthetic round are in the repo.
Telemetry: a heartbeat line every 60 s (% done, minutes left, OK/WARNING), a smoke test
before the long work, and out/report.json at the end, written on failure too.

Push from the repo root:  kaggle kernels push -p asr-llm/scripts/kaggle_asr_bakeoff
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
WHISPER = {"large-v3": "models/whisper", "turbo": "models/whisper-turbo"}
VARIANTS = [(m, merge) for m in WHISPER for merge in (False, True)]
STEPS = ["setup", "smoke", "nemo"] + [f"whisper:{m}{'+merge' if g else ''}" for m, g in VARIANTS] + ["hour:large-v3", "hour:turbo", "correct"]
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


def whisper_env(model: str, merge: bool) -> dict:
    return {**os.environ, "MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16",
            "MOM_ASR_MODEL_DIR": str(ASR / WHISPER[model]), "MOM_CS_MERGE": str(merge).lower(),
            "MOM_CORRECT_TERMS": "false"}  # scored raw here; the corrector is measured separately below


BENCH = f"{sys.executable} -m asr_train.zeroshot --work {WORK} --sets all " \
        "--clip synthetic=data/syntethic_record.m4a,data/recording_scripts/medical_round.md"


def run_whisper(model: str, merge: bool) -> None:
    label = model + ("-merge" if merge else "")
    sh(f"{BENCH} --models whisper", env=whisper_env(model, merge))
    (OUT / "result_whisper.json").rename(OUT / f"result_whisper-{label}.json")
    for f in OUT.glob("hyp_whisper_*.json"):
        f.rename(OUT / f.name.replace("hyp_whisper_", f"hyp_whisper-{label}_"))


def time_hour(model: str) -> None:
    code = ("import json,time,pathlib;from asr_llm.pipeline import transcribe_audio;"
            f"w=pathlib.Path('{WORK}/data/medpark_60min.wav');t=time.perf_counter();tr,tm=transcribe_audio(w);"
            "s=time.perf_counter()-t;"
            f"pathlib.Path('{OUT}/result_hour-{model}.json').write_text(json.dumps("
            "{'seconds':round(s,1),'rtfx':round(3600/s,1),'stages':{k:round(v,1) for k,v in tm.items()},'segments':len(tr.segments)}))")
    sh(f"{sys.executable} -c \"{code}\"", env=whisper_env(model, False))


def correct_all() -> None:
    """The corrector over every engine's hypotheses, scored against the same references."""
    sys.path.insert(0, str(ASR))
    from asr_llm.correct import correct_text
    from asr_llm.score import glossary_terms
    from asr_train.metrics import fold, score

    terms = glossary_terms()
    table = {}
    for f in sorted(OUT.glob("hyp_*.json")):
        rows = [r for r in json.loads(f.read_text(encoding="utf-8")) if r.get("ref")]
        if not rows:
            continue
        refs, hyps = [r["ref"] for r in rows], [r["hyp"] or "" for r in rows]
        fixed, changes = [], []
        for h in hyps:
            lang = "ru" if sum("Ѐ" <= c <= "ӿ" for c in h) > len(h) / 3 else "ro"
            text, c = correct_text(h, lang)
            fixed.append(text)
            changes += c
        ref_all = fold(" ".join(refs))
        wanted = [t for t in terms if t in ref_all]
        hit = lambda hs: sum(t in fold(" ".join(hs)) for t in wanted)  # noqa: E731
        table[f.stem] = {"before": score(refs, hyps), "after": score(refs, fixed), "terms_in_ref": len(wanted),
                         "terms_hit_before": hit(hyps), "terms_hit_after": hit(fixed), "changes": changes[:50]}
    (OUT / "result_corrector.json").write_text(json.dumps(table, ensure_ascii=False, indent=1))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        def setup():
            sh(f"git clone -q --depth 1 -b samoilov-asr-llm https://github.com/foxymadeit/medpark-challenge {REPO}")
            sh("pip install -q 'nemo_toolkit[asr]' huggingface_hub soundfile pyarrow")
            sh(f"pip install -q -e '{ASR}[asr]' && python scripts/fetch_whisper.py all")
        step("setup", setup)

        def smoke():  # the product pipeline end to end on the synthetic round, smallest setup, before anything long
            sh(f"{sys.executable} -m asr_llm.cli data/syntethic_record.m4a --skip-llm --out {OUT}/smoke.json "
               f"--transcript-out {OUT}/smoke_transcript.json", env=whisper_env("turbo", False))
            log("smoke test passed: " + json.loads((OUT / "smoke_transcript.json").read_text())["text"][:200])
        step("smoke", smoke)
        step("nemo", sh, f"{BENCH} --audio data/Medpark_audio.m4a --models parakeet,canary,jackrabbit")
        for model, merge in VARIANTS:
            step(f"whisper:{model}{'+merge' if merge else ''}", run_whisper, model, merge)
        for model in WHISPER:
            step(f"hour:{model}", time_hour, model)
        step("correct", correct_all)
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
