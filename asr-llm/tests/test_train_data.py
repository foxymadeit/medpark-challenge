import random

import numpy as np
import pytest

from asr_train.build_data import parse_args
from asr_train.collage import (
    DIRECTIONS,
    FADE,
    SR,
    align_word,
    clean_text,
    fit_phrase,
    hour_stats,
    plan_splice,
    splice,
    split_dev,
    usable_directions,
)
from asr_train.hub import Hub


def test_splice_keeps_length_and_matches_loudness():
    matrix = np.ones(SR, dtype=np.float32) * 0.1
    donor = np.ones(SR // 2, dtype=np.float32) * 0.5
    out = splice(matrix, (4000, 8000), donor)
    assert abs(len(out) - (SR - 4000 + SR // 2 - 2 * FADE)) <= 1
    assert abs(float(np.sqrt(np.mean(out[6000:9000] ** 2))) - 0.1) < 0.01  # donor matched to matrix loudness


def test_text_helpers():
    assert clean_text("În parlament[ar] **Last week** ok", "rompar") == "În parlament Last week ok"
    assert align_word("Pacientul,", "ro", str) == "pacientul"
    assert align_word("și-a", "ro", str) == "sia"
    assert fit_phrase(["Кровотечения", "нет."], at_start=False, at_end=False) == ["кровотечения", "нет"]
    assert fit_phrase(["ECG", "today."], at_start=False, at_end=True) == ["ECG", "today."]


def test_dev_split_never_leaks_a_weighted_file():
    rows = [{"audio_filepath": f"a{i}", "duration": 1} for i in range(1000)]
    train, dev = split_dev(rows + rows[:10])  # first ten weighted x2, as ROMPAR is
    assert 0 < len(dev) < 40
    assert not {r["audio_filepath"] for r in dev} & {r["audio_filepath"] for r in train}


@pytest.mark.parametrize("n_matrix,n_donor", [(3, 1), (4, 4), (12, 2), (30, 30)])
def test_plan_splice_stays_inside_both_sentences(n_matrix, n_donor):
    rng = random.Random(0)
    for _ in range(500):
        i, k, j, n = plan_splice(rng, n_matrix, n_donor)
        assert 1 <= i and 1 <= k <= 4 and i + k <= n_matrix and k < n_matrix
        assert 1 <= n <= 4 and 0 <= j and j + n <= n_donor


def test_collage_skips_pairs_a_partial_build_lacks():
    assert usable_directions({"ro": 5, "ru": 5, "en": 5}) == DIRECTIONS
    assert [(m, i) for m, i, _ in usable_directions({"ro": 5, "ru": 5, "en": 0})] == [("ro", "ru"), ("ru", "ro")]
    assert usable_directions({"ro": 5}) == []


def test_hour_stats():
    rows = [{"source": "fleurs_ro", "lang": "ro", "duration": 1800}, {"source": "collage", "lang": "ro+ru", "duration": 1800}]
    assert hour_stats(rows) == {"collage": 0.5, "fleurs_ro": 0.5, "lang:ro": 0.5, "lang:ro+ru": 0.5, "total": 1.0}


def test_hub_mirror_lists_and_resolves_without_network(tmp_path):
    root = tmp_path / "fixie-ai" / "common_voice_17_0"
    for rel in ("ro/test/0.parquet", "ro/train/1.parquet", "ro/train/0.parquet", "ro/train/notes.txt"):
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(b"")
    hub = Hub(mirror=tmp_path)
    assert hub.list("fixie-ai/common_voice_17_0", "ro/train/") == ["ro/train/0.parquet", "ro/train/1.parquet"]
    assert hub.file("fixie-ai/common_voice_17_0", "ro/test/0.parquet") == root / "ro/test/0.parquet"
    with pytest.raises(FileNotFoundError, match="not in mirror"):
        hub.file("google/fleurs", "data/ro_ro/train.tsv")


def test_build_args(tmp_path):
    args = parse_args(["--out", str(tmp_path), "--sources", "fleurs, cv_ro"])
    assert args.sources == ["fleurs", "cv_ro"] and args.collage_hours == 30.0
    with pytest.raises(SystemExit):
        parse_args(["--out", str(tmp_path), "--sources", "nope"])
    with pytest.raises(SystemExit):  # never prunes the shared HF cache
        parse_args(["--out", str(tmp_path), "--prune-raw"])


def test_writer_writes_flac_and_weights_rows(tmp_path):
    pytest.importorskip("soundfile")
    from asr_train.build_data import Writer

    w = Writer(tmp_path)
    assert w.add(np.zeros(SR // 10, dtype=np.float32), "prea scurt", "ro", "t") is None  # under 0.5 s
    row = w.add(np.zeros(SR, dtype=np.float32), "Bună ziua.", "ro", "t", weight=2)
    assert (tmp_path / row["audio_filepath"]).exists()
    assert w.rows == [row, row]
