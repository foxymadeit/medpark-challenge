from asr_llm.batching import AudioBatch, assign_speakers, pack_batches
import numpy as np


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


def test_assign_speakers_by_overlap():
    samples = np.zeros(1600, dtype=np.float32)
    batches = [
        AudioBatch(0, 0.0, 2.0, samples),
        AudioBatch(1, 2.0, 4.0, samples),
    ]
    turns = [
        {"speaker": "Speaker 1", "start": 0.0, "end": 2.5},
        {"speaker": "Speaker 2", "start": 2.5, "end": 5.0},
    ]
    assert assign_speakers(batches, turns) == ["Speaker 1", "Speaker 2"]
