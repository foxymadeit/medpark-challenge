"""Kaggle GPU job: how long Liminal takes on a 60-minute recording, stage by
stage, on one 16 GB GPU (a T4 here), with the product's own commands.

For every hour in the attached test set (coflaz/liminal-hour-tests, built by
coflaz/liminal-hour-tests-data) it does what the backend does
(backend/jobs.py, all from the merged liminal branch):

  1. transcription (asr-llm/) and speaker diarization
     (diarization/) side by side,
  2. the recogniser's segments unwrapped into transcript.json,
  3. mom report (minutes/): RO, RU and EN minutes as
     PDF and DOCX,

and records each stage's wall time, the total (challenge target: under 15 min
per 60-min recording, upload to email; the email itself is a local SMTP send
of a few seconds), peak GPU and RAM, CER and WER against the reference, the
recogniser's language checks, DER for the ICSI hour, and the minutes report.

A smoke test (the first 3 minutes of one hour, every stage) runs first. A
heartbeat line every minute; /kaggle/working/status.json holds the same.
Edit the constants below once the ASR and minutes bake-offs pick winners.
"""

import faulthandler
import json
import os
import shlex
import shutil
import subprocess
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# ---------------------------------------------------------------- what to test (edit after the bake-offs)
ASR_FETCH = "large-v3"                     # scripts/fetch_whisper.py argument: large-v3 | turbo
ASR_ENV = {"MOM_DEVICE": "cuda", "MOM_ASR_COMPUTE_TYPE": "int8_float16", "MOM_ASR_MODEL_DIR": "models/whisper",
           "MOM_CS_MERGE": "false", "MOM_CORRECT_TERMS": "true"}
MINUTES_MODEL = "qwen3:8b"                 # Ollama tag the minutes use (MOM_LLM_MODEL)
HOURS = ["icsi_60", "kremlin_60", "md_parl_60", "rompar_60"]
MEETING_TYPE = {"icsi_60": "administrative", "kremlin_60": "executive", "md_parl_60": "administrative",
                "rompar_60": "administrative"}
# the backend's defaults (LIMINAL_*_CMD); {audio} {work} {session} {type} {date} {start} are filled per argument
CMDS = {
    "asr": f"{sys.executable} -m asr_llm.cli {{audio}} --skip-llm --out {{work}}/asr.json",
    "diarize": "diarizer file {audio} --out {work}/diarization --plain",
    "minutes": "mom report {work}/transcript.json --session {session} --type {type} --date {date} "
               "--start {start} --out {work}/minutes",
}
BRANCH = "liminal"                         # the merged product: every stage from one checkout
GIT = "https://github.com/foxymadeit/medpark-challenge"

T0 = time.time()
WORK = Path("/kaggle/working") if Path("/kaggle/working").exists() else Path("/tmp/work")
OUT = WORK / "out"
OUT.mkdir(parents=True, exist_ok=True)
LIMINAL = ASR = Path("/tmp/liminal")
OFFLINE_ENV = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
               "HF_HUB_DISABLE_TELEMETRY": "1", "DO_NOT_TRACK": "1"}
STATE = {"step": "setup", "hour": "", "note": "", "done": 0, "total": len(HOURS) + 1, "progress": 0,
         "warnings": [], "setup_s": {}, "results": {}}
STATE["total"] += 1   # the team recordings


def log(msg):
    print(f"[{(time.time() - T0) / 60:6.1f} min] {msg}", flush=True)


def sh(cmd, check=True, timeout=None, cwd=None, env=None):
    log(f"$ {cmd}")
    return subprocess.run(cmd, shell=True, check=check, timeout=timeout, cwd=cwd, env=env)


def gpu_used():
    r = subprocess.run("nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader,nounits",
                       shell=True, capture_output=True, text=True)
    rows = [x.split(",") for x in r.stdout.strip().splitlines() if "," in x]
    return [(int(u), int(m) / 1024) for u, m in rows]


