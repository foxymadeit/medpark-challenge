from asr_llm.batching import pack_batches
from asr_llm.local import require_local_path
import numpy as np
import pytest
from pathlib import Path


def test_pack_merges_short_gaps():
    sr = 16_000
    audio = np.zeros(sr * 10, dtype=np.float32)
    spans = [(0.0, 1.0), (1.2, 2.0), (8.0, 9.0)]
    batches = pack_batches(audio, spans, sample_rate=sr, max_batch_s=30.0, merge_gap_s=0.4)
    assert len(batches) == 2
    assert batches[0].start == 0.0
    assert batches[0].end == 2.0
    assert batches[1].start == 8.0


def test_pack_splits_long_span():
    sr = 16_000
    audio = np.zeros(sr * 70, dtype=np.float32)
    batches = pack_batches(audio, [(0.0, 65.0)], sample_rate=sr, max_batch_s=30.0, merge_gap_s=0.4)
    assert len(batches) == 3
    assert batches[0].end - batches[0].start == 30.0
    assert batches[-1].end == 65.0


def test_require_local_path_rejects_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="offline"):
        require_local_path(tmp_path / "missing-model", "Whisper model dir")
