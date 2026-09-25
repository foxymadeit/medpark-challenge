"""Score the diarizer against human-labelled meetings.

  python -m eval.run_eval observe  --meetings ES2011a IS1008a --embedder campp
  python -m eval.run_eval score    --meetings ES2011a IS1008a --embedder campp --assign 0.55
  python -m eval.run_eval sweep    --meetings ES2011a IS1008a --embedder campp

`observe` runs the neural models once per meeting and caches what they saw.
`score` and `sweep` replay that cache through the tracker, so trying a new
threshold takes seconds. Audio + RTTM + UEM live in data/ami/ (AMI corpus,
CC-BY 4.0; RTTM/UEM from github.com/pyannote/AMI-diarization-setup).
"""

import argparse
import dataclasses
import itertools
import pickle
import time
from pathlib import Path

from diarizer import models
from diarizer.audio import load
from diarizer.backend import Backend
from diarizer.engine import Labeler, Observer
from diarizer.neural import SR, Embedder, Segmenter
from diarizer.timeline import Timeline
from diarizer.tracker import SpeakerTracker

from .der import der, read_rttm

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "ami"
CACHE = Path(__file__).resolve().parent / "cache"


def cache_path(meeting, kind, embedder, latency):
    return CACHE / f"{meeting}.{kind}.{embedder}.L{latency}.pkl"


def observe(meeting, kind, embedder, latency, threads=2):
    out = cache_path(meeting, kind, embedder, latency)
    if out.exists():
        return pickle.loads(out.read_bytes())
    audio = load(audio_path(meeting, kind))
    obs = Observer(Segmenter(models.model_path(models.SEGMENTATION), threads),
                   Embedder(models.embedder_path(embedder), threads), latency=latency)
    t = time.perf_counter()
    seen = []
    for i in range(0, len(audio), SR):
        seen += obs.feed(audio[i:i + SR])
    seen += obs.flush()
    rtf = (time.perf_counter() - t) / (len(audio) / SR)
    CACHE.mkdir(exist_ok=True)
    out.write_bytes(pickle.dumps({"obs": seen, "rtf": rtf, "dur": len(audio) / SR}))
    print(f"  observed {meeting} {kind} {embedder}: RTF {rtf:.3f}")
    return pickle.loads(out.read_bytes())


def audio_path(meeting, kind):
    flac = DATA / f"{meeting}.{kind}.flac"
    return flac if flac.exists() else DATA / f"{meeting}.{kind}.wav"


def crop(segs, uem):
    a, b = uem
    return [(s, max(x, a), min(y, b)) for s, x, y in segs if y > a and x < b]


def read_uem(meeting):
    f = (DATA / f"{meeting}.uem").read_text().split()
    return float(f[2]), float(f[3])


def project(cached, backend):
    """Replay cached observations through a trained backend (raw embeddings stay cached)."""
    if backend is None:
        return cached
    obs = [dataclasses.replace(o, embs=list(backend(o.embs)) if o.embs else []) for o in cached["obs"]]
    return {**cached, "obs": obs}


def score(cached, meeting, **params):
    tracker_keys = ("assign", "new", "anchor", "max_speakers")
    tracker = SpeakerTracker(**{k: v for k, v in params.items() if k in tracker_keys})
    lab = Labeler(tracker, Timeline(min_gap=params.get("min_gap", 0.5), min_dur=params.get("min_dur", 0.3)),
                  merge=params.get("merge", 0.75), final=params.get("final", "refine"),
                  cluster=params.get("cluster", 0.5))
    for o in cached["obs"]:
        lab.apply(o)
    hyp = [(str(t.speaker), t.start, t.end) for t in lab.finish()]
    uem = read_uem(meeting)
    return der(crop(read_rttm(DATA / f"{meeting}.rttm"), uem), crop(hyp, uem))


def report(rows, label=""):
    tot = sum(r["dur"] for r in rows)
    w = lambda k: sum(r[k] * r["dur"] for r in rows) / tot  # noqa: E731
    for r in rows:
        print(f"  {r['meeting']:8s} DER {r['der']:.3f}  miss {r['miss']:.3f}  FA {r['false_alarm']:.3f}  "
              f"conf {r['confusion']:.3f}  spk {r['hyp_speakers']}/{r['ref_speakers']}  RTF {r['rtf']:.3f}")
    print(f"  {label}weighted DER {w('der'):.3f}  (conf {w('confusion'):.3f})")
    return w("der")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["observe", "score", "sweep"])
    ap.add_argument("--meetings", nargs="+", default=["ES2011a", "IS1008a"])
    ap.add_argument("--kind", default="Array1-01", help="Array1-01 (far mic) or Mix-Headset")
    ap.add_argument("--embedder", default="campp", choices=list(models.EMBEDDERS))
    ap.add_argument("--latency", type=float, default=1.0)
    for k, v in (("assign", 0.55), ("new", 0.45), ("merge", 0.75), ("min_gap", 0.5), ("min_dur", 0.3)):
        ap.add_argument(f"--{k.replace('_', '-')}", dest=k, type=float, default=v)
    ap.add_argument("--max-speakers", type=int, default=0)
    ap.add_argument("--final", default="refine", choices=["recluster", "refine", "none"])
    ap.add_argument("--cluster", type=float, default=0.5)
    ap.add_argument("--backend", help="trained backend .npz applied to embeddings")
    ap.add_argument("--data", type=Path, help="folder of <meeting>.<kind>.wav/.flac + .rttm + .uem (default data/ami)")
    a = ap.parse_args()
    if a.data:
        global DATA
        DATA = a.data.resolve()

    backend = Backend.load(a.backend) if a.backend else None
    cached = {m: project(observe(m, a.kind, a.embedder, a.latency), backend) for m in a.meetings}
    if a.cmd == "observe":
        return
    base = dict(assign=a.assign, new=a.new, merge=a.merge, min_gap=a.min_gap,
                min_dur=a.min_dur, max_speakers=a.max_speakers, final=a.final, cluster=a.cluster)
    if a.cmd == "score":
        rows = [{"meeting": m, "rtf": c["rtf"], "dur": c["dur"], **score(c, m, **base)} for m, c in cached.items()]
        report(rows, f"{a.embedder} {a.kind} ")
        return
    best = None
    for assign, gap, merge in itertools.product((0.4, 0.5, 0.6, 0.7), (0.1, 0.2, 0.3), (0.6, 0.7, 0.8)):
        p = dict(base, assign=assign, new=assign - gap, merge=merge)
        rows = [{"meeting": m, "rtf": c["rtf"], "dur": c["dur"], **score(c, m, **p)} for m, c in cached.items()]
        tot = sum(r["dur"] for r in rows)
        d = sum(r["der"] * r["dur"] for r in rows) / tot
        spk = [f"{r['hyp_speakers']}/{r['ref_speakers']}" for r in rows]
        print(f"assign {assign:.2f} new {assign - gap:.2f} merge {merge:.2f}  DER {d:.3f}  speakers {spk}")
        if best is None or d < best[0]:
            best = (d, p)
    print(f"best DER {best[0]:.3f} with {best[1]}")


if __name__ == "__main__":
    main()
