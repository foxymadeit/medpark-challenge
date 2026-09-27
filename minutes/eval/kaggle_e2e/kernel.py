"""Kaggle job: time the whole minutes pipeline on the one-hour meeting.

Run this after the bake-off has picked a model: edit MODELS below. For each
model it runs mom.pipeline.run on eval long01 (60 min, 7 speakers, no names)
exactly as the product does, writing all six documents (PDF and DOCX in RO,
RU and EN), and records the time of every stage, peak GPU memory, tokens,
the verifier's counts, whether each language came from the model, a repair
or the fallback, and the score against the answer key. Then one CPU-only run
on med02 gives the 32 GB CPU tier's timing.

A smoke test (gemma3:4b on med01, full pipeline including XeLaTeX) runs
first, so a broken TeX or Ollama install fails in minutes, not hours. A
heartbeat line every minute says how far it is and OK or the problem;
/kaggle/working/status.json holds the same. Results: /kaggle/working/out/.
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

MODELS = ["gemma3:12b"]          # edit after the bake-off; "name|think" or "name|low" as in eval/bakeoff.py
CPU_MODEL = "gemma3:12b"         # the CPU tier's pick, timed on med02 with num_gpu=0
SMOKE_MODEL = "gemma3:4b"

T0 = time.time()
WORK = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path("/tmp/work")
OUT = WORK / "out"
OUT.mkdir(parents=True, exist_ok=True)
REPO = Path("/tmp/repo")
STATE = {"step": "setup", "model": "", "note": "", "done": 0, "total": len(MODELS) + 2,
         "warnings": [], "results": {}, "progress": 0, "setup_s": {}}


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd, check=True, timeout=None):
    log(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, timeout=timeout)


def gpu():
    r = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                       shell=True, capture_output=True, text=True)
    return " ".join(f"{u.strip()}% {int(m) / 1024:.1f} GB" for u, m in (x.split(",") for x in r.stdout.strip().splitlines() if "," in x))


def heartbeat(every=60, stall=1200):
    last, since = None, time.time()
    while True:
        time.sleep(every)
        try:
            if STATE["progress"] != last:
                last, since = STATE["progress"], time.time()
            spent = (time.time() - T0) / 60
            per = spent / STATE["done"] if STATE["done"] else 25
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
    sh("apt-get -qq install -y zstd pciutils > /dev/null", check=False, timeout=600)
    if sh("curl -fsSL https://ollama.com/install.sh | sh > /tmp/ollama-install.log 2>&1", check=False).returncode != 0:
        log("install.sh failed:\n" + Path("/tmp/ollama-install.log").read_text(errors="replace")[-1500:])
        base = "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64"
        if sh(f"curl -fsSL {base}.tar.zst | zstd -d | tar -x -C /usr", check=False).returncode != 0:
            sh(f"curl -fsSL {base}.tgz | tar -xz -C /usr")
    sh("ollama --version", check=False)


def install_tex():
    """XeLaTeX plus what medpark-mom.cls loads: pdfx, xltabular, titlesec,
    ragged2e, needspace (latex-extra), and Romanian and Russian hyphenation."""
    sh("apt-get -qq install -y --no-install-recommends texlive-xetex texlive-latex-recommended texlive-latex-extra "
       "texlive-lang-european texlive-lang-cyrillic lmodern > /tmp/tex-install.log 2>&1", timeout=1800)
    sh("xelatex --version | head -1", check=False)


def timed(name, fn):
    t = time.time()
    fn()
    STATE["setup_s"][name] = round(time.time() - t)
    log(f"{name}: {STATE['setup_s'][name]} s")


def run_one(spec, mid, data, out, cpu_only=False):
    """The product's own pipeline on one eval meeting, scored against its key."""
    from eval.bakeoff import PeakGPU
    from eval.meetings import DATE
    from eval.score import score_meeting
    from mom.llm import LocalLLM
    from mom.pipeline import run
    from mom.schemas import Fact, Meeting

    model, _, think = spec.partition("|")
    think_arg = {"think": True, "off": False, "low": "low", "medium": "medium"}.get(think) if think else None
    gold = json.loads((data / f"{mid}.gold.json").read_text(encoding="utf-8"))
    llm = LocalLLM(model, "http://127.0.0.1:11434", ctx=16384)
    llm.cpu_only = cpu_only
    peak = PeakGPU()
    peak.start()
    try:
        r = run(data / f"{mid}.txt", out, llm, Meeting(type=gold["type"], date=DATE, start="09:00"),
                langs=("ro", "ru", "en"), think=think_arg)
    finally:
        peak.running = False
    facts = [Fact(**f) for f in json.loads(Path(r["facts"]).read_text(encoding="utf-8"))["facts"]]
    st = r["llm"]
    summary = {"model": spec, "meeting": mid, "cpu_only": cpu_only, "timings_s": r["timings_s"],
               "minutes_total": round(r["timings_s"]["total"] / 60, 1), "peak_gpu_gb": round(peak.peak, 1),
               "llm_calls": st.get("calls"), "prompt_tokens": st.get("prompt_tokens"), "output_tokens": st.get("output_tokens"),
               "tokens_per_s": round(st["output_tokens"] / st["seconds"], 1) if st.get("seconds") else None,
               "checks": r["checks"], "write_source": {k: v["source"] for k, v in r["writing"].items()},
               "score": score_meeting(facts, gold)}
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary


