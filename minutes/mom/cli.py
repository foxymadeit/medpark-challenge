"""mom: minutes from a meeting transcript, fully offline.

  mom purge DIR [--days 30]   delete minutes files older than the retention period
  mom report TRANSCRIPT [--session diarizer.json] [--type medical|executive|administrative]
             [--date 2026-09-26] [--start 14:10] [--number 14] [--place ...]
             [--chair ...] [--secretary ...] [--lang ro,ru,en] [--out DIR]
             [--model qwen3:8b] [--url http://127.0.0.1:11434]
"""

import argparse
import re
import sys
import time
from pathlib import Path

from .llm import DEFAULT_MODEL, DEFAULT_URL, LocalLLM
from .pipeline import run
from .schemas import LANGS, MEETING_TYPES, Meeting


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="mom", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("report", help="write the minutes for one meeting")
    p.add_argument("transcript")
    p.add_argument("--session", help="the diarizer's session JSON, for speakers")
    p.add_argument("--type", default="medical", choices=MEETING_TYPES)
    p.add_argument("--date", default="", help="meeting date, YYYY-MM-DD (default today)")
    p.add_argument("--start", default="", help="clock time the recording started, HH:MM")
    p.add_argument("--number", default="", help="minutes number")
    p.add_argument("--place", default="")
    p.add_argument("--chair", default="")
    p.add_argument("--secretary", default="")
    p.add_argument("--lang", default=",".join(LANGS), help="comma-separated: ro,ru,en")
    p.add_argument("--out", default="out")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--url", default=DEFAULT_URL, help="local model server (loopback only)")
    p.add_argument("--think", choices=["off", "low", "medium", "high"], default=None)
    q = sub.add_parser("purge", help="delete minutes files older than the retention period")
    q.add_argument("dir")
    q.add_argument("--days", type=float, default=30)
    a = ap.parse_args(argv)
    if a.cmd == "purge":
        print(f"deleted {purge(Path(a.dir), a.days)} files older than {a.days:g} days")
        return

    if a.date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        sys.exit("--date must look like 2026-09-26")
    if a.start and not re.fullmatch(r"\d{1,2}:\d{2}", a.start):
        sys.exit("--start must look like 14:10")
    langs = tuple(x for x in a.lang.split(",") if x)
    if not langs or any(x not in LANGS for x in langs):
        sys.exit(f"--lang takes {', '.join(LANGS)}")
    think = None if a.think is None else (False if a.think == "off" else a.think)
    meeting = Meeting(type=a.type, number=a.number, date=a.date, start=a.start, place=a.place,
                      chair=a.chair, secretary=a.secretary)
    result = run(a.transcript, a.out, LocalLLM(a.model, a.url), meeting, langs, a.session, think)
    c = result["checks"]
    print(f"{c['ok']} facts checked against the transcript, {c['confirm']} to confirm, {c['dropped']} dropped")
    for lang, f in result["files"].items():
        print(f"  {lang}: {f['pdf']}\n      {f['docx']}")
    print("time: " + ", ".join(f"{k} {v}s" for k, v in result["timings_s"].items()))
    print("report: " + result["facts"].replace(".facts.json", ".report.json"))


def purge(folder: Path, days: float) -> int:
    """GDPR Art. 5(1)(e): nothing is kept longer than the hospital decides.
    Only our own outputs (MoM_*) directly in the folder; never follows links."""
    cutoff, n = time.time() - days * 86400, 0
    for f in folder.glob("MoM_*"):
        if f.is_file() and not f.is_symlink() and f.stat().st_mtime < cutoff:
            f.unlink()
            n += 1
    return n


if __name__ == "__main__":
    main()
