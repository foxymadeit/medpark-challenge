"""Build NeMo speaker-training manifests from labelled meetings.

  python -m train.make_manifest --data ../data/ami/train --out train/manifests/ami_train.jsonl

One JSON line per clean single-speaker piece (1.5-3 s), the format NeMo's
EncDecSpeakerLabelModel trains on:
  {"audio_filepath": ..., "offset": 12.3, "duration": 2.4, "label": "FEE005"}
Paths are written relative to --root so the manifest can be uploaded with
the audio to a GPU machine.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from eval.der import read_rttm

from .fit_backend import clean_intervals


def pieces(intervals, rng, lo=1.5, hi=3.0, cap=200):
    out = []
    for a, b in intervals:
        t = a
        while b - t >= lo:
            n = min(b - t, rng.uniform(lo, hi))
            out.append((round(t, 3), round(n, 3)))
            t += n
    rng.shuffle(out)
    return out[:cap]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="folder with <meeting>.Array1-01.flac + <meeting>.rttm")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=None, help="make audio paths relative to this folder")
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    n, speakers = 0, set()
    with a.out.open("w") as f:
        for flac in sorted(a.data.glob("*.Array1-01.flac")):
            rttm = a.data / f"{flac.name.split('.')[0]}.rttm"
            if not rttm.exists():
                continue
            path = str(flac.relative_to(a.root)) if a.root else str(flac.resolve())
            for spk, iv in clean_intervals(read_rttm(rttm)).items():
                for off, dur in pieces(iv, rng):
                    f.write(json.dumps({"audio_filepath": path, "offset": off, "duration": dur, "label": spk}) + "\n")
                    n += 1
                    speakers.add(spk)
    print(f"wrote {n} pieces from {len(speakers)} speakers to {a.out}")


if __name__ == "__main__":
    main()
