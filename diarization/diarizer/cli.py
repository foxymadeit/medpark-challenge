"""diarizer: who spoke when, fully offline.

  diarizer live   [--speakers N] [--out DIR]      listen to the mic, label voices as they appear
  diarizer file   MEETING.m4a [--speakers N]      same engine over a recording
  diarizer enroll NAME [--file CLIP] [--seconds 20]
  diarizer attach SESSION.json WHISPER.json       put speaker names on a Whisper transcript
  diarizer models fetch [--all]                   one-time download (the only networked command)
"""

import argparse
import itertools
import json
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from . import models
from .attach import attach, load_segments
from .audio import load, mic_blocks
from .backend import Backend
from .engine import Labeler, Observer, StreamingDiarizer
from .export import build_session, clock, consecutive_labels, summary, write_all
from .neural import SR, Embedder, Segmenter
from .passages import PASSAGES
from .profiles import PROFILES, pick, speech_to_background_db
from . import ui
from .timeline import Timeline
from .tracker import SpeakerTracker
from .voices import closest_voice, load_voices, save_voice, voice_embeddings

DEFAULT_OUT = Path("sessions")
CHECK_S = 10  # seconds of room audio the live microphone check listens to


def choose_profile(args, audio, quiet=False):
    """(profile, dB). --mic close/far as given; auto measures speech over the room's background."""
    if args.mic != "auto":
        return args.mic, None
    db = speech_to_background_db(audio, Segmenter(models.model_path(PROFILES["far"]["segmentation"]), args.threads))
    profile = pick(db)
    if not quiet:
        print(f"microphone check: speech {db:.1f} dB over the room -> {profile} profile", file=sys.stderr)
    return profile, db


def build(args, profile="far", quiet=False) -> StreamingDiarizer:
    p = PROFILES[profile]
    default = args.embedder == models.DEFAULT_EMBEDDER  # profile thresholds are tuned for the default embedder
    th = {k: p[k] for k in ("assign", "new", "merge")} if default else dict(models.THRESHOLDS[args.embedder])
    for k in ("assign", "new", "merge"):
        if getattr(args, k) is not None:
            th[k] = getattr(args, k)
    seg_file = p["segmentation"]
    if not (models.MODELS_DIR / seg_file).is_file():
        if not quiet:
            print(f"{seg_file} is missing; using the stock segmentation model", file=sys.stderr)
        seg_file = PROFILES["far"]["segmentation"]
    backend = _backend(args) if p["backend"] else None
    seg = Segmenter(models.model_path(seg_file), args.threads)
    emb = Embedder(models.embedder_path(args.embedder), args.threads, backend=backend)
    tracker = SpeakerTracker(assign=th["assign"], new=th["new"], max_speakers=args.speakers)
    if not args.no_voices:
        for name, embs in load_voices(args.embedder).items():  # stored raw; project like live audio
            tracker.enroll(name, list(backend(np.asarray(embs))) if backend else embs)
            if not quiet:
                print(f"enrolled voice: {name}", file=sys.stderr)
    observer = Observer(seg, emb, window=args.window, step=args.step, latency=args.latency)
    return StreamingDiarizer(observer, Labeler(tracker, Timeline(), merge=th["merge"]))


def finalize(d: StreamingDiarizer, turns, start: float, source: str, args, renumber=False, console=None) -> None:
    labels = {i: d.label(i) for i in {t.speaker for t in turns}}
    if renumber:
        labels = consecutive_labels(turns, labels)
    session = build_session(turns, labels, session_start=start, source=source, model=args.embedder)
    uri = datetime.fromtimestamp(start).strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else DEFAULT_OUT / uri
    paths = write_all(out, session, uri=uri)
    if console is not None:
        ui.summary(console, session, paths)
        return
    print("\n" + summary(session))
    for p in paths:
        print(f"wrote {p}")


def pretty(args) -> bool:
    """The animated screen, unless --plain or the output is not a terminal."""
    return not getattr(args, "plain", False) and sys.stdout.isatty()


