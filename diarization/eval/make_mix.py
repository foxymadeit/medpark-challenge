"""Build mixed-language test meetings from voices the fine-tune never heard.

  python -m eval.make_mix --meetings 12
  python -m eval.run_eval sweep --data ../data/mix/meetings --kind mix --embedder titanet-small --meetings mix01 ...

Romanian and Russian voices come from Common Voice 22 (CC0): the tenth of
speakers the Kaggle run holds out (train/holdout.py) plus everyone who
recorded both languages. English voices come from LibriSpeech test-clean
(CC BY 4.0), whose speakers are outside LibriSpeech's training sets. Each
meeting has 3 to 7 people taking turns of a few seconds, short gaps and some
overlap; every other meeting has a bilingual person switching between
Romanian and Russian under one label. Writes <meeting>.mix.wav, .rttm and
.uem to data/mix/meetings/.

This is the one networked tool in eval/ besides the AMI fetch script: it
downloads about 3.7 GB once into data/mix/ (gitignored).
"""

import argparse
import csv
import json
import tarfile
import urllib.request
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from diarizer.audio import load
from train.holdout import held_out

SR = 16000
ROOT = Path(__file__).resolve().parents[2] / "data" / "mix"
CV = "https://huggingface.co/datasets/fsicoli/common_voice_22_0"
LIBRI = "https://www.openslr.org/resources/12/test-clean.tar.gz"
SPLITS = ("train", "dev", "test", "other")


