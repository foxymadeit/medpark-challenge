import numpy as np

from eval.make_mix import SR, build_meeting


def test_reference_turns_match_the_audio_they_describe():
    rng = np.random.default_rng(0)
    voices = {name: [np.full(int(2 * SR), 0.1 * (i + 1), np.float32)] for i, name in enumerate(["ro_a", "ru_b", "bi_c"])}
    audio, ref = build_meeting(voices, rng, minutes=1.0, overlap=0.2)
    assert {w for w, _, _ in ref} == set(voices)
    assert all(e > s for _, s, e in ref)
    assert ref[-1][2] <= len(audio) / SR
    assert all(b[1] >= 0 for b in ref)
    # every labelled turn has sound under it, and turns never repeat the same speaker back to back
    assert all(np.abs(audio[int(s * SR):int(e * SR)]).mean() > 0.01 for _, s, e in ref)
    assert all(x[0] != y[0] for x, y in zip(ref, ref[1:]))


def test_some_turns_overlap_the_previous_one():
    rng = np.random.default_rng(1)
    voices = {n: [np.ones(SR * 3, np.float32)] for n in ("a", "b", "c", "d")}
    _, ref = build_meeting(voices, rng, minutes=3.0, overlap=0.3)
    overlaps = sum(b[1] < a[2] for a, b in zip(ref, ref[1:]))
    assert 0.1 < overlaps / len(ref) < 0.5