def stdin_lines() -> queue.Queue:
    """Every line typed, in order: Enter ends a phase, names are typed in."""
    q: queue.Queue = queue.Queue()
    threading.Thread(target=lambda: [q.put(x.rstrip("\n")) for x in iter(sys.stdin.readline, "")], daemon=True).start()
    return q


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
    if pretty(args):
        return live_screen(args)
    blocks, first = mic_blocks(device=args.device), []
    start = time.time()
    if args.mic == "auto":
        print("Listening to the room for 10 s to pick the microphone profile...", file=sys.stderr)
        for block, start in blocks:
            first.append(block)
            if sum(map(len, first)) >= CHECK_S * SR:
                break
    d = build(args, choose_profile(args, np.concatenate(first))[0] if first else args.mic)
    stop = threading.Event()
    threading.Thread(target=lambda: (sys.stdin.readline(), stop.set()), daemon=True).start()
    print("Listening. Press Enter (or Ctrl+C) to finish.", file=sys.stderr)
    heard = 0
    try:
        for block, start in itertools.chain(((b, start) for b in first), blocks):
            heard += len(block)
            for e in d.feed(block):
                show(e, d, start)
            if stop.is_set() or (args.duration and heard >= args.duration * SR):
                break
    except KeyboardInterrupt:
        pass
    finalize(d, d.finish(), start, "microphone", args)


INTRO_HINT = "INTRODUCTIONS · EACH PERSON: NAME AND ROLE · [ENTER] WHEN EVERYONE HAS SPOKEN"
LIVE_HINT = "[ENTER] FINISH   [CTRL+C] STOP"


def live_screen(args) -> None:
    """Room check and introductions, optional names, then the meeting."""
    from rich.console import Console
    from rich.live import Live
    console, lines, blocks = Console(), stdin_lines(), mic_blocks(device=args.device)
    holder: dict = {}
    screen = ui.Screen(lambda i: holder["d"].label(i) if "d" in holder else f"Speaker {i}", console)
    clock_of = {"start": time.time()}
    heard = 0

    def feed(block):
        nonlocal heard
        heard += len(block)
        screen.audio(block)
        for e in holder["d"].feed(block):
            screen.event(e, lambda t: clock(clock_of["start"] + t))

    def pump() -> None:  # until Enter, --duration or Ctrl+C
        for block, clock_of["start"] in blocks:
            feed(block)
            if not lines.empty() or (args.duration and heard >= args.duration * SR):
                return

    intro = not args.no_intro
    try:
        with Live(screen, console=console, refresh_per_second=12, transient=True):
            screen.phase, screen.hint = ("INTRO", INTRO_HINT) if intro else ("LIVE", LIVE_HINT)
            profile, db, first = args.mic, None, []
            if args.mic == "auto":
                for block, clock_of["start"] in blocks:
                    first.append(block)
                    screen.audio(block)
                    screen.status = f"LISTENING TO THE ROOM {sum(map(len, first)) / SR:4.1f} / {CHECK_S} s"
                    if sum(map(len, first)) >= CHECK_S * SR:
                        break
                profile, db = choose_profile(args, np.concatenate(first), quiet=True)
            holder["d"] = build(args, profile, quiet=True)
            screen.status = f"{profile.upper()} MIC" + (f" · {db:.0f} dB" if db is not None and db == db else "")
            for block in first:
                feed(block)
            if intro:
                pump()
                if not lines.empty():
                    lines.get()  # the Enter that ended the introductions
        if intro and screen.voices() and not (args.duration and heard >= args.duration * SR):
            name_voices(console, lines, holder["d"], screen)
        if not (args.duration and heard >= args.duration * SR):
            while not lines.empty():  # stray Enters from naming must not end the meeting
                lines.get()
            with Live(screen, console=console, refresh_per_second=12, transient=True):
                screen.phase, screen.hint = "LIVE", LIVE_HINT
                pump()
    except KeyboardInterrupt:
        pass
    if "d" in holder:
        finalize(holder["d"], holder["d"].finish(), clock_of["start"], "microphone", args, console=console)


def name_voices(console, lines, d, screen) -> None:
    from rich.text import Text
    console.print(Text(" WHO IS WHO?  type a name and press ENTER, or just ENTER to keep the number", ui.BRIGHT))
    for sid in screen.voices():
        console.print(Text(f" {d.label(sid).upper():<14} talked {ui.mmss(screen.talk.get(sid, 0))}  → name: ", ui.BASE), end="")
        name = lines.get().strip()
        if name:
            d.rename(sid, name)


def cmd_file(args) -> None:
    if pretty(args):
        return file_screen(args)
    path = Path(args.path)
    audio = load(path)
    start = _start_time(args.start_time, path, len(audio) / SR)
    d = build(args, choose_profile(args, audio)[0])
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


