"""Learned projection applied to voice embeddings before comparing them.

Trained on labelled meetings (the same person heard in several rooms), it
keeps the directions that tell people apart and shrinks the ones that only
say "this is the far corner of room B": LDA, then within-speaker whitening
(WCCN), then length normalisation. At runtime it is one small matrix product.
"""

from pathlib import Path

import numpy as np


class Backend:
    def __init__(self, mean: np.ndarray, proj: np.ndarray):
        self.mean = np.asarray(mean, dtype=np.float32)
        self.proj = np.asarray(proj, dtype=np.float32)

    def __call__(self, X) -> np.ndarray:
        Y = (np.asarray(X, dtype=np.float32) - self.mean) @ self.proj
        return Y / (np.linalg.norm(Y, axis=-1, keepdims=True) + 1e-9)

    def save(self, path) -> None:
        np.savez(path, mean=self.mean, proj=self.proj)

    @classmethod
    def load(cls, path) -> "Backend":
        d = np.load(Path(path))
        return cls(d["mean"], d["proj"])


def fit_lda_wccn(X, y, dim: int, shrink: float = 1e-3) -> Backend:
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y)
    mean = X.mean(axis=0)
    Xc = X - mean
    classes = np.unique(y)
    Sw = np.zeros((X.shape[1],) * 2)
    Sb = np.zeros_like(Sw)
    for c in classes:
        Xi = Xc[y == c]
        mu = Xi.mean(axis=0)
        D = Xi - mu
        Sw += D.T @ D
        Sb += len(Xi) * np.outer(mu, mu)
    Sw /= len(X)
    Sb /= len(X)
    Sw += shrink * np.trace(Sw) / len(Sw) * np.eye(len(Sw))
    # Generalised eigenproblem Sb v = w Sw v via Sw^-1/2 whitening.
    ew, V = np.linalg.eigh(Sw)
    W = V @ np.diag(ew ** -0.5) @ V.T
    eb, U = np.linalg.eigh(W @ Sb @ W)
    lda = W @ U[:, np.argsort(eb)[::-1][:dim]]
    # WCCN: whiten what is left of the within-speaker spread.
    Z = Xc @ lda
    Sw2 = sum(np.cov(Z[y == c].T, bias=True) * (y == c).sum() for c in classes) / len(Z)
    e2, V2 = np.linalg.eigh(Sw2 + shrink * np.eye(dim))
    return Backend(mean, lda @ V2 @ np.diag(e2 ** -0.5) @ V2.T)
