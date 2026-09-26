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
GPU_MODELS = [
    "gemma3:4b", "qwen3:4b", "gemma3:12b", "qwen3:8b", "qwen3:8b|think", "gpt-oss:20b|low", "phi4:14b", "qwen3:14b",
    "gemma4:e4b", "gemma4:12b", "gemma4:26b", "qwen3:30b-a3b", "mistral-small3.2:24b",
    "hf.co/bartowski/utter-project_EuroLLM-22B-Instruct-2512-GGUF:Q4_K_M",
]
CPU_MODELS = ["gemma3:4b", "qwen3:4b", "gpt-oss:20b|low", "qwen3:30b-a3b", "gemma4:26b"]
STATE = {"step": "setup", "model": "", "note": "", "done": 0, "total": len(GPU_MODELS) + len(CPU_MODELS),
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


def serve():
    env = {**os.environ, "OLLAMA_MODELS": "/tmp/ollama", "OLLAMA_KEEP_ALIVE": "10m", "OLLAMA_HOST": "127.0.0.1:11434"}
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
    sh("git clone -q --depth 1 -b Coflazo-Branch https://github.com/foxymadeit/medpark-challenge /tmp/repo")
    sh(f"{sys.executable} -m pip install -q -e /tmp/repo/minutes")
    install_ollama()
    serve()
    try:  # grammar counts for fluency; optional
        sh("apt-get -qq update && apt-get -qq install -y openjdk-17-jre-headless > /dev/null", timeout=600)
        sh(f"{sys.executable} -m pip install -q language-tool-python")
    except Exception as e:
        log(f"LanguageTool setup failed, fluency uses script checks only: {e!r}")
    sys.path.insert(0, "/tmp/repo/minutes")
    os.chdir("/tmp/repo/minutes")
    from eval import bakeoff
    from eval.meetings import build
    data = Path("/tmp/repo/minutes/eval/data")
    build(data)
    tools = bakeoff.language_tool()

    def progress(i, n):
        STATE["note"] = f"meeting {i}/{n}"
        STATE["progress"] += 1

    STATE["step"] = "smoke"
    sh("ollama pull gemma3:4b", timeout=1800)
    (OUT / "smoke").mkdir(exist_ok=True)
    r = bakeoff.run_model("gemma3:4b", data, OUT / "smoke", tools, only=["med01"], progress=progress)  # extraction and writing
    log(f"smoke test OK: {json.dumps(r['score'])}")

    for cpu_only, models in ((False, GPU_MODELS), (True, CPU_MODELS)):
        for spec in models:
            STATE.update(step="CPU" if cpu_only else "GPU", model=spec, note="pull")
            name = spec.partition("|")[0]
            try:
                sh(f"ollama pull {name}", timeout=2400)
                r = bakeoff.run_model(spec, data, OUT, None if cpu_only else tools, cpu_only=cpu_only,
                                      progress=progress, only=["med02"] if cpu_only else None)
                STATE["results"][spec + (" cpu" if cpu_only else "")] = {**r["score"], "tok_s": r["tokens_per_s"], "peak_gpu_gb": r["peak_gpu_gb"],
                                                                          "minutes": r["minutes"]}
                log(f"{spec}{' (CPU)' if cpu_only else ''}: {json.dumps(STATE['results'][spec + (' cpu' if cpu_only else '')])}")
            except Exception as e:
                STATE["warnings"].append(f"{spec}: {e!r}"[:300])
                log(f"{spec} failed: {e!r}")
                traceback.print_exc()
            finally:
                STATE["done"] += 1
                if not cpu_only and spec.partition("|")[0] not in [m.partition("|")[0] for m in CPU_MODELS]:
                    subprocess.run(f"ollama rm {name}", shell=True)
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
