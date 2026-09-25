import numpy as np
import pytest

from diarizer.tracker import SpeakerTracker

DIM = 64


def unit(v):
    return v / np.linalg.norm(v)


@pytest.fixture
def voices():
    rng = np.random.default_rng(7)
    return [unit(rng.standard_normal(DIM)) for _ in range(4)]


def sample(voice, rng, noise=0.4):
    # Same-voice samples land around cosine 0.85-0.95, different voices near 0.
    return unit(voice + noise * rng.standard_normal(DIM) / np.sqrt(DIM))


@pytest.fixture
def rng():
    return np.random.default_rng(11)


def test_first_voice_becomes_speaker_1(voices, rng):
    t = SpeakerTracker()
    assert t.assign([sample(voices[0], rng)], [True]) == [1]


def test_returning_voice_gets_its_old_label(voices, rng):
    t = SpeakerTracker()
    a, b, c = voices[:3]
    order = [a, b, a, c, b, a]
    got = [t.assign([sample(v, rng)], [True])[0] for v in order]
    assert got == [1, 2, 1, 3, 2, 1]


def test_unknown_voice_without_enough_audio_is_not_created(voices, rng):
    t = SpeakerTracker()
    assert t.assign([sample(voices[0], rng)], [False]) == [None]
    assert t.speakers == []


def test_speaker_cap_forces_nearest(voices, rng):
    t = SpeakerTracker(max_speakers=2)
    t.assign([sample(voices[0], rng)], [True])
    t.assign([sample(voices[1], rng)], [True])
    third = t.assign([sample(voices[2], rng)], [True])[0]
    assert third in (1, 2)
    assert len(t.speakers) == 2


def test_enrolled_voice_is_named(voices, rng):
    t = SpeakerTracker()
    sid = t.enroll("Ana", [sample(voices[0], rng) for _ in range(3)])
    assert t.assign([sample(voices[0], rng)], [True]) == [sid]
    assert t.label(sid) == "Ana"
    other = t.assign([sample(voices[1], rng)], [True])[0]
    assert other != sid
    assert t.label(other) == "Speaker 2"


def test_two_local_speakers_never_share_a_label(voices, rng):
    t = SpeakerTracker()
    t.assign([sample(voices[0], rng)], [True])
    t.assign([sample(voices[1], rng)], [True])
    got = t.assign([sample(voices[1], rng), sample(voices[0], rng)], [True, True])
    assert got == [2, 1]


def test_split_of_one_voice_does_not_mint_a_phantom(voices, rng):
    # The segmenter sometimes splits one person into two local speakers.
    t = SpeakerTracker()
    t.assign([sample(voices[0], rng)], [True])
    got = t.assign([sample(voices[0], rng), sample(voices[0], rng)], [True, True])
    assert sorted(got, key=str) == [1, None]
    assert len(t.speakers) == 1


def test_merge_pass_folds_duplicates_into_older_id(voices, rng):
    t = SpeakerTracker(assign=0.99, new=0.99)  # force a duplicate speaker
    t.assign([sample(voices[0], rng)], [True])
    t.assign([sample(voices[0], rng)], [True])
    assert len(t.speakers) == 2
    remap = t.merge_pass(threshold=0.7)
    assert remap == {2: 1}
    assert t.resolve(2) == 1
    assert [s.id for s in t.speakers] == [1]


def test_second_prototype_helps_a_shifted_voice(voices, rng):
    # A speaker switching language drifts away from the centroid; a stored
    # prototype of the shifted voice should keep matching it.
    t = SpeakerTracker(assign=0.5, proto_novelty=0.9)
    v = voices[0]
    shifted = unit(v + 0.9 * voices[3])
    t.assign([v], [True])
    t.assign([shifted], [True])
    spk = t.speakers[0]
    assert len(spk.protos) == 2
    probe = unit(shifted + 0.05 * voices[2])
    assert t.similarity(probe, spk) > float(probe @ spk.centroid)
