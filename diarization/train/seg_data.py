"""Training meetings for the segmentation fine-tune, and the pyannote
protocol files that describe them.

Real far-field meetings come from AMI. Romanian and Russian ones are built
from Common Voice training speakers (never the held-out tenth): people take
turns with short gaps and some overlap, each voice goes through its own room
echo, and the room gets background noise, so the model hears turn changes
in the languages Medpark speaks.
"""

from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

from eval.make_mix import build_meeting, trim


def room(clip, rir):
    """Clip as heard across a room, same length so labels stay aligned."""
    wet = fftconvolve(clip, rir)[: len(clip)]
    return (wet / (np.abs(wet).max() + 1e-9) * np.abs(clip).max()).astype(np.float32)


def synth_meetings(voices: dict, n: int, rng, rirs=(), noises=(), minutes=4.0):
    """voices: {label: [16 kHz clips]} -> n (audio, [(label, start, end)]) meetings of 3 to 6 people."""
    labels = sorted(voices)
    for _ in range(n):
        people = list(rng.choice(labels, size=int(rng.integers(3, 7)), replace=False))
        clips = {}
        for p in people:
            rir = rirs[rng.integers(len(rirs))] if len(rirs) and rng.random() < 0.7 else None
            clips[p] = [room(c, rir) if rir is not None else c for c in voices[p][:12]]
        audio, ref = build_meeting(clips, rng, minutes=minutes, overlap=float(rng.uniform(0.1, 0.25)))
        if len(noises) and rng.random() < 0.7:
            noise = np.resize(noises[rng.integers(len(noises))], len(audio))
            snr = rng.uniform(10, 25)
            gain = np.sqrt(np.mean(audio ** 2) / (np.mean(noise ** 2) + 1e-12) / 10 ** (snr / 10))
            audio = audio + gain * noise
        yield audio.astype(np.float32), ref


def voices_from_items(items, load, min_clips=8, max_speakers=1500, rng=None):
    """Kernel pieces (path, offset, dur, label) -> {label: [trimmed clips]}."""
    by = {}
    for path, _, _, label in items:
        by.setdefault(label, []).append(path)
    keep = [k for k, v in by.items() if len(v) >= min_clips]
    if rng is not None and len(keep) > max_speakers:
        keep = list(rng.choice(keep, size=max_speakers, replace=False))
    return {k: [trim(load(p)) for p in by[k][:12]] for k in keep}


def write_protocol(root: Path, splits: dict) -> Path:
    """splits: {"train"|"development": [(uri, wav, [(spk, start, end)], (uem_start, uem_end))]}
    -> database.yml for protocol MOM.SpeakerDiarization.far, audio at {root}/wav/{uri}.wav."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "wav").mkdir(exist_ok=True)
    blocks = []
    for split, rows in splits.items():
        uris, rttm, uem = [], [], []
        for uri, wav, ref, (a, b) in rows:
            link = root / "wav" / f"{uri}.wav"
            if not link.exists():
                link.symlink_to(Path(wav).resolve())
            uris.append(uri)
            rttm += [f"SPEAKER {uri} 1 {s:.3f} {e - s:.3f} <NA> <NA> {w} <NA> <NA>" for w, s, e in ref if e > s]
            uem.append(f"{uri} 1 {a:.3f} {b:.3f}")
        for name, lines in (("lst", uris), ("rttm", rttm), ("uem", uem)):
            (root / f"{split}.{name}").write_text("\n".join(lines) + "\n")
        blocks.append(f"        {split}:\n          uri: {root}/{split}.lst\n"
                      f"          annotation: {root}/{split}.rttm\n          annotated: {root}/{split}.uem\n")
    db = root / "database.yml"
    db.write_text(f"Databases:\n  MOM: {root}/wav/{{uri}}.wav\nProtocols:\n  MOM:\n    SpeakerDiarization:\n"
                  f"      far:\n" + "".join(blocks))
    return db
