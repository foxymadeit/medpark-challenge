"""Session output: JSON for the pipeline, RTTM for scoring, CSV for people.

Every turn carries the three values the team asked for: who spoke, when they
started and when they stopped. Clock times come from the machine's local
clock (no network time needed); offsets are seconds from the session start.
"""

import csv
import json
import os
from datetime import datetime
from pathlib import Path


def clock(epoch: float) -> str:
    return datetime.fromtimestamp(epoch).strftime("%H:%M:%S.%f")[:-3]


def consecutive_labels(turns, names: dict) -> dict:
    """Unnamed speakers become Speaker 1, 2, 3... in order of first appearance.
    Merges during a run leave gaps in the raw ids (1, 2, 4, 5); a finished
    recording has no live audience that saw those numbers, so close the gaps."""
    out, n = {}, 0
    for t in sorted(turns, key=lambda t: t.start):
        if t.speaker in out:
            continue
        name = names.get(t.speaker, f"Speaker {t.speaker}")
        if name.startswith("Speaker "):
            n += 1
            name = f"Speaker {n}"
        out[t.speaker] = name
    return out


def build_session(turns, labels: dict, *, session_start: float, source: str, model: str) -> dict:
    rows, speakers = [], {}
    for t in turns:
        name = labels.get(t.speaker, f"Speaker {t.speaker}")
        rows.append({
            "speaker": name,
            "start_clock": clock(session_start + t.start),
            "end_clock": clock(session_start + t.end),
            "start": round(t.start, 3),
            "end": round(t.end, 3),
        })
        s = speakers.setdefault(name, {"talk_time": 0.0, "turns": 0})
        s["talk_time"] = round(s["talk_time"] + t.duration, 3)
        s["turns"] += 1
    return {
        "session_start": datetime.fromtimestamp(session_start).isoformat(timespec="milliseconds"),
        "source": source,
        "model": model,
        "speakers": speakers,
        "turns": rows,
    }


def summary(session: dict) -> str:
    lines = [f"Session started {session['session_start']}  ({session['source']})", ""]
    width = max((len(t["speaker"]) for t in session["turns"]), default=0)
    for t in session["turns"]:
        dur = t["end"] - t["start"]
        lines.append(f"{t['speaker']:<{width}}  {t['start_clock']} → {t['end_clock']}  ({dur:.2f} s)")
    lines += ["", "Talk time:"]
    for name, s in session["speakers"].items():
        lines.append(f"  {name:<{width}}  {s['talk_time']:8.1f} s in {s['turns']} turns")
    return "\n".join(lines)


def write_all(out_dir, session: dict, uri: str) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    os.chmod(out, 0o700)  # who spoke when in a hospital meeting: owner only
    paths = [out / f"{uri}.json", out / f"{uri}.rttm", out / f"{uri}.csv"]
    paths[0].write_text(json.dumps(session, indent=2, ensure_ascii=False))
    paths[1].write_text("".join(
        f"SPEAKER {uri} 1 {t['start']:.3f} {t['end'] - t['start']:.3f} <NA> <NA> "
        f"{t['speaker'].replace(' ', '_')} <NA> <NA>\n" for t in session["turns"]))
    with paths[2].open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["speaker", "start", "end", "start_s", "end_s", "duration_s"])
        for t in session["turns"]:
            w.writerow([t["speaker"], t["start_clock"], t["end_clock"],
                        t["start"], t["end"], round(t["end"] - t["start"], 3)])
    for p in paths:
        os.chmod(p, 0o600)
    return paths
