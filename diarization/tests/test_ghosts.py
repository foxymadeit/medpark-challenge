import numpy as np

from diarizer.engine import ghost_remap
from diarizer.timeline import Turn


def _unit(v):
    v = np.asarray(v, dtype=np.float64)
    return v / np.linalg.norm(v)


A, B, C = _unit([1, 0, 0]), _unit([0, 1, 0]), _unit([0, 0, 1])


def _session(voices):
    """voices: [(speaker id, embedding, [turn durations])] -> turns, embs, ids."""
    turns, embs, ids, t = [], [], [], 0.0
    for sid, e, durs in voices:
        for d in durs:
            turns.append(Turn(sid, t, t + d))
            embs.append([e])
            ids.append([sid])
            t += d + 1.0
    return turns, embs, ids


def test_a_tiny_fragment_unlike_anyone_is_dropped():
    # team rec1: one real voice, plus a 2 s fragment in 2 turns that sounds like no one
    turns, embs, ids = _session([(2, A, [100.0, 200.0, 190.0]), (1, B, [0.9, 1.2])])
    assert ghost_remap(turns, embs, ids) == {1: None}


def test_a_tiny_fragment_that_sounds_like_a_speaker_joins_them():
    turns, embs, ids = _session([(1, A, [60.0]), (2, B, [50.0]), (3, _unit([1, 0.2, 0]), [1.5])])
    assert ghost_remap(turns, embs, ids) == {3: 1}


def test_a_quiet_but_distinct_person_is_kept():
    # three short "da" in a voice of their own: a participant, not a fragment
    turns, embs, ids = _session([(1, A, [60.0]), (2, B, [50.0]), (3, C, [0.8, 1.0, 0.9])])
    assert ghost_remap(turns, embs, ids) == {}


def test_an_enrolled_speaker_is_never_dropped():
    turns, embs, ids = _session([(1, A, [60.0]), (2, C, [1.0])])
    assert ghost_remap(turns, embs, ids, keep={2}) == {}


def test_the_main_speaker_is_never_a_ghost():
    turns, embs, ids = _session([(1, A, [1.0]), (2, B, [0.5])])
    assert 1 not in ghost_remap(turns, embs, ids)