class Peak(threading.Thread):
    """Highest GPU memory (GB, all GPUs) and system RAM in use while running."""

    def __init__(self):
        super().__init__(daemon=True)
        self.gpu = self.ram = 0.0
        self.running = True

    def run(self):
        import psutil
        while self.running:
            self.gpu = max(self.gpu, sum(m for _, m in gpu_used()))
            self.ram = max(self.ram, psutil.virtual_memory().used / 1e9)
            time.sleep(2)


def heartbeat(every=60, stall=1800):
    last, since = None, time.time()
    while True:
        time.sleep(every)
        try:
            if STATE["progress"] != last:
                last, since = STATE["progress"], time.time()
            spent = (time.time() - T0) / 60
            per = spent / STATE["done"] if STATE["done"] else 35
            left = per * (STATE["total"] - STATE["done"])
            problems = []
            if time.time() - since > stall:
                problems.append(f"no progress for {(time.time() - since) / 60:.0f} min")
            if shutil.disk_usage("/tmp").free / 1e9 < 8:
                problems.append("less than 8 GB free on /tmp")
            if spent > 10.5 * 60:
                problems.append("past 10.5 h; Kaggle stops runs at 12 h")
            g = " ".join(f"{u}% {m:.1f} GB" for u, m in gpu_used()) or "n/a"
            msg = (f"{100 * STATE['done'] / STATE['total']:.0f}% done, about {left:.0f} min left | {STATE['step']} "
                   f"{STATE['hour']} {STATE['note']} | GPU {g} | " + ("OK" if not problems else "WARNING: " + "; ".join(problems)))
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


# ---------------------------------------------------------------- setup

def timed(name, fn):
    STATE["step"] = f"setup: {name}"
    t = time.time()
    fn()
    STATE["setup_s"][name] = round(time.time() - t)
    log(f"{name}: {STATE['setup_s'][name]} s")


def clone():
    sh(f"git clone -q --depth 1 -b {BRANCH} {GIT} {LIMINAL}")
    sh("git log -1 --format='%h %an %s'", cwd=LIMINAL, check=False)


def install_python():
    sh(f"{sys.executable} -m pip install -q -e {LIMINAL}/diarization -e {LIMINAL}/minutes -e '{ASR}/asr-llm[asr]' psutil rapidfuzz")
    sh(f"{sys.executable} scripts/fetch_whisper.py {ASR_FETCH}", cwd=ASR / "asr-llm")


def install_ollama():
    """The installer ships a .tar.zst and needs zstd, which the image lacks."""
    sh("apt-get -qq update > /dev/null && apt-get -qq install -y zstd pciutils > /dev/null", check=False, timeout=900)
    if sh("curl -fsSL https://ollama.com/install.sh | sh > /tmp/ollama-install.log 2>&1", check=False).returncode != 0:
        log("install.sh failed:\n" + Path("/tmp/ollama-install.log").read_text(errors="replace")[-1500:])
        base = "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64"
        if sh(f"curl -fsSL {base}.tar.zst | zstd -d | tar -x -C /usr", check=False).returncode != 0:
            sh(f"curl -fsSL {base}.tgz | tar -xz -C /usr")
    env = {**os.environ, "OLLAMA_MODELS": "/tmp/ollama", "OLLAMA_KEEP_ALIVE": "10m", "OLLAMA_HOST": "127.0.0.1:11434"}
    subprocess.Popen("ollama serve > /tmp/ollama.log 2>&1", shell=True, env=env)
    for _ in range(60):
        if subprocess.run("curl -s 127.0.0.1:11434/api/version", shell=True, capture_output=True).returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("ollama did not start: " + Path("/tmp/ollama.log").read_text()[-500:])
    sh(f"ollama pull {MINUTES_MODEL}", timeout=2400)


def install_tex():
    """XeLaTeX plus what medpark-mom.cls loads, and RO and RU hyphenation."""
    sh("apt-get -qq install -y --no-install-recommends texlive-xetex texlive-latex-recommended texlive-latex-extra "
       "texlive-lang-european texlive-lang-cyrillic lmodern poppler-utils > /tmp/tex-install.log 2>&1", timeout=1800)


# ---------------------------------------------------------------- the product's stages (as backend/jobs.py)

