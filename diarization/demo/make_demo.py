"""Build the 5-person recording behind the README's terminal demo.

  python -m demo.make_demo      # after eval/make_mix.py has fetched its voices

Five voices none of our models trained on: Romanian and Russian speakers
from the held-out tenth of Common Voice 22 (CC0) and one English speaker
from LibriSpeech test-clean (CC BY 4.0). They get the most common first
names in Moldova: Ion and Maria for the population as a whole, David,
Sofia and Alexandru from the Public Services Agency's birth records (see
README.md). Maria recorded both Romanian and Russian, so she switches
language under one label.

The recording opens with each person introducing themselves in turn, then
a meeting with interruptions, over a quiet room-noise floor (a real
microphone never records exact silence). Writes demo/meeting.wav, meeting.rttm (who
really spoke when) and meeting.json (which clips were used).
"""

import csv
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from diarizer.audio import load
from eval.make_mix import ROOT, SPLITS, build_meeting, trim
from train.holdout import held_out

SR = 16000
OUT = Path(__file__).resolve().parent
CAST = [("Ion", "ro", "m"), ("Maria", "bi", "f"), ("David", "en", "m"), ("Sofia", "ru", "f"), ("Alexandru", "ru", "m")]


def cv_people(lang):
    """client_id -> (gender, [local clip paths]) for held-out speakers whose clips are on disk."""
    csv.field_size_limit(10**9)
    out = {}
    for split in SPLITS:
        with (ROOT / "cv" / lang / f"{split}.tsv").open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                clip = ROOT / "cv" / lang / "clips" / r["path"]
                if clip.exists():
                    g, clips = out.get(r["client_id"], (r["gender"][:1], []))
                    out[r["client_id"]] = (g or r["gender"][:1], clips + [clip])
    return out


def libri_people():
    base = ROOT / "LibriSpeech"
    gender = {}
    for line in (base / "SPEAKERS.TXT").read_text().splitlines():
        if not line.startswith(";") and "|" in line:
            sid, g, subset = (x.strip() for x in line.split("|")[:3])
            if subset == "test-clean":
                gender[sid] = g.lower()
    return {sid: (g, sorted((base / "test-clean" / sid).rglob("*.flac"))) for sid, g in gender.items()}


def pick(people, gender, rng, taken, n=8, both=None):
    ok = sorted(c for c, (g, clips) in people.items()
                if g == gender and len(clips) >= n and c not in taken and (both is None or c in both))
    return ok[rng.integers(len(ok))] if ok else None


def main():
    rng = np.random.default_rng(7)
    ro, ru, en = cv_people("ro"), cv_people("ru"), libri_people()
    ro = {c: v for c, v in ro.items() if held_out(c) or c in ru}  # held out, or bilingual (held out by rule)
    ru = {c: v for c, v in ru.items() if held_out(c) or c in ro}
    voices, used, taken = {}, {}, set()
    for name, lang, g in CAST:
        if lang == "bi":
            c = pick(ro, g, rng, taken, n=4, both=set(ru)) or pick(ro, g, rng, taken)
            files = ro[c][1][:8] + (ru[c][1][:8] if c in ru else [])
        else:
            people = {"ro": ro, "ru": ru, "en": en}[lang]
            c = pick(people, g, rng, taken)
            files = people[c][1][:12]
        if c is None:
            raise SystemExit(f"no local {lang} voice for {name}; run eval/make_mix.py first")
        taken.add(c)
        voices[name] = [trim(load(f))[: 8 * SR] for f in files]
        used[name] = {"language": lang, "source": "LibriSpeech test-clean" if lang == "en" else "Common Voice 22",
                      "speaker": c if lang == "en" else c[:12], "clips": [f.name for f in files]}

    # introductions: one at a time, about 4 s each
    parts, ref, t = [np.zeros(SR, np.float32)], [], 1.0
    for name, _, _ in CAST:
        intro = next((c for c in voices[name] if 3 * SR <= len(c) <= 7 * SR), voices[name][0])  # a whole sentence
        intro = intro / (np.sqrt(np.mean(intro**2)) + 1e-9) * 0.05
        parts += [intro, np.zeros(int(1.2 * SR), np.float32)]
        ref.append((name, round(t, 3), round(t + len(intro) / SR, 3)))
        t += len(intro) / SR + 1.2
    parts.append(np.zeros(7 * SR, np.float32))  # someone reaches for Enter
    t += 7.0
    short = {n: [c[: 4 * SR] for c in v[2:]] for n, v in voices.items()}  # quick back-and-forth
    meeting, turns = build_meeting(short, rng, minutes=1.3, overlap=0.2)
    ref += [(w, round(t + s, 3), round(t + e, 3)) for w, s, e in turns]
    audio = np.concatenate(parts + [meeting, np.zeros(2 * SR, np.float32)])
    audio = audio + rng.normal(0, 0.0009, len(audio)).astype(np.float32)  # a room is never digitally silent

    wavfile.write(OUT / "meeting.wav", SR, audio.astype(np.float32))
    (OUT / "meeting.rttm").write_text("".join(
        f"SPEAKER meeting 1 {s:.3f} {e - s:.3f} <NA> <NA> {w} <NA> <NA>\n" for w, s, e in ref))
    (OUT / "meeting.json").write_text(json.dumps({"seconds": round(len(audio) / SR, 1), "turns": len(ref),
                                                 "voices": used}, indent=2))
    print(f"{len(audio) / SR:.0f} s, {len(ref)} turns: " + ", ".join(f"{n} ({used[n]['language']})" for n in used))


if __name__ == "__main__":
    main()
