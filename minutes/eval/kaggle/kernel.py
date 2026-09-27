"""Kaggle job: choose the minutes model. Two T4 GPUs, synthetic meetings only.

Installs Ollama, runs a smoke test with the smallest model, then every
candidate through eval/bakeoff.py, one at a time, deleting each model after
its run to keep the disk free. Once a minute a heartbeat line says how far it
is, what it is on, GPU memory and OK or the problem; /kaggle/working/
status.json holds the same. Results land in /kaggle/working/results/.
"""

import faulthandler
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

T0 = time.time()
WORK = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path("/tmp/work")
OUT = WORK / "results"
OUT.mkdir(parents=True, exist_ok=True)
REPO = Path("/tmp/repo")
# round 2 (2026-09-26 evening): the models that worked in round 1, plus the ones that
# only failed on thinking or a cut-off answer, now fixed in mom/llm.py
# round 3 (2026-09-27 night): round 2 lost the whole 60-minute meeting to one cut-off answer. Now a
# broken window is read in halves, and the product's GPU settings are on: one GPU, 3 requests at once.
GPU_MODELS = ["qwen3:8b", "gpt-oss:20b|low"]
CPU_MODELS = []
os.environ.update(CUDA_VISIBLE_DEVICES="0")
# round 4 (2026-09-27, 04:15): round 3 fixed the empty long meeting (qwen3:8b 8/12 decisions, 11/12
# actions) but took 48 min on it: qwen3's answers ran past 4,096 tokens and were split again and
# again (136k output tokens). Only speed and the long meeting are measured here, one GPU:
# (name, model, window seconds, requests at once)
CONFIGS = [("a-qwen3-w300-p3", "qwen3:8b", 300, 3), ("b-gptoss-w600-p1", "gpt-oss:20b|low", 600, 1),
           ("c-gptoss-w300-p2", "gpt-oss:20b|low", 300, 2)]
ONLY = ["med01", "long01"]
STATE = {"step": "setup", "model": "", "note": "", "done": 0, "total": 3,
         "warnings": [], "results": {}, "progress": 0}


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd, check=True, timeout=None):
    log(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, timeout=timeout)


def gpu():
    r = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                       shell=True, capture_output=True, text=True)
    return " ".join(f"{u.strip()}% {int(m) / 1024:.1f} GB" for u, m in (x.split(",") for x in r.stdout.strip().splitlines() if "," in x))


def heartbeat(every=60, stall=900):
    last, since = None, time.time()
    while True:
        time.sleep(every)
        try:
            if STATE["progress"] != last:
                last, since = STATE["progress"], time.time()
            spent = (time.time() - T0) / 60
            per = spent / STATE["done"] if STATE["done"] else 12
            left = per * (STATE["total"] - STATE["done"])
            problems = []
            if time.time() - since > stall:
                problems.append(f"no progress for {(time.time() - since) / 60:.0f} min")
            if shutil.disk_usage("/tmp").free / 1e9 < 8:
                problems.append("less than 8 GB free on /tmp")
            if spent > 10.5 * 60:
                problems.append("past 10.5 h; Kaggle stops runs at 12 h")
            msg = (f"{100 * STATE['done'] / STATE['total']:.0f}% done, about {left:.0f} min left | {STATE['step']} "
                   f"{STATE['model']} {STATE['note']} | GPU {gpu() or 'n/a'} | " + ("OK" if not problems else "WARNING: " + "; ".join(problems)))
            log(f"[heartbeat] {msg}")
            for p in problems:
                if p not in STATE["warnings"]:
                    STATE["warnings"].append(p)
            (WORK / "status.json").write_text(json.dumps({"minute": round(spent, 1), "status": msg, **STATE}, indent=1))
            if time.time() - since > stall:
                faulthandler.dump_traceback(all_threads=True)
                since = time.time()
        except Exception as e:
            log(f"heartbeat error: {e!r}")


