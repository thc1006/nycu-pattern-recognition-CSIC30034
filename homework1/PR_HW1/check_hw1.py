"""Checks pr_hw1.py against direct formulas, SciPy and scikit-learn.

Run from the repository root:  uv run homework1/PR_HW1/check_hw1.py
"""
import numpy as np
from scipy.linalg import eigh, subspace_angles
from sklearn.neighbors import KNeighborsClassifier

import pr_hw1 as hw

rng = np.random.default_rng(7)
y3 = lambda n: np.repeat(np.arange(3), n)


def direct_md2(x, y, q, ridge=0.0):
    out = []
    for c in range(3):
        xc = x[y == c]
        s = np.cov(xc, rowvar=False, bias=True) + ridge * np.eye(x.shape[1])
        inv = np.linalg.pinv(s, rcond=hw.RTOL, hermitian=True)  # inv(s) when s is invertible
        out.append(np.einsum("ij,jk,ik->i", q - xc.mean(0), inv, q - xc.mean(0)))
    return np.array(out)


# Mahalanobis distances: invertible, singular, and with a covariance ridge.
for n, d in ((40, 5), (40, 60), (12, 30)):
    x, q = rng.normal(size=(3 * n, d)), rng.normal(size=(50, d))
    for ridge in (0.0, 0.1):
        got, ref = hw.md_dist2(hw.md_fit(x, y3(n)), q, ridge), direct_md2(x, y3(n), q, ridge)
        assert np.allclose(got, ref, rtol=1e-6, atol=1e-8), (n, d, ridge)
print("Mahalanobis distance matches pinv formula: ok")

# Invertible case: predictions do not change under x -> A x + b.
x, q = rng.normal(size=(120, 6)), rng.normal(size=(80, 6))
a, b = rng.normal(size=(6, 6)) + 3 * np.eye(6), rng.normal(size=6)
p1 = hw.md_predict(hw.md_fit(x, y3(40)), q)
p2 = hw.md_predict(hw.md_fit(x @ a.T + b, y3(40)), q @ a.T + b)
assert np.array_equal(p1, p2)
print("affine invariance of the Mahalanobis classifier: ok")

# Singular case: every training point sits at squared distance n_c - 1 from its own class mean.
x = rng.normal(size=(60, 50))
model = hw.md_fit(x, y3(20))
own = hw.md_dist2(model, x)[y3(20), np.arange(60)]
assert np.allclose(own, 19.0)
print("pinv distance of a training point to its own class = n_c - 1: ok")

# Ranks: class covariance n_c - 1, PCA covariance N - 1, within-class scatter N - C.
x = rng.normal(size=(60, 103))
assert np.count_nonzero(hw.eig_desc(hw.cov(x[:20]))[0]) == 19
assert np.count_nonzero(hw.pca_fit(x)[1]) == 59
sw = sum(hw.cov(x[y3(20) == c]) / 3 for c in range(3))
assert np.count_nonzero(hw.eig_desc(sw)[0]) == 57
print("ranks 19 / 59 / 57 for n_c = 20, N = 60, d = 103: ok")

# PCA whitening: identity covariance; with ridge, diag(lambda / (lambda + gamma)).
x = rng.normal(size=(200, 8)) @ rng.normal(size=(8, 8))
mu, lam, v = hw.pca_fit(x)
for gamma in (0.0, 0.5):
    z = (x - mu) @ v / np.sqrt(lam + gamma)
    assert np.allclose(hw.cov(z), np.diag(lam / (lam + gamma)), atol=1e-10)
print("PCA whitening covariance with and without ridge: ok")

# LDA: same subspace as SciPy's generalized symmetric eigensolver.
x = rng.normal(size=(150, 10)) + np.repeat(rng.normal(size=(3, 10)), 50, axis=0)
y = y3(50)
sw = sum(hw.cov(x[y == c]) / 3 for c in range(3))
sb = sum(np.outer(x[y == c].mean(0) - x.mean(0), x[y == c].mean(0) - x.mean(0)) / 3 for c in range(3))
for gamma in (0.0, 0.1, 1.0):
    _, w = hw.lda_fit(x, y, gamma)
    _, vecs = eigh(sb, sw + gamma * np.eye(10))
    assert np.max(subspace_angles(w, vecs[:, -2:])) < 1e-8
print("LDA subspace matches scipy.linalg.eigh(S_b, S_w + gamma I): ok")

# Singular S_w (more dimensions than N - C): gamma = 0 must match the pseudo-inverse solution.
x = rng.normal(size=(30, 40)) + np.repeat(rng.normal(size=(3, 40)), 10, axis=0)
y = y3(10)
sw = sum(hw.cov(x[y == c]) / 3 for c in range(3))
sb = sum(np.outer(x[y == c].mean(0) - x.mean(0), x[y == c].mean(0) - x.mean(0)) / 3 for c in range(3))
vals, vecs = np.linalg.eig(np.linalg.pinv(sw, rcond=hw.RTOL, hermitian=True) @ sb)
top = vecs[:, np.argsort(vals.real)[::-1][:2]].real
assert np.max(subspace_angles(hw.lda_fit(x, y, 0.0)[1], top)) < 1e-6
print("LDA with singular S_w matches the pseudo-inverse solution: ok")

# 1-NN on every prefix of the columns, against scikit-learn.
x, q = rng.normal(size=(90, 7)), rng.normal(size=(40, 7))
yq = rng.integers(0, 3, 40)
curve = hw.nn_curve(x, y3(30), q, yq)
for k in range(1, 8):
    knn = KNeighborsClassifier(n_neighbors=1).fit(x[:, :k], y3(30))
    assert curve[k - 1, 0] == 1.0
    assert curve[k - 1, 2] == knn.score(q[:, :k], yq)
    d = ((x[:, None, :k] - x[None, :, :k]) ** 2).sum(-1) + np.diag(np.full(90, np.inf))
    assert curve[k - 1, 1] == np.mean(y3(30)[d.argmin(1)] == y3(30))
print("1-NN prefix curves and leave-one-out match direct computation: ok")

# Splits: stratified, disjoint, nested; normalization uses training rows only.
signal, y, noise = hw.synthetic(0)
tr50, te50 = hw.split(y, 0, 0.5)
tr20, te20 = hw.split(y, 0, 0.2)
assert np.bincount(y[tr50]).tolist() == [50] * 3 and np.bincount(y[tr20]).tolist() == [20] * 3
assert not np.intersect1d(tr50, te50).size and set(tr20) <= set(tr50)
moved = signal.copy()
moved[te50] += 1e3
assert np.array_equal(hw.features(signal, noise, 0.5, tr50, True)[tr50],
                      hw.features(moved, noise, 0.5, tr50, True)[tr50])
print("stratified nested splits, training-only normalization: ok")

# Generator: class means and covariance pooled over the 20 repetitions.
data = [hw.synthetic(r) for r in range(hw.REPEATS)]
sig = np.vstack([d[0] for d in data])
lab = np.concatenate([d[1] for d in data])
noise = np.vstack([d[2] for d in data]) * np.sqrt(hw.NOISE_VAR)
assert np.abs(np.array([sig[lab == c].mean(0) for c in range(3)]) - hw.MEANS).max() < 0.1
assert np.abs(sum(hw.cov(sig[lab == c]) for c in range(3)) / 3 - hw.SIGMA).max() < 0.1
assert abs(noise.var() - hw.NOISE_VAR) < 0.01
print("generator moments (6000 samples): ok")
