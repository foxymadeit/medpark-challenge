import numpy as np

from diarizer.refine import refine

DIM = 32


def unit(v):
    return v / np.linalg.norm(v)


def test_early_mistake_is_fixed_by_final_centroids():
    rng = np.random.default_rng(1)
    a, b = unit(rng.standard_normal(DIM)), unit(rng.standard_normal(DIM))
    noisy = lambda v: unit(v + 0.3 * rng.standard_normal(DIM) / np.sqrt(DIM))  # noqa: E731
    # Online, the first B observation was glued to speaker 1 before B existed.
    history = [([noisy(a)], [1]), ([noisy(b)], [1])] + \
              [([noisy(a)], [1]) for _ in range(5)] + [([noisy(b)], [2]) for _ in range(5)]
    new_ids = refine([e for e, _ in history], [i for _, i in history], new_th=0.3)
    assert new_ids[1] == [2]
    assert all(ids == [1] for ids in new_ids[2:7])
    assert all(ids == [2] for ids in new_ids[7:])


def test_locals_in_one_window_stay_distinct():
    rng = np.random.default_rng(2)
    a, b = unit(rng.standard_normal(DIM)), unit(rng.standard_normal(DIM))
    embs = [[a, b]] * 3
    ids = [[1, 2]] * 3
    assert refine(embs, ids, new_th=0.3) == [[1, 2]] * 3


def test_unlabelled_local_gets_a_label_when_close_enough():
    rng = np.random.default_rng(3)
    a = unit(rng.standard_normal(DIM))
    embs = [[a], [a], [unit(a + 0.1 * rng.standard_normal(DIM))]]
    assert refine(embs, [[1], [1], [None]], new_th=0.3) == [[1], [1], [1]]


def test_far_away_unlabelled_local_stays_unlabelled():
    rng = np.random.default_rng(4)
    a, far = unit(rng.standard_normal(DIM)), unit(rng.standard_normal(DIM))
    assert refine([[a], [far]], [[1], [None]], new_th=0.5) == [[1], [None]]


def test_silent_windows_are_skipped():
    a = unit(np.ones(DIM))
    assert refine([[a], [], [a]], [[1], [], [1]], new_th=0.3) == [[1], [], [1]]
