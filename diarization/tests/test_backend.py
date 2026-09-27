import numpy as np

from diarizer.backend import Backend, fit_lda_wccn


def dprime(E, labels):
    S = E @ E.T
    same = labels[:, None] == labels[None, :]
    iu = np.triu_indices(len(E), 1)
    a, b = S[iu][same[iu]], S[iu][~same[iu]]
    return (a.mean() - b.mean()) / np.sqrt((a.var() + b.var()) / 2)


def synthetic(n_spk=40, per=20, dim=32, seed=0):
    """Speaker identity lives in dims 0-7; a strong 'room' offset lives in
    dims 8-15 and swamps it, like far-field meeting audio. New seeds bring
    new speakers and new rooms, but rooms always vary in the same subspace."""
    rng = np.random.default_rng(seed)
    spk = rng.standard_normal((n_spk, dim)) * np.r_[np.ones(8), np.zeros(dim - 8)]
    rooms = rng.standard_normal((6, dim)) * np.r_[np.zeros(8), np.ones(8), np.zeros(dim - 16)] * 3.0
    X, y = [], []
    for s in range(n_spk):
        for _ in range(per):
            v = spk[s] + rooms[rng.integers(6)] + 0.3 * rng.standard_normal(dim)
            X.append(v / np.linalg.norm(v))
            y.append(s)
    return np.array(X), np.array(y)


def test_projection_separates_speakers_better_than_raw():
    X, y = synthetic()
    Xt, yt = synthetic(seed=1)  # unseen speakers and rooms
    backend = fit_lda_wccn(X, y, dim=8)
    assert dprime(backend(Xt), yt) > dprime(Xt, yt) + 1.0


def test_backend_round_trips_through_a_file(tmp_path):
    X, y = synthetic()
    b = fit_lda_wccn(X, y, dim=10)
    b.save(tmp_path / "b.npz")
    b2 = Backend.load(tmp_path / "b.npz")
    np.testing.assert_allclose(b(X[:5]), b2(X[:5]), rtol=1e-5)
    assert np.allclose(np.linalg.norm(b2(X[:5]), axis=1), 1.0)