def stage(name, values, work):
    args = [part.format(**values) for part in shlex.split(CMDS[name])]
    if name == "minutes" and not values["session"]:   # drop the flag and its empty value together
        i = args.index("--session")
        del args[i:i + 2]
    env = {**os.environ, **OFFLINE_ENV, "MOM_LLM_MODEL": MINUTES_MODEL,
           **({k: str(ASR / "asr-llm" / v) if k == "MOM_ASR_MODEL_DIR" else v for k, v in ASR_ENV.items()}
              if name == "asr" else {})}
    (work / "logs").mkdir(parents=True, exist_ok=True)
    t = time.perf_counter()
    with open(work / "logs" / f"{name}.log", "w") as out:
        code = subprocess.run(args, cwd=ASR / "asr-llm" if name == "asr" else None, stdout=out,
                              stderr=subprocess.STDOUT, env=env, timeout=3 * 3600).returncode
    seconds = round(time.perf_counter() - t, 1)
    if code != 0:
        raise RuntimeError(f"{name} exited {code}: " + (work / "logs" / f"{name}.log").read_text(errors="replace")[-1500:])
    return seconds


def transcript_segments(path):
    """Copied from backend/jobs.py: the recogniser's segments whatever the wrapper."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("transcript"), dict):
        data = data["transcript"]
    raw = data.get("segments", []) if isinstance(data, dict) else data
    out = []
    for s in raw if isinstance(raw, list) else []:
        text = str(s.get("text", "")).strip()
        if not text:
            continue
        seg = {"start": float(s.get("start", 0)), "end": float(s.get("end", s.get("start", 0))), "text": text}
        if s.get("language"):
            seg["language"] = s["language"]
        if s.get("speaker"):
            seg["speaker"] = s["speaker"]
        out.append(seg)
    return out


def run_pipeline(audio, work, meeting_type, date="2026-09-24"):
    """Transcription and diarization side by side, then the minutes. Returns stage times."""
    work.mkdir(parents=True, exist_ok=True)
    values = {"audio": str(audio), "work": str(work), "type": meeting_type, "date": date,
              "start": "09:00", "session": ""}
    t = time.perf_counter()
    times = {}
    with ThreadPoolExecutor(2) as pool:
        asr = pool.submit(stage, "asr", values, work)
        diar = pool.submit(stage, "diarize", values, work)
        times["asr"] = asr.result()
        try:
            times["diarize"] = diar.result()
        except RuntimeError as e:   # the product carries on without speakers; so does the timing
            times["diarize"] = None
            log(f"diarization failed, minutes without speakers: {str(e)[:300]}")
    times["asr_and_diarize_wall"] = round(time.perf_counter() - t, 1)
    segments = transcript_segments(work / "asr.json")
    (work / "transcript.json").write_text(json.dumps({"segments": segments}, ensure_ascii=False, indent=1), encoding="utf-8")
    session = next((p for p in sorted((work / "diarization").glob("*.json"))
                    if "turns" in json.loads(p.read_text())), None) if (work / "diarization").exists() else None
    values["session"] = str(session) if session else ""
    times["minutes"] = stage("minutes", values, work)
    times["total"] = round(time.perf_counter() - t, 1)
    return times, segments, session


# ---------------------------------------------------------------- scoring

def asr_scores(segments, entry, root, work):
    from rapidfuzz.distance import Levenshtein
    from asr_llm.clean import _fold
    from asr_llm.pipeline import load_transcript
    from asr_llm.score import report

    out = {}
    try:   # the recogniser's own language and script checks, no reference needed
        out.update(report(load_transcript(work / "asr.json").segments))
    except Exception as e:
        out["lid_error"] = repr(e)[:200]
    if not entry.get("reference"):
        return out
    window = float(entry.get("reference_window_s") or 3600)
    lines = (root / entry["reference"]).read_text(encoding="utf-8").splitlines()
    ref = _fold("\n".join(x for x in lines if not x.lstrip().startswith("#")))
    hyp = _fold(" ".join(s["text"] for s in segments if (s["start"] + s["end"]) / 2 < window))   # the scorer's midpoint rule
    out.update(reference_window_s=window, ref_chars=len(ref),
               cer=round(Levenshtein.distance(ref, hyp) / max(1, len(ref)), 3),
               wer=round(Levenshtein.distance(ref.split(), hyp.split()) / max(1, len(ref.split())), 3))
    return out


def der_score(session, rttm):
    """DER the diarizer's own strict way (diarization/eval/der.py): 10 ms, no collar."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("der", LIMINAL / "diarization" / "eval" / "der.py")
    der = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(der)
    hyp = [(t["speaker"], float(t["start"]), float(t["end"])) for t in json.loads(session.read_text())["turns"]]
    return {k: round(float(v), 3) if isinstance(v, float) else int(v) for k, v in der.der(der.read_rttm(rttm), hyp).items()}


