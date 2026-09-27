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


def test_no_upper_limit_on_speakers():
    # 100 people take turns, then each speaks again in random order.
    rng = np.random.default_rng(3)
    dim = 512
    people = [unit(rng.standard_normal(dim)) for _ in range(100)]
    noisy = lambda v: unit(v + 0.4 * rng.standard_normal(dim) / np.sqrt(dim))  # noqa: E731
    t = SpeakerTracker()
    first = [t.assign([noisy(p)], [True])[0] for p in people]
    assert first == list(range(1, 101))
    for i in rng.permutation(100):
        assert t.assign([noisy(people[i])], [True]) == [i + 1]
    assert len(t.speakers) == 100


def test_newcomer_who_sounds_a_bit_like_someone_is_founded_from_a_group():
    # B's single voiceprints score ~0.3 against A: too close to found a
    # speaker alone (new=0.25), too far to count as A (assign=0.4).
    rng = np.random.default_rng(5)
    a = unit(rng.standard_normal(DIM))
    r = rng.standard_normal(DIM)
    ortho = unit(r - (a @ r) * a)
    b = unit(0.3 * a + 0.95 * ortho)
    near = lambda v: unit(v + 0.15 * rng.standard_normal(DIM) / np.sqrt(DIM))  # noqa: E731
    t = SpeakerTracker(assign=0.4, new=0.25, pending_min=4)
    for _ in range(5):
        t.assign([near(a)], [True])
    got = [t.assign([near(b)], [True])[0] for _ in range(8)]
    assert len(t.speakers) == 2
    assert got[-1] == 2  # once founded, B keeps its own label


def test_renamed_voice_keeps_normal_matching_and_survives_a_merge():
    from diarizer.tracker import SpeakerTracker
    import numpy as np
    t = SpeakerTracker(assign=0.5, new=0.3)
    a = np.array([1.0, 0, 0, 0]); b = np.array([0.95, 0.31, 0, 0])
    sid = t.assign([a], [True])[0]
    t.rename(sid, "Dr. Ana Popescu")
    assert t.label(sid) == "Dr. Ana Popescu"
    assert t.assign([b], [True])[0] == sid  # 0.95 similar: same person, no stricter enrolled threshold
    other = t._create(np.array([0.99, 0.14, 0, 0]))
    t._absorb(t._by_id(other.id), t._by_id(sid))
    assert t.label(sid) == "Dr. Ana Popescu"