def serve(parallel: int = 3):
    """(Re)start Ollama with room for `parallel` requests: its memory is sized for that many."""
    subprocess.run("pkill -f 'ollama serve'", shell=True)
    time.sleep(2)
    env = {**os.environ, "OLLAMA_MODELS": "/tmp/ollama", "OLLAMA_KEEP_ALIVE": "10m", "OLLAMA_HOST": "127.0.0.1:11434",
           "OLLAMA_NUM_PARALLEL": str(parallel)}
    subprocess.Popen("ollama serve > /tmp/ollama.log 2>&1", shell=True, env=env)
    for _ in range(60):
        if subprocess.run("curl -s 127.0.0.1:11434/api/version", shell=True, capture_output=True).returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("ollama did not start: " + Path("/tmp/ollama.log").read_text()[-500:])


def install_ollama():
    """The installer now ships a .tar.zst and needs zstd, which the Kaggle image
    lacks. Install zstd first; if the script still fails, show why and unpack
    the release archive directly."""
    sh("apt-get -qq update > /dev/null && apt-get -qq install -y zstd pciutils > /dev/null", check=False, timeout=600)
    if sh("curl -fsSL https://ollama.com/install.sh | sh > /tmp/ollama-install.log 2>&1", check=False).returncode != 0:
        log("install.sh failed:\n" + Path("/tmp/ollama-install.log").read_text(errors="replace")[-1500:])
        base = "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64"
        if sh(f"curl -fsSL {base}.tar.zst | zstd -d | tar -x -C /usr", check=False).returncode != 0:
            sh(f"curl -fsSL {base}.tgz | tar -xz -C /usr")
    sh("ollama --version", check=False)


def run():
    threading.Thread(target=heartbeat, daemon=True).start()
    STATE["step"] = "setup"
    sh("git clone -q --depth 1 -b liminal https://github.com/foxymadeit/medpark-challenge /tmp/repo")
    sh(f"{sys.executable} -m pip install -q -e /tmp/repo/minutes")
    install_ollama()
    serve()
    # round 3 measures extraction and speed; fluency was measured in round 2 (LanguageTool skipped)
    sys.path.insert(0, "/tmp/repo/minutes")
    os.chdir("/tmp/repo/minutes")
    from eval import bakeoff
    from eval.long import build as build_long
    from eval.meetings import build
    data = Path("/tmp/repo/minutes/eval/data")
    build(data)
    build_long(data)
    tools = None

    def progress(i, n):
        STATE["note"] = f"meeting {i}/{n}"
        STATE["progress"] += 1

    # no separate smoke test: each configuration starts with the 3-minute med01 before the hour
    import mom.extract
    for name, spec, window, parallel in CONFIGS:
        STATE.update(step="GPU", model=name, note="pull")
        model = spec.partition("|")[0]
        try:
            serve(parallel)
            sh(f"ollama pull {model}", timeout=2400)
            mom.extract.WINDOW_S, mom.extract.PARALLEL = float(window), parallel
            r = bakeoff.run_model(spec, data, OUT / name, None, progress=progress, only=ONLY)
            STATE["results"][name] = {**r["score"], "tok_s": r["tokens_per_s"], "peak_gpu_gb": r["peak_gpu_gb"],
                                      "minutes": r["minutes"], "per_meeting": r.get("per_meeting")}
            log(f"{name}: {json.dumps(STATE['results'][name])[:600]}")
        except Exception as e:
            STATE["warnings"].append(f"{name}: {e!r}"[:300])
            log(f"{name} failed: {e!r}")
            traceback.print_exc()
        finally:
            STATE["done"] += 1
            subprocess.run(f"ollama stop {model}", shell=True)
            (WORK / "run_report.json").write_text(json.dumps(STATE, indent=1))
    STATE["step"] = "done"
    (WORK / "run_report.json").write_text(json.dumps({**STATE, "minutes": round((time.time() - T0) / 60, 1)}, indent=1))
    log("done")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        (WORK / "run_report.json").write_text(json.dumps({**STATE, "failed": traceback.format_exc()[-2000:]}, indent=1))
        raise
