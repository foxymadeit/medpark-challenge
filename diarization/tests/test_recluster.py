import numpy as np

from diarizer.recluster import recluster

DIM = 48


def unit(v):
    return v / np.linalg.norm(v)


def voices(n, seed=0):
    rng = np.random.default_rng(seed)
    return [unit(rng.standard_normal(DIM)) for _ in range(n)], rng


def noisy(v, rng, s=0.3):
    return unit(v + s * rng.standard_normal(DIM) / np.sqrt(DIM))


def run(sequence, online, **kw):
    """sequence: true voice per step; online: the online id given at that step."""
    embs = [[e] for e in sequence]
    ids = [[i] for i in online]
    durs = [[0.5] for _ in sequence]
    return [row[0] for row in recluster(embs, ids, durs, **kw)]


def test_speaker_hidden_inside_another_is_recovered():
    (a, b), rng = voices(2)
    seq = [noisy(a, rng) for _ in range(20)] + [noisy(b, rng) for _ in range(20)]
    online = [1] * 40  # online glued B onto A
    out = run(seq, online, threshold=0.5)
    assert len(set(out[:20])) == 1 and len(set(out[20:])) == 1
    assert out[0] != out[20]
    assert out[0] == 1  # keeps the online number where it matches


def test_one_person_split_in_two_is_joined():
    (a,), rng = voices(1)
    seq = [noisy(a, rng) for _ in range(30)]
    online = [1] * 15 + [3] * 15
    assert set(run(seq, online, threshold=0.5)) == {1}


def test_tiny_phantom_cluster_is_folded_into_nearest():
    (a, b), rng = voices(2, seed=5)
    odd = unit(a + 0.8 * voices(1, seed=9)[0][0])  # one odd-sounding moment of A
    seq = [noisy(a, rng) for _ in range(20)] + [odd] + [noisy(b, rng) for _ in range(20)]
    online = [1] * 20 + [7] + [2] * 20
    out = run(seq, online, threshold=0.8, min_speaker_s=2.0)
    assert out[20] == 1
    assert set(out) == {1, 2}


def test_max_speakers_caps_the_count():
    vs, rng = voices(4, seed=3)
    seq = [noisy(v, rng) for v in vs for _ in range(10)]
    online = [i + 1 for i in range(4) for _ in range(10)]
    assert len(set(run(seq, online, threshold=0.5, max_speakers=2))) == 2


def test_unlabelled_steps_stay_unlabelled():
    (a,), rng = voices(1)
    out = run([noisy(a, rng), noisy(a, rng)], [1, None], threshold=0.5)
    assert out == [1, None]
