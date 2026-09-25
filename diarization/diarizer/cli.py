"""diarizer: who spoke when, fully offline.

  diarizer live   [--speakers N] [--out DIR]      listen to the mic, label voices as they appear
  diarizer file   MEETING.m4a [--speakers N]      same engine over a recording
  diarizer enroll NAME [--file CLIP] [--seconds 20]
  diarizer models fetch [--all]                   one-time download (the only networked command)
"""

import argparse
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from . import models
from .audio import load, mic_blocks
from .engine import Labeler, Observer, StreamingDiarizer
from .export import build_session, clock, consecutive_labels, summary, write_all
from .neural import SR, Embedder, Segmenter
from .timeline import Timeline
from .tracker import SpeakerTracker
from .voices import load_voices, save_voice, voice_embeddings

DEFAULT_OUT = Path("sessions")


def build(args) -> StreamingDiarizer:
    th = dict(models.THRESHOLDS[args.embedder])
    for k in ("assign", "new", "merge"):
        if getattr(args, k) is not None:
            th[k] = getattr(args, k)
    seg = Segmenter(models.model_path(models.SEGMENTATION), args.threads)
    emb = Embedder(models.embedder_path(args.embedder), args.threads)
    tracker = SpeakerTracker(assign=th["assign"], new=th["new"], max_speakers=args.speakers)
    if not args.no_voices:
        for name, embs in load_voices(args.embedder).items():
            tracker.enroll(name, embs)
            print(f"enrolled voice: {name}", file=sys.stderr)
    observer = Observer(seg, emb, window=args.window, step=args.step, latency=args.latency)
    return StreamingDiarizer(observer, Labeler(tracker, Timeline(), merge=th["merge"]))


def finalize(d: StreamingDiarizer, turns, start: float, source: str, args, renumber=False) -> None:
    labels = {i: d.label(i) for i in {t.speaker for t in turns}}
    if renumber:
        labels = consecutive_labels(turns, labels)
    session = build_session(turns, labels, session_start=start, source=source, model=args.embedder)
    print("\n" + summary(session))
    uri = datetime.fromtimestamp(start).strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else DEFAULT_OUT / uri
    for p in write_all(out, session, uri=uri):
        print(f"wrote {p}")


def show(event, d: StreamingDiarizer, start: float) -> None:
    if event[0] == "start":
        print(f"{clock(start + event[2])}  ▶ {d.label(event[1])}", flush=True)
    elif event[0] == "end":
        t = event[1]
        print(f"{clock(start + t.end)}  ■ {d.label(t.speaker)}  {clock(start + t.start)} → "
              f"{clock(start + t.end)}  ({t.duration:.2f} s)", flush=True)
    elif event[0] == "merge":
        for old, new in event[1].items():
            print(f"              ↺ Speaker {old} is the same voice as {d.label(new)}, merged", flush=True)


def cmd_live(args) -> None:
    d = build(args)
    stop = threading.Event()
    threading.Thread(target=lambda: (sys.stdin.readline(), stop.set()), daemon=True).start()
    print("Listening. Press Enter (or Ctrl+C) to finish.", file=sys.stderr)
    start, heard = time.time(), 0
    try:
        for block, start in mic_blocks(device=args.device):
            heard += len(block)
            for e in d.feed(block):
                show(e, d, start)
            if stop.is_set() or (args.duration and heard >= args.duration * SR):
                break
    except KeyboardInterrupt:
        pass
    finalize(d, d.finish(), start, "microphone", args)


def cmd_file(args) -> None:
    path = Path(args.path)
    audio = load(path)
    start = _start_time(args.start_time, path, len(audio) / SR)
    d = build(args)
    t0 = time.perf_counter()
    for i in range(0, len(audio), SR):
        for e in d.feed(audio[i:i + SR]):
            if args.verbose:
                show(e, d, start)
    turns = d.finish()
    took = time.perf_counter() - t0
    print(f"processed {len(audio) / SR:.0f} s of audio in {took:.1f} s "
          f"({took / max(len(audio) / SR, 1e-9):.3f}x real time)", file=sys.stderr)
    finalize(d, turns, start, str(path), args, renumber=True)


def cmd_enroll(args) -> None:
    if args.file:
        audio = load(args.file)
    else:
        print(f"Recording {args.seconds:.0f} s. Talk normally, in any language.", file=sys.stderr)
        chunks, n = [], 0
        for block, _ in mic_blocks(device=args.device):
            chunks.append(block)
            n += len(block)
            if n >= args.seconds * SR:
                break
        audio = np.concatenate(chunks)
    seg = Segmenter(models.model_path(models.SEGMENTATION), args.threads)
    emb = Embedder(models.embedder_path(args.embedder), args.threads)
    embs = voice_embeddings(audio, seg, emb)
    if not embs:
        sys.exit("heard less than 3 s of speech; try again closer to the mic")
    path = save_voice(args.name, args.embedder, embs)
    print(f"saved {len(embs)} voiceprints for {args.name} to {path}")


def cmd_models(args) -> None:
    models.fetch(tuple(models.EMBEDDERS) if args.all else (models.DEFAULT_EMBEDDER,))


def _start_time(text, path: Path, duration: float) -> float:
    if text:
        today = datetime.now().date().isoformat()
        return datetime.fromisoformat(text if "T" in text or "-" in text else f"{today}T{text}").timestamp()
    return path.stat().st_mtime - duration  # recordings usually finish when the file is written


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="diarizer", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def engine_args(p):
        p.add_argument("--speakers", type=int, default=0, help="max speakers if known (0 = figure it out)")
        p.add_argument("--embedder", default=models.DEFAULT_EMBEDDER, choices=list(models.EMBEDDERS))
        p.add_argument("--latency", type=float, default=1.0, help="seconds of look-ahead before a label is final")
        p.add_argument("--step", type=float, default=0.5)
        p.add_argument("--window", type=float, default=5.0)
        p.add_argument("--assign", type=float, help="override the match threshold")
        p.add_argument("--new", type=float, help="override the new-speaker threshold")
        p.add_argument("--merge", type=float, help="override the merge threshold")
        p.add_argument("--no-voices", action="store_true", help="ignore enrolled voices")
        p.add_argument("--threads", type=int, default=2)
        p.add_argument("--out", help="output folder (default sessions/<start time>)")

    p = sub.add_parser("live", help="label speakers from the microphone")
    engine_args(p)
    p.add_argument("--device", help="input device name or index")
    p.add_argument("--duration", type=float, help="stop after this many seconds")
    p.set_defaults(fn=cmd_live)

    p = sub.add_parser("file", help="label speakers in a recording")
    p.add_argument("path")
    engine_args(p)
    p.add_argument("--start-time", help="wall clock of the recording start, e.g. 14:02:00")
    p.add_argument("-v", "--verbose", action="store_true", help="print turns as they are found")
    p.set_defaults(fn=cmd_file)

    p = sub.add_parser("enroll", help="save a person's voiceprint")
    p.add_argument("name")
    p.add_argument("--file", help="use a clip instead of the mic")
    p.add_argument("--seconds", type=float, default=20.0)
    p.add_argument("--embedder", default=models.DEFAULT_EMBEDDER, choices=list(models.EMBEDDERS))
    p.add_argument("--device")
    p.add_argument("--threads", type=int, default=2)
    p.set_defaults(fn=cmd_enroll)

    p = sub.add_parser("models", help="download models (needs internet once)")
    p.add_argument("action", choices=["fetch"])
    p.add_argument("--all", action="store_true", help="also fetch the comparison embedders")
    p.set_defaults(fn=cmd_models)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
