import json
from pathlib import Path

from asr_llm.batching import pack_batches
from asr_llm.diarization import load_turns, speaker_for, split_at_turns

import numpy as np

TURNS = [(0.0, 3.0, "Speaker 1"), (3.0, 8.0, "Speaker 2"), (8.2, 12.0, "Speaker 1")]


def test_span_is_cut_where_the_speaker_changes():
    assert split_at_turns([(1.0, 6.0)], TURNS) == [(1.0, 3.0), (3.0, 6.0)]


def test_no_slivers_near_span_edges():
    assert split_at_turns([(2.8, 7.0)], TURNS) == [(2.8, 7.0)]


def test_speaker_is_largest_overlap():
    assert speaker_for(1.0, 3.0, TURNS) == "Speaker 1"
    assert speaker_for(2.5, 7.0, TURNS) == "Speaker 2"
    assert speaker_for(20.0, 21.0, TURNS) is None


def test_cut_pieces_are_not_glued_back():
    audio = np.zeros(16_000 * 10, dtype=np.float32)
    batches = pack_batches(audio, [(1.0, 3.0), (3.0, 6.0)], merge_gap_s=0.0)
    assert [(b.start, b.end) for b in batches] == [(1.0, 3.0), (3.0, 6.0)]


def test_load_diarizer_session(tmp_path: Path):
    src = tmp_path / "s.json"
    src.write_text(json.dumps({"turns": [{"speaker": "Dr. A", "start": 0, "end": 2.5, "start_clock": "x"}]}))
    assert load_turns(src) == [(0.0, 2.5, "Dr. A")]