def get(url, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {url}")
        urllib.request.urlretrieve(url, dest)  # noqa: S310 (fixed https sources above)
    return dest


def trim(x, frame=0.02, floor_db=-30.0):
    """Cut the silence Common Voice and LibriSpeech clips carry at each end,
    so a reference turn covers speech only (anything 30 dB under the loudest
    20 ms frame counts as silence)."""
    n = int(frame * SR)
    rms = np.sqrt(np.mean(x[: len(x) // n * n].reshape(-1, n) ** 2, axis=1)) if len(x) >= n else np.zeros(0)
    on = np.flatnonzero(rms > rms.max() * 10 ** (floor_db / 20)) if rms.size else []
    return x[on[0] * n:(on[-1] + 1) * n] if len(on) else x


def cv_speakers(lang):
    """client_id -> [(split, clip file name)] from the four split TSVs."""
    csv.field_size_limit(10**9)
    out = {}
    for split in SPLITS:
        tsv = get(f"{CV}/resolve/main/transcript/{lang}/{split}.tsv", ROOT / "cv" / lang / f"{split}.tsv")
        with tsv.open(encoding="utf-8") as f:
            for r in csv.DictReader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
                out.setdefault(r["client_id"], []).append((split, r["path"]))
    return out


def cv_clips(lang, wanted: dict) -> dict:
    """Decode only the clips we use: {client_id: [16 kHz arrays]}."""
    names = {name: cid for cid, clips in wanted.items() for _, name in clips}
    splits = {split for clips in wanted.values() for split, _ in clips}
    tree = json.loads(urllib.request.urlopen(  # noqa: S310
        f"https://huggingface.co/api/datasets/fsicoli/common_voice_22_0/tree/main/audio/{lang}?recursive=true").read())
    out = {cid: [] for cid in wanted}
    for split in sorted(splits):
        for tar in (x["path"] for x in tree if x["type"] == "file" and x["path"].split("/")[2] == split):
            local = get(f"{CV}/resolve/main/{tar}", ROOT / "cv" / tar)
            with tarfile.open(local) as t:
                for m in t:
                    name = m.name.rsplit("/", 1)[-1]
                    if name in names:
                        clip = ROOT / "cv" / lang / "clips" / name
                        if not clip.exists():
                            clip.parent.mkdir(parents=True, exist_ok=True)
                            clip.write_bytes(t.extractfile(m).read())
                        out[names[name]].append(trim(load(clip)))
    return out


def libri_speakers(n, rng):
    tgz = get(LIBRI, ROOT / "test-clean.tar.gz")
    base = ROOT / "LibriSpeech" / "test-clean"
    if not base.exists():
        with tarfile.open(tgz) as t:
            t.extractall(ROOT, filter="data")
    spk = sorted(p for p in base.iterdir() if p.is_dir())
    chosen = rng.choice(len(spk), size=n, replace=False)
    out = {}
    for i in chosen:
        files = sorted(spk[i].rglob("*.flac"))
        pick = rng.choice(len(files), size=min(15, len(files)), replace=False)
        out[f"en_{spk[i].name}"] = [trim(load(files[j]))[: 8 * SR] for j in pick]  # Common Voice clips run 3-8 s too
    return out


def build_meeting(voices: dict, rng, minutes=3.5, overlap=0.15):
    """voices: {label: [clips]}. Returns (audio, [(label, start, end)])."""
    labels = list(voices)
    audio, ref, t, last = np.zeros(int((minutes * 60 + 60) * SR), np.float32), [], 0.0, None
    while t < minutes * 60:
        who = rng.choice([x for x in labels if x != last] if len(labels) > 1 else labels)
        clips = voices[who]
        turn = np.concatenate([clips[rng.integers(len(clips))] for _ in range(rng.integers(1, 4))])
        turn = turn / (np.sqrt(np.mean(turn**2)) + 1e-9) * 0.05 * 10 ** (rng.uniform(-3, 3) / 20)
        start = t - rng.uniform(0.3, 1.0) if ref and rng.random() < overlap else t + rng.uniform(0.2, 1.0)
        start = max(start, 0.0)
        a = int(start * SR)
        audio[a:a + len(turn)] += turn[: len(audio) - a]
        end = start + len(turn) / SR
        ref.append((who, round(start, 3), round(end, 3)))
        t, last = max(t, end), who
    return audio[: int(t * SR) + SR], ref


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", type=int, default=12)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    ro, ru = cv_speakers("ro"), cv_speakers("ru")
    both = sorted(c for c in set(ro) & set(ru) if len(ro[c]) >= 4 and len(ru[c]) >= 4)
    pool = {lang: sorted(c for c, clips in spk.items() if held_out(c) and c not in both and len(clips) >= 8)
            for lang, spk in (("ro", ro), ("ru", ru))}
    print(f"held-out voices: {len(pool['ro'])} Romanian, {len(pool['ru'])} Russian, {len(both)} bilingual")
    plan, need = [], {"ro": {}, "ru": {}}
    for m in range(a.meetings):
        n_ro, n_ru, n_en = [(2, 1, 0), (1, 2, 1), (2, 2, 2), (1, 1, 1)][m % 4]
        pick = {lang: list(rng.choice(pool[lang], size=n, replace=False)) for lang, n in (("ro", n_ro), ("ru", n_ru))}
        bi = both[m // 2 % len(both)] if both and m % 2 == 0 else None
        plan.append((pick, n_en, bi))
        for lang in ("ro", "ru"):
            for c in pick[lang] + ([bi] if bi else []):
                need[lang][c] = (ro if lang == "ro" else ru)[c][:15]
    clips = {lang: cv_clips(lang, need[lang]) for lang in ("ro", "ru")}
    out = ROOT / "meetings"
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for m, (pick, n_en, bi) in enumerate(plan, 1):
        voices = {f"{lang}_{c[:8]}": clips[lang][c] for lang in ("ro", "ru") for c in pick[lang] if clips[lang][c]}
        if n_en:
            voices.update(libri_speakers(n_en, rng))
        if bi:
            voices[f"bi_{bi[:8]}"] = clips["ro"][bi] + clips["ru"][bi]  # one person, two languages, one label
        name = f"mix{m:02d}"
        audio, ref = build_meeting(voices, rng)
        wavfile.write(out / f"{name}.mix.wav", SR, audio)
        (out / f"{name}.rttm").write_text("".join(
            f"SPEAKER {name} 1 {s:.3f} {e - s:.3f} <NA> <NA> {w} <NA> <NA>\n" for w, s, e in ref))
        (out / f"{name}.uem").write_text(f"{name} 1 0.000 {len(audio) / SR:.3f}\n")
        summary[name] = {"speakers": sorted(voices), "minutes": round(len(audio) / SR / 60, 1), "turns": len(ref)}
        print(f"{name}: {len(voices)} speakers {sorted(voices)}, {len(audio) / SR / 60:.1f} min, {len(ref)} turns")
    (out / "meetings.json").write_text(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