def file_screen(args) -> None:
    from rich.console import Console
    from rich.live import Live
    console, path = Console(), Path(args.path)
    audio = load(path)
    start = _start_time(args.start_time, path, len(audio) / SR)
    holder: dict = {}
    screen = ui.Screen(lambda i: holder["d"].label(i) if "d" in holder else f"Speaker {i}", console, title="FILE")
    screen.phase, screen.hint, screen.progress = "FILE", path.name.upper(), 0.0
    with Live(screen, console=console, refresh_per_second=12, transient=True):
        screen.status = "LISTENING TO THE ROOM"
        profile, db = choose_profile(args, audio, quiet=True)
        holder["d"] = d = build(args, profile, quiet=True)
        mic = f"{profile.upper()} MIC" + (f" · {db:.0f} dB" if db is not None and db == db else "")
        t0 = time.perf_counter()
        for i in range(0, len(audio), SR):
            screen.audio(audio[i:i + SR])
            for e in d.feed(audio[i:i + SR]):
                screen.event(e, lambda t: clock(start + t))
            done = min(1.0, (i + SR) / len(audio))
            took = time.perf_counter() - t0
            screen.progress = done
            screen.status = f"{mic} · {took / max(done * len(audio) / SR, 1e-9):.2f}x REAL TIME · ETA {ui.mmss(took / done - took)}"
        turns = d.finish()
    took = time.perf_counter() - t0
    console.print(ui.Text(f" processed {ui.mmss(len(audio) / SR)} of audio in {ui.mmss(took)} "
                          f"({took / max(len(audio) / SR, 1e-9):.2f}x real time) · {mic}", ui.BASE))
    finalize(d, turns, start, str(path), args, renumber=True, console=console)


def cmd_enroll(args) -> None:
    if args.file:
        audio = load(args.file)
    elif pretty(args):
        audio = enroll_screen(args)
    else:
        print(f"Recording {args.seconds:.0f} s. Read this aloud at your normal pace:\n\n"
              f"{PASSAGES[args.language]}\n", file=sys.stderr)
        chunks, n = [], 0
        for block, _ in mic_blocks(device=args.device):
            chunks.append(block)
            n += len(block)
            if n >= args.seconds * SR:
                break
        audio = np.concatenate(chunks)
    seg = Segmenter(models.model_path(models.SEGMENTATION), args.threads)
    emb = Embedder(models.embedder_path(args.embedder), args.threads)  # raw; each profile projects at load
    embs = voice_embeddings(audio, seg, emb)
    if not embs:
        sys.exit("heard less than 3 s of speech; try again closer to the mic")
    if len(embs) < 5:
        print(f"only {3 * len(embs)} s of clear speech; reading the whole passage gives a steadier voiceprint",
              file=sys.stderr)
    other, sim = closest_voice(embs, load_voices(args.embedder), skip=args.name)
    if sim >= 0.70:
        print(f"warning: this voice is very close to {other} ({sim:.2f}); they may be mixed up in meetings. "
              "Recording again in a quiet room usually helps.", file=sys.stderr)
    path = save_voice(args.name, args.embedder, embs, add=args.add)
    print(f"saved {len(embs)} voiceprints for {args.name} to {path}")


def enroll_screen(args):
    from rich.console import Console
    from rich.live import Live
    console = Console()
    screen = ui.Screen(lambda i: "", console, title=f"ENROLL {args.name.upper()}")
    screen.phase, screen.progress, screen.passage = "REC", 0.0, PASSAGES[args.language]
    screen.hint = "READ THE TEXT ABOVE AT YOUR NORMAL PACE"
    chunks, n, loud = [], 0, 0
    with Live(screen, console=console, refresh_per_second=12, transient=True):
        for block, _ in mic_blocks(device=args.device):
            chunks.append(block)
            n += len(block)
            screen.audio(block)
            loud += len(block) if ui.level_db(block) > -45 else 0
            screen.progress = min(1.0, n / (args.seconds * SR))
            screen.status = f"VOICE {loud / SR:4.1f} s · {max(0, args.seconds - n / SR):4.1f} s LEFT"
            if n >= args.seconds * SR:
                break
    return np.concatenate(chunks)


