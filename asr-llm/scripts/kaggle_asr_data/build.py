"""Kaggle: build the RO/RU/EN fine-tuning set, including spliced code-switched speech.

Dev-time only (Internet ON). Writes /kaggle/working/asrdata/:
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

    kaggle kernels push -p asr-llm/scripts/kaggle_asr_data        (on Kaggle)
    python build.py selftest                                      (anywhere, numpy only)
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import re
import subprocess
import sys
import tarfile
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 16_000
MIN_S, MAX_S = 0.5, 20.0
FADE = int(0.02 * SR)
RAW = Path(os.environ.get("RAW_DIR", "/tmp/raw"))
OUT = Path(os.environ.get("OUT_DIR", "/kaggle/working/asrdata"))
COLLAGE_HOURS = float(os.environ.get("COLLAGE_HOURS", "30"))
SEED = 1234

# Direction weights for spliced items: matrix language -> inserted language.
DIRECTIONS = [("ro", "ru", 0.50), ("ro", "en", 0.20), ("ru", "ro", 0.15), ("ru", "en", 0.15)]


def sh(cmd: str) -> None:
    print("+", cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


# ---------------------------------------------------------------- text

def clean_text(text: str, source: str) -> str:
    if source == "rompar":
        text = re.sub(r"\[[^\]]*\]", "", text)  # "parlament[ar]": the bracket was not spoken
    text = text.replace("**", "")  # CS-FLEURS marks the English spans
    return re.sub(r"\s+", " ", text).strip()


_LETTERS = re.compile(r"[^a-z']")


def align_word(token: str, lang: str, romanize) -> str:
    """Lowercase ASCII letters for the MMS aligner. Cyrillic goes through uroman first."""
    word = romanize(token) if lang == "ru" else token
    word = unicodedata.normalize("NFKD", word.lower())
    return _LETTERS.sub("", "".join(c for c in word if not unicodedata.combining(c)))


def fit_phrase(words: list[str], at_start: bool, at_end: bool) -> list[str]:
    """A phrase lifted from another sentence keeps its capital and full stop only where they still belong."""
    words = list(words)
    if not at_start and words[0][:1].isupper() and not words[0].isupper():
        words[0] = words[0][0].lower() + words[0][1:]
    if not at_end:
        words[-1] = words[-1].rstrip(".!?…")
    return [w for w in words if w]


# ---------------------------------------------------------------- audio

def to_16k(data: np.ndarray, sr: int) -> np.ndarray:
    from math import gcd

    from scipy.signal import resample_poly

    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SR:
        g = gcd(SR, sr)
        data = resample_poly(data, SR // g, sr // g)
    return data.astype(np.float32)


def decode(blob: bytes) -> np.ndarray:
    import soundfile as sf

    try:
        data, sr = sf.read(io.BytesIO(blob), always_2d=False)
    except Exception:  # mp3 on an old libsndfile
        import librosa

        data, sr = librosa.load(io.BytesIO(blob), sr=None, mono=True)
    return to_16k(np.asarray(data, dtype=np.float32), sr)


def splice(matrix: np.ndarray, cut: tuple[int, int], donor: np.ndarray) -> np.ndarray:
    """matrix[:a] + donor + matrix[b:], loudness matched to the matrix, 20 ms crossfades."""
    a, b = cut
    rms = lambda x: float(np.sqrt(np.mean(x**2)) + 1e-8)  # noqa: E731
    donor = donor * (rms(matrix) / rms(donor))
    parts = [matrix[:a], donor, matrix[b:]]
    out = parts[0]
    for nxt in parts[1:]:
        n = min(FADE, len(out), len(nxt))
        if n:
            ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
            out = np.concatenate([out[:-n], out[-n:] * (1 - ramp) + nxt[:n] * ramp, nxt[n:]])
        else:
            out = np.concatenate([out, nxt])
    return np.clip(out, -1.0, 1.0).astype(np.float32)


# ---------------------------------------------------------------- writer

@dataclass
class Writer:
    rows: list[dict] = field(default_factory=list)
    n: int = 0

    def add(self, audio: np.ndarray, text: str, lang: str, source: str, speaker: str = "", weight: int = 1) -> dict | None:
        import soundfile as sf

        dur = len(audio) / SR
        if not (MIN_S <= dur <= MAX_S) or not text:
            return None
        rel = f"audio/{source}_{self.n:07d}.flac"
        self.n += 1
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        sf.write(OUT / rel, audio, SR, format="FLAC")
        row = {"audio_filepath": rel, "duration": round(dur, 3), "text": text, "lang": lang, "source": source, "speaker": speaker}
        self.rows.extend([row] * weight)
        return row


# ---------------------------------------------------------------- sources

def hf_file(repo: str, path: str) -> str:
    from huggingface_hub import hf_hub_download

    return hf_hub_download(repo, path, repo_type="dataset", cache_dir=str(RAW / "hf"))


def repo_files(repo: str, prefix: str) -> list[str]:
    from huggingface_hub import HfApi

    return sorted(f for f in HfApi().list_repo_files(repo, repo_type="dataset") if f.startswith(prefix) and f.endswith(".parquet"))


def parquet_rows(path: str, columns: list[str]):
    import pyarrow.parquet as pq

    for batch in pq.ParquetFile(path).iter_batches(batch_size=256, columns=columns):
        yield from batch.to_pylist()


def add_rompar(w: Writer) -> None:
    for f in repo_files("avramandrei/rompar", "data/train-"):
        for r in parquet_rows(hf_file("avramandrei/rompar", f), ["audio", "transcript", "dialect", "record_id"]):
            w.add(decode(r["audio"]["bytes"]), clean_text(r["transcript"], "rompar"), "ro", "rompar", str(r["dialect"]), weight=2)


def add_common_voice(w: Writer, locale: str, split: str, max_files: int | None = None, skip_paths: set | None = None) -> None:
    repo = "fixie-ai/common_voice_17_0"
    for f in repo_files(repo, f"{locale}/{split}/")[:max_files]:
        for r in parquet_rows(hf_file(repo, f), ["audio", "sentence", "client_id", "path"]):
            if skip_paths and r["path"] in skip_paths:
                continue
            w.add(decode(r["audio"]["bytes"]), clean_text(r["sentence"], "cv"), locale, f"cv_{locale}", r["client_id"])


def cv_test_paths(locale: str) -> set:
    repo = "fixie-ai/common_voice_17_0"
    return {r["path"] for f in repo_files(repo, f"{locale}/test/") for r in parquet_rows(hf_file(repo, f), ["path"])}


def add_fleurs(w: Writer, lang: str, code: str) -> None:
    tsv = hf_file("google/fleurs", f"data/{code}/train.tsv")
    rows = list(csv.reader(open(tsv, encoding="utf-8"), delimiter="\t", quoting=csv.QUOTE_NONE))
    text = {r[1]: r[2] for r in rows}
    with tarfile.open(hf_file("google/fleurs", f"data/{code}/audio/train.tar.gz")) as tf:
        for m in tf:
            name = Path(m.name).name
            if name in text:
                w.add(decode(tf.extractfile(m).read()), clean_text(text[name], "fleurs"), lang, f"fleurs_{lang}")


def add_voxpopuli_ro(w: Writer) -> None:
    f = repo_files("facebook/voxpopuli", "ro/train-")[0]
    for r in parquet_rows(hf_file("facebook/voxpopuli", f), None):
        text = r.get("raw_text") or r.get("normalized_text") or ""
        w.add(decode(r["audio"]["bytes"]), clean_text(text, "voxpopuli"), "ro", "voxpopuli_ro", str(r.get("speaker_id", "")))


def add_csfleurs_ru_en(w: Writer) -> None:
    from huggingface_hub import snapshot_download

    root = Path(snapshot_download("byan/cs-fleurs", repo_type="dataset", cache_dir=str(RAW / "hf"),
                                  allow_patterns=["xtts/train/metadata.jsonl", "xtts/train/audio/cs_rus_eng*/*"]))
    for line in open(root / "xtts/train/metadata.jsonl", encoding="utf-8"):
        r = json.loads(line)
        if r["language"] == "rus-eng":
            w.add(decode((root / "xtts/train" / r["file_name"]).read_bytes()), clean_text(r["text"], "csfleurs"), "ru+en", "csfleurs_ru_en", r["speaker"])


# ---------------------------------------------------------------- speech collage

@dataclass
class Aligned:
    path: str
    lang: str
    speaker: str
    words: list[str]  # original tokens, with their punctuation and case
    spans: list[tuple[int, int]]  # sample start/end of each token


def align_bank(rows: list[dict], per_lang: int) -> dict[str, list[Aligned]]:
    """Force-align up to per_lang clean monolingual utterances per language (MMS aligner on GPU)."""
    import soundfile as sf
    import torch
    import torchaudio
    import uroman

    ur = uroman.Uroman()
    romanize = lambda t: ur.romanize_string(t, lcode="rus")  # noqa: E731
    bundle = torchaudio.pipelines.MMS_FA
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
        audio, _ = sf.read(OUT / r["audio_filepath"], dtype="float32")
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
            cache[a.path] = sf.read(OUT / a.path, dtype="float32")[0]
        return cache[a.path]

    total, target = 0.0, hours * 3600
    dirs, weights = [(m, i) for m, i, _ in DIRECTIONS], [p for *_, p in DIRECTIONS]
    while total < target:
        m_lang, i_lang = rng.choices(dirs, weights)[0]
        if not bank[m_lang] or not bank[i_lang]:
            break
        mat = rng.choice(bank[m_lang])
        same_voice = by_speaker.get((i_lang, mat.speaker)) if mat.speaker else None
        don = rng.choice(same_voice) if same_voice and rng.random() < 0.7 else rng.choice(bank[i_lang])
        k = rng.randint(1, min(4, len(mat.words) - 2))  # replace k words, never the whole sentence
        i = rng.randint(1, len(mat.words) - k)
        n = rng.randint(1, min(4, len(don.words)))
        j = rng.randint(0, len(don.words) - n)
        cut = (mat.spans[i][0], mat.spans[i + k - 1][1])
        piece = audio(don)[don.spans[j][0] : don.spans[j + n - 1][1]]
        mixed = splice(audio(mat), cut, piece)
        phrase = fit_phrase(don.words[j : j + n], at_start=i == 0, at_end=i + k == len(mat.words))
        text = " ".join(mat.words[:i] + phrase + mat.words[i + k :])
        row = w.add(mixed, text, f"{m_lang}+{i_lang}", "collage", mat.speaker)
        if row:
            total += row["duration"]


# ---------------------------------------------------------------- main

def split_dev(rows: list[dict], frac: float = 0.01) -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    uniq = {r["audio_filepath"]: r for r in rows}
    dev_keys = {k for k in uniq if rng.random() < frac}
    train = [r for r in rows if r["audio_filepath"] not in dev_keys]
    dev = [uniq[k] for k in sorted(dev_keys)]
    return train, dev


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    w = Writer()
    steps = [
        ("rompar", lambda: add_rompar(w)),
        ("cv_ro", lambda: add_common_voice(w, "ro", "validated", skip_paths=cv_test_paths("ro"))),
        ("cv_ru", lambda: add_common_voice(w, "ru", "train")),
        ("cv_en", lambda: add_common_voice(w, "en", "train", max_files=1)),
        ("fleurs", lambda: [add_fleurs(w, l, c) for l, c in (("ro", "ro_ro"), ("ru", "ru_ru"), ("en", "en_us"))]),
        ("voxpopuli_ro", lambda: add_voxpopuli_ro(w)),
        ("csfleurs_ru_en", lambda: add_csfleurs_ru_en(w)),
    ]
    for name, fn in steps:
        before = len(w.rows)
        try:
            fn()
        except Exception as exc:  # one broken source must not cost the whole run
            print(f"!! {name} failed: {exc!r}", flush=True)
        print(f"{name}: +{len(w.rows) - before} rows", flush=True)
        sh(f"rm -rf {RAW}/hf")  # raw downloads are big; the FLAC copies are all we need
    write_outputs(w.rows)  # real speech is saved even if splicing fails below
    try:
        mono = [r for r in w.rows if r["source"] != "csfleurs_ru_en"]
        make_collage(align_bank(mono, per_lang=6000), w, COLLAGE_HOURS)
        write_outputs(w.rows)
    except Exception as exc:
        print(f"!! collage failed, manifests keep real speech only: {exc!r}", flush=True)


def write_outputs(rows: list[dict]) -> None:
    train, dev = split_dev(rows)
    for name, part in (("train", train), ("dev", dev)):
        with open(OUT / f"{name}.jsonl", "w", encoding="utf-8") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stats: dict[str, float] = {}
    for r in train:
        for key in (r["source"], "lang:" + r["lang"], "total"):
            stats[key] = stats.get(key, 0) + r["duration"] / 3600
    stats = {k: round(v, 1) for k, v in sorted(stats.items())}
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1))
    print(json.dumps(stats, indent=1), flush=True)


def selftest() -> None:
    m = np.ones(SR, dtype=np.float32) * 0.1
    d = np.ones(SR // 2, dtype=np.float32) * 0.5
    out = splice(m, (4000, 8000), d)
    assert abs(len(out) - (SR - 4000 + SR // 2 - 2 * FADE)) <= 1
    assert abs(float(np.sqrt(np.mean(out[6000:9000] ** 2))) - 0.1) < 0.01  # donor matched to matrix loudness
    assert clean_text("În parlament[ar] **Last week** ok", "rompar") == "În parlament Last week ok"
    assert align_word("Pacientul,", "ro", str) == "pacientul"
    assert align_word("și-a", "ro", str) == "sia"
    assert fit_phrase(["Кровотечения", "нет."], at_start=False, at_end=False) == ["кровотечения", "нет"]
    assert fit_phrase(["ECG", "today."], at_start=False, at_end=True) == ["ECG", "today."]
    rows = [{"audio_filepath": f"a{i}", "duration": 1} for i in range(1000)]
    train, dev = split_dev(rows + rows[:10])
    assert 0 < len(dev) < 40 and not {r["audio_filepath"] for r in dev} & {r["audio_filepath"] for r in train}
    print("selftest ok")


if __name__ == "__main__":
    if sys.argv[1:2] == ["selftest"]:
        selftest()
    else:
        main()