def minutes_summary(work):
    rep = next((work / "minutes").glob("*.report.json"), None)
    if not rep:
        return {}
    r = json.loads(rep.read_text(encoding="utf-8"))
    return {"checks": r.get("checks"), "timings_s": r.get("timings_s"), "llm": r.get("llm"), "model": r.get("model"),
            "writing": {k: v.get("source") for k, v in (r.get("writing") or {}).items()},
            "files": sorted(p.name for p in (work / "minutes").glob("MoM_*"))}


# ---------------------------------------------------------------- our own recorded board meeting, scored end to end
# minutes/eval/team_recording/script.md: a 10-minute mock medical board in RO/RU/EN, recorded on 26 September 2026
# twice (one voice reading every part; three of us at a table). Our voices, not hospital audio.
TEAM = [("team1", "team_rec1_cristina_all"), ("team2", "team_rec2_no_cristina")]
TEAM_DATE = "2026-09-26"
DECISIONS = {"D1": r"angiograf|coronarograf|ангиограф", "D2": r"\bhme\b|filtr|фильтр", "D3": r"hygien|igien|гигиен",
             "D4": r"electronic|электрон", "D5": r"pilot|пилот", "D6": r"next meeting|ședinț\w* următoare|следующ"}
TRAPS = {"portable ventilator": r"ventilator portabil|portable ventilator|портативн", "stethoscopes": r"stetoscop|stethoscop|стетоскоп",
         "monthly audit": r"lunar|monthly|ежемесячн"}
ACTIONS = {"A1": (r"angiograf|coronarograf|ангиограф", r"roman", "2026-09-27"), "A2": (r"\binr\b|мно", r"stanislav|stas|станислав", "2026-09-27"),
           "A3": (r"financ|финанс|semn|подпис", r"cristina|кристин", "2026-09-26"), "A4": (r"order|comand|заказ", r"volodymyr|володимир|владимир|vova", "2026-09-27"),
           "A5": (r"\bbed\b|\bpat\b|койк|кроват|place", r"stanislav|stas|станислав", "2026-10-02"), "A6": (r"checklist|chek|чек", r"cagan|ceagan|джан|чаган", "2026-09-30"),
           "A7": (r"form|форм", r"volodymyr|володимир|владимир|vova", "2026-10-03"), "A8": (r"instruc|инструкц", r"cagan|ceagan|джан|чаган", "2026-10-15"),
           "A9": (r"feedback|отзыв|păreri|opini", r"roman", "")}
TERMS = ["supradenivelare de segment ST", "infarct miocardic acut", "ecocardiografie", "fracția de ejecție", "troponina",
         "creatinina", "insuficiență renală", "coronarografie", "substanța de contrast", "варфарин", "МНО", "abord radial",
         "ventilație mecanică", "sepsis", "hemoculturi", "Klebsiella", "meropenem", "HME фильтры", "AVC ischemic", "JCI",
         "hand hygiene compliance"]
PATIENTS = ["ion popa", "galina petrenko", "popa", "petrenko", "попа", "петренко"]


def term_recall(text):
    from asr_llm.clean import _fold
    words = set(_fold(text).split())
    heard = []
    for term in TERMS:
        stems = [w[:5] for w in _fold(term).split()]
        if all(any(w.startswith(st) for w in words) for st in stems):
            heard.append(term)
    return {"heard": len(heard), "of": len(TERMS), "missed": [t for t in TERMS if t not in heard]}