def cmd_attach(args) -> None:
    session = json.loads(Path(args.session).read_text())
    if "turns" not in session:
        sys.exit(f"{args.session} has no turns; pass the .json that diarizer file/live wrote")
    try:
        segments = load_segments(json.loads(Path(args.transcript).read_text()))
    except (ValueError, KeyError, TypeError) as e:
        sys.exit(f"could not read {args.transcript}: {e}")
    t0 = datetime.fromisoformat(session["session_start"]).timestamp()
    lines = [{**x, "start_clock": clock(t0 + x["start"]), "end_clock": clock(t0 + x["end"])}
             for x in attach(segments, session["turns"], max_gap=args.max_gap)]
    for x in lines:
        print(f"{x['start_clock']}  {x['speaker'] or '?':<12}  {_printable(x['text'])}")
    out = Path(args.out) if args.out else Path(args.session).with_suffix(".transcript.json")
    out.write_text(json.dumps({"session_start": session["session_start"], "lines": lines}, indent=2, ensure_ascii=False))
    print(f"wrote {out}")


def _printable(text: str) -> str:
    """Transcript text without control characters, so a file cannot drive the terminal."""
    return "".join(c for c in text if c == "\t" or (ord(c) >= 32 and ord(c) != 127))


def cmd_models(args) -> None:
    models.fetch(tuple(models.EMBEDDERS) if args.all else (models.DEFAULT_EMBEDDER,))


def _backend(args):
    path = None if getattr(args, "no_backend", False) else models.backend_path(args.embedder)
    return Backend.load(path) if path else None


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
        p.add_argument("--mic", default="auto", choices=["auto", "close", "far"],
                       help="close: speakers near the mic; far: one mic on the table; auto: measure it")
        p.add_argument("--embedder", default=models.DEFAULT_EMBEDDER, choices=list(models.EMBEDDERS))
        p.add_argument("--latency", type=float, default=1.0, help="seconds of look-ahead before a label is final")
        p.add_argument("--step", type=float, default=0.5)
        p.add_argument("--window", type=float, default=5.0)
        p.add_argument("--assign", type=float, help="override the match threshold")
        p.add_argument("--new", type=float, help="override the new-speaker threshold")
        p.add_argument("--merge", type=float, help="override the merge threshold")
        p.add_argument("--no-voices", action="store_true", help="ignore enrolled voices")
        p.add_argument("--no-backend", action="store_true", help="skip the trained embedding projection")
        p.add_argument("--threads", type=int, default=2)
        p.add_argument("--out", help="output folder (default sessions/<start time>)")
        p.add_argument("--plain", action="store_true", help="line-by-line output instead of the live screen")

    p = sub.add_parser("live", help="label speakers from the microphone")
    engine_args(p)
    p.add_argument("--device", help="input device name or index")
    p.add_argument("--duration", type=float, help="stop after this many seconds")
    p.add_argument("--no-intro", action="store_true", help="skip the introductions round and naming")
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
    p.add_argument("--seconds", type=float, default=28.0)
    p.add_argument("--language", default="en", choices=list(PASSAGES), help="passage to read (en, ro, ru)")
    p.add_argument("--add", action="store_true", help="keep existing voiceprints, e.g. a second language")
    p.add_argument("--embedder", default=models.DEFAULT_EMBEDDER, choices=list(models.EMBEDDERS))
    p.add_argument("--device")
    p.add_argument("--threads", type=int, default=2)
    p.add_argument("--no-backend", action="store_true")
    p.add_argument("--plain", action="store_true", help="plain text instead of the recording screen")
    p.set_defaults(fn=cmd_enroll)

    p = sub.add_parser("attach", help="put speaker names on a Whisper transcript")
    p.add_argument("session", help="the .json written by diarizer file or live")
    p.add_argument("transcript", help="Whisper JSON: openai-whisper, faster-whisper list, or whisper.cpp -oj")
    p.add_argument("--max-gap", type=float, default=2.0, help="seconds to reach for the nearest turn when none overlaps")
    p.add_argument("--out", help="output file (default <session>.transcript.json)")
    p.set_defaults(fn=cmd_attach)

    p = sub.add_parser("models", help="download models (needs internet once)")
    p.add_argument("action", choices=["fetch"])
    p.add_argument("--all", action="store_true", help="also fetch the comparison embedders")
    p.set_defaults(fn=cmd_models)

    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
