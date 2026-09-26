"""Build the RO/RU/EN fine-tuning set, including spliced code-switched speech.

Writes <out>/:
  audio/*.flac                 16 kHz mono
  train.jsonl, dev.jsonl       NeMo manifests: audio_filepath (relative), duration, text, lang, source
  stats.json                   hours per source and language

Real speech (punctuation and case kept, clips 0.5-20 s):
  ro  ROMPAR train (Moldovan + Romanian parliament, x2 weight), Common Voice 17 validated minus test,
      FLEURS train, one VoxPopuli shard
  ru  Common Voice 17 train, FLEURS train
  en  FLEURS train, one Common Voice 17 shard
  cs  CS-FLEURS XTTS train, Russian-English (one synthetic voice per sentence)
Spliced code-switching ("Speech Collage", arXiv 2309.15674): words force-aligned with
torchaudio's MMS aligner; 1-4 words of a real sentence are replaced by a phrase from
another language, with 20 ms crossfades and loudness matching. Speakers who recorded
both Romanian and Russian in Common Voice are used as donors first, so the voice
does not change at the switch.

Test sets stay out: ROMPAR test, FLEURS test, CS-FLEURS tests, the Medpark gold.

    python -m asr_train.build_data --out data/asrdata                        # from the Hub
    python -m asr_train.build_data --out data/asrdata --hf-mirror ~/hf-mirror # offline, see hub.py
    python -m asr_train.build_data --out /tmp/smoke --sources fleurs --collage-hours 0.2
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import re
import shutil
import tarfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .collage import (
    MAX_S,
    MIN_S,
    SEED,
    SR,
    align_word,
    clean_text,
    fit_phrase,
    hour_stats,
    plan_splice,
    splice,
    split_dev,
    to_16k,
    usable_directions,
)
from .common import write_jsonl
from .hub import Hub

CV = "fixie-ai/common_voice_17_0"


def decode(blob: bytes) -> np.ndarray:
    import soundfile as sf

    try:
        data, sr = sf.read(io.BytesIO(blob), always_2d=False)
    except Exception:  # mp3 on an old libsndfile
        import librosa

        data, sr = librosa.load(io.BytesIO(blob), sr=None, mono=True)
    return to_16k(np.asarray(data, dtype=np.float32), sr)


# ---------------------------------------------------------------- writer

@dataclass
class Writer:
    out: Path
    rows: list[dict] = field(default_factory=list)
    n: int = 0

    def add(self, audio: np.ndarray, text: str, lang: str, source: str, speaker: str = "", weight: int = 1) -> dict | None:
        import soundfile as sf

        dur = len(audio) / SR
        if not (MIN_S <= dur <= MAX_S) or not text:
            return None
        rel = f"audio/{source}_{self.n:07d}.flac"
        self.n += 1
        (self.out / rel).parent.mkdir(parents=True, exist_ok=True)
        sf.write(self.out / rel, audio, SR, format="FLAC")
        row = {"audio_filepath": rel, "duration": round(dur, 3), "text": text, "lang": lang, "source": source, "speaker": speaker}
        self.rows.extend([row] * weight)
        return row


# ---------------------------------------------------------------- sources

def parquet_rows(path: Path, columns: list[str] | None):
    import pyarrow.parquet as pq

    for batch in pq.ParquetFile(path).iter_batches(batch_size=256, columns=columns):
        yield from batch.to_pylist()


def add_rompar(w: Writer, hub: Hub) -> None:
    for f in hub.list("avramandrei/rompar", "data/train-"):
        for r in parquet_rows(hub.file("avramandrei/rompar", f), ["audio", "transcript", "dialect", "record_id"]):
            w.add(decode(r["audio"]["bytes"]), clean_text(r["transcript"], "rompar"), "ro", "rompar", str(r["dialect"]), weight=2)


def add_common_voice(w: Writer, hub: Hub, locale: str, split: str, max_files: int | None = None, skip_paths: set | None = None) -> None:
    for f in hub.list(CV, f"{locale}/{split}/")[:max_files]:
        for r in parquet_rows(hub.file(CV, f), ["audio", "sentence", "client_id", "path"]):
            if skip_paths and r["path"] in skip_paths:
                continue
            w.add(decode(r["audio"]["bytes"]), clean_text(r["sentence"], "cv"), locale, f"cv_{locale}", r["client_id"])


def cv_test_paths(hub: Hub, locale: str) -> set:
    return {r["path"] for f in hub.list(CV, f"{locale}/test/") for r in parquet_rows(hub.file(CV, f), ["path"])}


def add_fleurs(w: Writer, hub: Hub, lang: str, code: str) -> None:
    with open(hub.file("google/fleurs", f"data/{code}/train.tsv"), encoding="utf-8") as f:
        text = {r[1]: r[2] for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)}
    with tarfile.open(hub.file("google/fleurs", f"data/{code}/audio/train.tar.gz")) as tf:
        for m in tf:
            name = Path(m.name).name
            if name in text:
                w.add(decode(tf.extractfile(m).read()), clean_text(text[name], "fleurs"), lang, f"fleurs_{lang}")


def add_voxpopuli_ro(w: Writer, hub: Hub) -> None:
    f = hub.list("facebook/voxpopuli", "ro/train-")[0]
    for r in parquet_rows(hub.file("facebook/voxpopuli", f), None):
        text = r.get("raw_text") or r.get("normalized_text") or ""
        w.add(decode(r["audio"]["bytes"]), clean_text(text, "voxpopuli"), "ro", "voxpopuli_ro", str(r.get("speaker_id", "")))


def add_csfleurs_ru_en(w: Writer, hub: Hub) -> None:
    root = hub.snapshot("byan/cs-fleurs", ["xtts/train/metadata.jsonl", "xtts/train/audio/cs_rus_eng*/*"])
    with open(root / "xtts/train/metadata.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["language"] == "rus-eng":
                audio = decode((root / "xtts/train" / r["file_name"]).read_bytes())
                w.add(audio, clean_text(r["text"], "csfleurs"), "ru+en", "csfleurs_ru_en", r["speaker"])


SOURCES: dict[str, Callable[[Writer, Hub], None]] = {
    "rompar": add_rompar,
    "cv_ro": lambda w, hub: add_common_voice(w, hub, "ro", "validated", skip_paths=cv_test_paths(hub, "ro")),
    "cv_ru": lambda w, hub: add_common_voice(w, hub, "ru", "train"),
    "cv_en": lambda w, hub: add_common_voice(w, hub, "en", "train", max_files=1),
    "fleurs": lambda w, hub: [add_fleurs(w, hub, l, c) for l, c in (("ro", "ro_ro"), ("ru", "ru_ru"), ("en", "en_us"))],
    "voxpopuli_ro": add_voxpopuli_ro,
    "csfleurs_ru_en": add_csfleurs_ru_en,
}


# ---------------------------------------------------------------- speech collage

@dataclass
class Aligned:
    path: str
    lang: str
    speaker: str
    words: list[str]  # original tokens, with their punctuation and case
    spans: list[tuple[int, int]]  # sample start/end of each token


def align_bank(rows: list[dict], root: Path, per_lang: int, device: str = "auto") -> dict[str, list[Aligned]]:
    """Force-align up to per_lang clean monolingual utterances per language (MMS aligner)."""
    import soundfile as sf
    import torch
    import torchaudio
    import uroman

    ur = uroman.Uroman()
    romanize = lambda t: ur.romanize_string(t, lcode="rus")  # noqa: E731
    bundle = torchaudio.pipelines.MMS_FA
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    model = bundle.get_model(with_star=False).to(device).eval()
    tokenizer, aligner = bundle.get_tokenizer(), bundle.get_aligner()

    rng = random.Random(SEED)
    bank: dict[str, list[Aligned]] = {"ro": [], "ru": [], "en": []}
    candidates = [r for r in rows if r["lang"] in bank and 2.0 <= r["duration"] <= 12.0 and not re.search(r"\d", r["text"])]
    rng.shuffle(candidates)
    seen = set()
    for r in candidates:
        lang = r["lang"]
        if len(bank[lang]) >= per_lang or r["audio_filepath"] in seen:
            continue
        seen.add(r["audio_filepath"])
        tokens = r["text"].split()
        keys = [align_word(t, lang, romanize) for t in tokens]
        if len(tokens) < 4 or any(not k for k in keys):
            continue  # standalone punctuation or unalignable token: skip, keep the bank clean
        audio, _ = sf.read(root / r["audio_filepath"], dtype="float32")
        with torch.inference_mode():
            emission, _ = model(torch.from_numpy(audio)[None].to(device))
        try:
            token_spans = aligner(emission[0], tokenizer(keys))
        except Exception:
            continue
        ratio = len(audio) / emission.shape[1]
        spans = [(int(s[0].start * ratio), int(s[-1].end * ratio)) for s in token_spans]
        bank[lang].append(Aligned(r["audio_filepath"], lang, r.get("speaker", ""), tokens, spans))
    print({k: len(v) for k, v in bank.items()}, flush=True)
    return bank


def make_collage(bank: dict[str, list[Aligned]], w: Writer, hours: float) -> None:
    import soundfile as sf

    directions = usable_directions({k: len(v) for k, v in bank.items()})
    if not directions:
        print("collage: no language pair has aligned sentences, skipped", flush=True)
        return
    rng = random.Random(SEED)
    by_speaker: dict[tuple[str, str], list[Aligned]] = {}
    for lang, items in bank.items():
        for a in items:
            by_speaker.setdefault((lang, a.speaker), []).append(a)
    cache: dict[str, np.ndarray] = {}

    def audio(a: Aligned) -> np.ndarray:
        if a.path not in cache:
            if len(cache) > 512:
                cache.clear()
            cache[a.path] = sf.read(w.out / a.path, dtype="float32")[0]
        return cache[a.path]

    total, target = 0.0, hours * 3600
    dirs, weights = [(m, i) for m, i, _ in directions], [p for *_, p in directions]
    while total < target:
        m_lang, i_lang = rng.choices(dirs, weights)[0]
        mat = rng.choice(bank[m_lang])
        same_voice = by_speaker.get((i_lang, mat.speaker)) if mat.speaker else None
        don = rng.choice(same_voice) if same_voice and rng.random() < 0.7 else rng.choice(bank[i_lang])
        i, k, j, n = plan_splice(rng, len(mat.words), len(don.words))
        cut = (mat.spans[i][0], mat.spans[i + k - 1][1])
        piece = audio(don)[don.spans[j][0] : don.spans[j + n - 1][1]]
        mixed = splice(audio(mat), cut, piece)
        phrase = fit_phrase(don.words[j : j + n], at_start=i == 0, at_end=i + k == len(mat.words))
        text = " ".join(mat.words[:i] + phrase + mat.words[i + k :])
        row = w.add(mixed, text, f"{m_lang}+{i_lang}", "collage", mat.speaker)
        if row:
            total += row["duration"]


# ---------------------------------------------------------------- main

def write_outputs(rows: list[dict], out: Path) -> None:
    train, dev = split_dev(rows)
    write_jsonl(out / "train.jsonl", train)
    write_jsonl(out / "dev.jsonl", dev)
    stats = hour_stats(train)
    (out / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1), flush=True)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, required=True, help="Dataset folder to write.")
    p.add_argument("--sources", default=",".join(SOURCES), help=f"Comma list out of: {', '.join(SOURCES)}.")
    p.add_argument("--hf-mirror", type=Path, default=None, help="Local copies of the Hub repos; no network then.")
    p.add_argument("--raw-dir", type=Path, default=None, help="Hub download cache (default: the usual HF cache).")
    p.add_argument("--prune-raw", action="store_true", help="Delete <raw-dir>/hf after each source (small disks, e.g. Kaggle).")
    p.add_argument("--collage-hours", type=float, default=30.0, help="Spliced code-switched speech to add; 0 = none.")
    p.add_argument("--per-lang", type=int, default=6000, help="Aligned sentences per language for the collage bank.")
    p.add_argument("--device", default="auto", help="Aligner device: auto | cuda | cpu.")
    args = p.parse_args(argv)
    args.sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = set(args.sources) - set(SOURCES)
    if unknown:
        p.error(f"unknown sources: {', '.join(sorted(unknown))}")
    if args.prune_raw and not args.raw_dir:
        p.error("--prune-raw needs --raw-dir; it never deletes the shared HF cache")
    return args


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    cache = args.raw_dir / "hf" if args.raw_dir else None
    hub = Hub(mirror=args.hf_mirror, cache=cache)
    w = Writer(args.out)
    for name in args.sources:
        before = len(w.rows)
        try:
            SOURCES[name](w, hub)
        except Exception as exc:  # one broken source must not cost the whole run
            print(f"!! {name} failed: {exc!r}", flush=True)
        print(f"{name}: +{len(w.rows) - before} rows", flush=True)
        if args.prune_raw and cache and not args.hf_mirror:
            shutil.rmtree(cache, ignore_errors=True)  # raw downloads are big; the FLAC copies are all we need
    write_outputs(w.rows, args.out)  # real speech is saved even if splicing fails below
    if args.collage_hours <= 0:
        return
    try:
        mono = [r for r in w.rows if r["source"] != "csfleurs_ru_en"]
        make_collage(align_bank(mono, args.out, per_lang=args.per_lang, device=args.device), w, args.collage_hours)
        write_outputs(w.rows, args.out)
    except Exception as exc:
        print(f"!! collage failed, manifests keep real speech only: {exc!r}", flush=True)


if __name__ == "__main__":
    main()