def score_minutes(work):
    import re
    facts_file = next((work / "minutes").glob("*.facts.json"), None)
    if not facts_file:
        return {"error": "no facts.json"}
    facts = [f for f in json.loads(facts_file.read_text(encoding="utf-8"))["facts"] if f.get("status") in ("ok", "confirm")]
    low = lambda f: (f.get("text") or "").lower()
    decisions = [f for f in facts if f["kind"] == "decision"]
    actions = [f for f in facts if f["kind"] == "action"]
    found_d = {k: next((f["id"] for f in decisions if re.search(rx, low(f))), None) for k, rx in DECISIONS.items()}
    traps = {k: [f["id"] for f in decisions if re.search(rx, low(f))] for k, rx in TRAPS.items()}
    acts = {}
    for k, (rx, owner, date) in ACTIONS.items():
        f = next((f for f in actions if re.search(rx, low(f))), None)
        acts[k] = None if f is None else {"id": f["id"], "owner_ok": bool(re.search(owner, (f.get("owner") or "").lower())),
                                         "deadline_ok": (f.get("deadline") or "") == date, "owner": f.get("owner"),
                                         "deadline": f.get("deadline"), "status": f.get("status")}
    everything = " ".join(low(f) + " " + (f.get("owner") or "").lower() for f in facts)
    minutes_text = ""
    for pdf in (work / "minutes").glob("*.pdf"):
        try:
            minutes_text += subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout.lower()
        except FileNotFoundError:   # poppler missing: the facts are still checked
            break
    return {"decisions_found": sum(v is not None for v in found_d.values()), "decisions_of": len(DECISIONS), "decisions": found_d,
            "decision_facts": len(decisions), "trap_errors": sum(bool(v) for v in traps.values()), "traps": traps,
            "actions_found": sum(v is not None for v in acts.values()), "actions_of": len(ACTIONS),
            "owners_right": sum(bool(v and v["owner_ok"]) for v in acts.values()),
            "deadlines_right": sum(bool(v and v["deadline_ok"]) for v in acts.values()), "actions": acts,
            "to_confirm": sum(f.get("status") == "confirm" for f in facts),
            "patient_names_in_minutes": [p for p in PATIENTS if p in everything or p in minutes_text],
            "facts": facts}


