"""Pure pieces of the data build: text cleanup, splicing, dev split. numpy only."""

from __future__ import annotations

import random
import re
import unicodedata

import numpy as np

SR = 16_000
MIN_S, MAX_S = 0.5, 20.0
FADE = int(0.02 * SR)
SEED = 1234

# Direction weights for spliced items: matrix language -> inserted language.
DIRECTIONS = [("ro", "ru", 0.50), ("ro", "en", 0.20), ("ru", "ro", 0.15), ("ru", "en", 0.15)]


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


def to_16k(data: np.ndarray, sr: int) -> np.ndarray:
    if data.ndim > 1:
        data = data.mean(axis=1)
    if sr != SR:
        from math import gcd

        from scipy.signal import resample_poly

        g = gcd(SR, sr)
        data = resample_poly(data, SR // g, sr // g)
    return data.astype(np.float32)


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


def plan_splice(rng: random.Random, n_matrix: int, n_donor: int) -> tuple[int, int, int, int]:
    """(i, k, j, n): replace matrix words [i, i+k) by donor words [j, j+n).

    Needs n_matrix >= 3 and n_donor >= 1. At most 4 words either way, never the
    first matrix word, never the whole sentence.
    """
    k = rng.randint(1, min(4, n_matrix - 2))
    i = rng.randint(1, n_matrix - k)
    n = rng.randint(1, min(4, n_donor))
    j = rng.randint(0, n_donor - n)
    return i, k, j, n


def usable_directions(bank_sizes: dict[str, int]) -> list[tuple[str, str, float]]:
    """DIRECTIONS whose two languages both have aligned sentences (a partial build may lack one)."""
    return [d for d in DIRECTIONS if bank_sizes.get(d[0]) and bank_sizes.get(d[1])]


def split_dev(rows: list[dict], frac: float = 0.01) -> tuple[list[dict], list[dict]]:
    """Dev keys are unique files; a file weighted x2 in train never leaks into dev."""
    rng = random.Random(SEED)
    uniq = {r["audio_filepath"]: r for r in rows}
    dev_keys = {k for k in uniq if rng.random() < frac}
    train = [r for r in rows if r["audio_filepath"] not in dev_keys]
    dev = [uniq[k] for k in sorted(dev_keys)]
    return train, dev


def hour_stats(rows: list[dict]) -> dict[str, float]:
    stats: dict[str, float] = {}
    for r in rows:
        for key in (r["source"], "lang:" + r["lang"], "total"):
            stats[key] = stats.get(key, 0) + r["duration"] / 3600
    return {k: round(v, 2) for k, v in sorted(stats.items())}