def attempt(label, spec, fn):
    STATE.update(step=label, model=spec, note="")
    try:
        s = fn()
        STATE["results"][f"{label} {spec}"] = s
        log(f"{label} {spec}: {json.dumps(s, ensure_ascii=False)}")
        return s
    except Exception as e:
        STATE["warnings"].append(f"{label} {spec}: {e!r}"[:300])
        log(f"{label} {spec} failed: {e!r}")
        traceback.print_exc()
    finally:
        STATE["done"] += 1
        STATE["progress"] += 1
        (WORK / "run_report.json").write_text(json.dumps(STATE, ensure_ascii=False, indent=1))


def tag(spec):
    return spec.replace(":", "_").replace("/", "_").replace("|", "_")


def run():
    threading.Thread(target=heartbeat, daemon=True).start()
    sh("apt-get -qq update > /dev/null", check=False, timeout=600)
    timed("clone", lambda: sh(f"git clone -q --depth 1 -b Coflazo-Branch https://github.com/foxymadeit/medpark-challenge {REPO}"))
    timed("pip", lambda: sh(f"{sys.executable} -m pip install -q -e {REPO}/minutes"))
    timed("tex", install_tex)
    timed("ollama", install_ollama)
    serve()
    sys.path.insert(0, str(REPO / "minutes"))
    os.chdir(REPO / "minutes")
    from eval.long import build as build_long
    from eval.meetings import build
    data = REPO / "minutes" / "eval" / "data"
    build(data)
    build_long(data)

    STATE["note"] = "pull"
    sh(f"ollama pull {SMOKE_MODEL}", timeout=1800)
    if not attempt("smoke", SMOKE_MODEL, lambda: run_one(SMOKE_MODEL, "med01", data, OUT / "smoke")):
        raise RuntimeError("smoke test failed; see the traceback above")

    for spec in MODELS:
        name = spec.partition("|")[0]
        STATE.update(step="GPU", model=spec, note="pull")
        sh(f"ollama pull {name}", timeout=2400)
        attempt("GPU long01", spec, lambda: run_one(spec, "long01", data, OUT / tag(spec)))
        if name != CPU_MODEL.partition("|")[0]:
            subprocess.run(f"ollama rm {name}", shell=True)

    sh(f"ollama pull {CPU_MODEL.partition('|')[0]}", timeout=2400)
    attempt("CPU med02", CPU_MODEL, lambda: run_one(CPU_MODEL, "med02", data, OUT / f"{tag(CPU_MODEL)}_cpu", cpu_only=True))

    STATE["step"] = "done"
    (WORK / "run_report.json").write_text(json.dumps({**STATE, "minutes": round((time.time() - T0) / 60, 1)}, ensure_ascii=False, indent=1))
    log("done")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        (WORK / "run_report.json").write_text(json.dumps({**STATE, "failed": traceback.format_exc()[-2000:]}, indent=1))
        raise