def team_recordings():
    root = next((p.parent for p in Path("/kaggle/input").glob("**/team_rec1_cristina_all.m4a")), None)
    if root is None:
        log("team recordings not attached: coflaz/liminal-team-recordings")
        return {}
    out = {}
    for name, stem in TEAM:
        STATE.update(step="team recording", hour=name, note="")
        work = OUT / name
        peak = Peak()
        peak.start()
        try:
            times, segments, session = run_pipeline(root / f"{stem}.m4a", work, "medical", TEAM_DATE)
            peak.running = False
            text = " ".join(s["text"] for s in segments)
            (work / "transcript.txt").write_text(text, encoding="utf-8")
            entry = {"reference": f"{stem}.ref.txt", "reference_window_s": 3600}
            out[name] = {"stages_s": times, "peak_gpu_gb": round(peak.gpu, 1), "asr": asr_scores(segments, entry, root, work),
                         "terms": term_recall(text), "speakers": len({t["speaker"] for t in json.loads(session.read_text())["turns"]}) if session else None,
                         "minutes": minutes_summary(work), "score": score_minutes(work)}
            sc = out[name]["score"]
            log(f"{name}: decisions {sc.get('decisions_found')}/{sc.get('decisions_of')}, traps {sc.get('trap_errors')}, "
                f"actions {sc.get('actions_found')}/{sc.get('actions_of')}, owners {sc.get('owners_right')}, deadlines {sc.get('deadlines_right')}, "
                f"terms {out[name]['terms']['heard']}/{out[name]['terms']['of']}, CER {out[name]['asr'].get('cer')}, {times['total']} s")
        except Exception as e:
            peak.running = False
            out[name] = {"error": repr(e)[:1500], "traceback": traceback.format_exc()[-3000:]}
            log(f"{name}: FAILED {e!r}")
        (OUT / "team.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ---------------------------------------------------------------- main

def find_tests():
    for m in sorted(Path("/kaggle/input").glob("**/manifest.json")):
        return m.parent, json.loads(m.read_text(encoding="utf-8"))
    raise FileNotFoundError("no manifest.json under /kaggle/input: attach coflaz/liminal-hour-tests")


def one_hour(hid, root, entry):
    STATE.update(step="hour", hour=hid, note="")
    work = OUT / hid
    peak = Peak()
    peak.start()
    try:
        times, segments, session = run_pipeline(root / entry["audio"], work, MEETING_TYPE.get(hid, "administrative"))
    finally:
        peak.running = False
    result = {"stages_s": times, "total_min": round(times["total"] / 60, 1),
              "under_15_min": times["total"] < 15 * 60, "peak_gpu_gb": round(peak.gpu, 1), "peak_ram_gb": round(peak.ram, 1),
              "segments": len(segments), "languages": entry.get("languages"), "asr": asr_scores(segments, entry, root, work),
              "minutes": minutes_summary(work)}
    if entry.get("rttm") and session:
        result["diarization"] = der_score(session, root / entry["rttm"])
    for p in (work / "diarization").glob("*.wav") if (work / "diarization").exists() else []:
        p.unlink()   # keep the output small; the transcript, turns and minutes stay
    return result


def main():
    threading.Thread(target=heartbeat, daemon=True).start()
    report = {"asr_fetch": ASR_FETCH, "asr_env": ASR_ENV, "minutes_model": MINUTES_MODEL, "cmds": CMDS, "hours": {}}
    try:
        timed("clone", clone)
        timed("python packages and Whisper weights", install_python)
        timed("TeX", install_tex)
        timed("Ollama and model", install_ollama)
        root, manifest = find_tests()
        entries = {h["id"]: h for h in manifest["hours"] if h.get("status") == "ok"}
        todo = [h for h in HOURS if h in entries]
        log(f"hours available: {todo}; missing: {[h for h in HOURS if h not in entries]}")
        if not todo:
            raise RuntimeError("the test set has no usable hour")

        STATE["step"] = "smoke test"
        clip = Path("/tmp/smoke.flac")
        sh(f"ffmpeg -nostdin -loglevel error -y -i '{root / entries[todo[0]]['audio']}' -t 180 '{clip}'")
        smoke, _, _ = run_pipeline(clip, OUT / "smoke", MEETING_TYPE.get(todo[0], "administrative"))
        report["smoke_s"] = smoke
        log(f"smoke test passed: {smoke}")
        STATE["done"] += 1
        report["team"] = team_recordings()   # short and the most telling: before the hours
        STATE["done"] += 1

        for hid in todo:
            try:
                report["hours"][hid] = one_hour(hid, root, entries[hid])
                r = report["hours"][hid]
                log(f"{hid}: {r['total_min']} min total, stages {r['stages_s']}, CER {r['asr'].get('cer')}, "
                    f"{'UNDER' if r['under_15_min'] else 'OVER'} 15 min")
            except Exception as e:
                report["hours"][hid] = {"error": repr(e)[:1500], "traceback": traceback.format_exc()[-3000:]}
                log(f"{hid}: FAILED {e!r}")
            STATE["done"] += 1
            STATE["progress"] += 1
            (OUT / "report.json").write_text(json.dumps({**report, "setup_s": STATE["setup_s"]}, ensure_ascii=False, indent=1))
    except Exception as e:
        report["failure"] = {"step": STATE["step"], "error": repr(e)[:1500], "traceback": traceback.format_exc()[-3000:]}
        log(f"FAILED at {STATE['step']}: {e!r}")
    report["setup_s"] = STATE["setup_s"]
    report["warnings"] = STATE["warnings"]
    report["minutes_total"] = round((time.time() - T0) / 60, 1)
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))
    log("report: " + json.dumps({h: (r.get("total_min"), r.get("asr", {}).get("cer")) if "error" not in r else "failed"
                                  for h, r in report["hours"].items()}))


if __name__ == "__main__":
    main()
