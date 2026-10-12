"""Pattern Recognition HW1 (NYCU, Fall 2026): experiments with linear feature spaces.

Run from the repository root (the environment is pinned by uv):
    uv run homework1/PR_HW1/pr_hw1.py               # experiments, then figures
    uv run homework1/PR_HW1/pr_hw1.py --plots-only  # figures from saved results
"""
import argparse
import json
import os
import platform
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# One BLAS thread per worker; the parallelism comes from the process pool.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np
import scipy
import sklearn
from sklearn.datasets import load_iris

HERE = Path(__file__).resolve().parent
SEED = 20261012
REPEATS = 20
FRACTIONS = (0.5, 0.2)  # share of each class used for training
N_NOISE = 100
GAMMAS = (0.0, 0.01, 0.1, 1.0, 10.0)
IRIS_VARS = (0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0)
MEANS = np.array([[2.0, 2.0, 0.0], [-2.0, 2.0, 0.0], [0.0, -2.0, 0.0]])
SIGMA = np.array([[1.0, 0.6, 0.0], [0.6, 1.5, 0.0], [0.0, 0.0, 0.5]])
NOISE_VAR = 0.5
RTOL = 1e-12  # eigenvalues below RTOL * largest count as zero (real ones sit above 1e-10, round-off below 1e-14)


# ---------------------------------------------------------------- data

def synthetic(rep):
    """Signal (300 x 3), labels, and a 300 x 100 standard-normal noise block."""
    rng = np.random.default_rng([SEED, rep, 1])
    y = np.repeat(np.arange(3), 100)
    signal = MEANS[y] + rng.standard_normal((300, 3)) @ np.linalg.cholesky(SIGMA).T
    return signal, y, rng.standard_normal((300, N_NOISE))


def iris_noise(rep):
    return np.random.default_rng([SEED, rep, 3]).standard_normal((150, N_NOISE))


def split(y, rep, fraction):
    """Stratified split. Both fractions use the same permutation, so the 20% set lies inside the 50% set."""
    rng = np.random.default_rng([SEED, rep, 2, len(y)])
    train = [rng.permutation(np.flatnonzero(y == c)) for c in np.unique(y)]
    train = np.sort(np.concatenate([t[:round(fraction * len(t))] for t in train]))
    return train, np.setdiff1d(np.arange(len(y)), train)


def features(signal, noise, var, train, normalize=False):
    """Signal columns, z-scored with training statistics if asked, followed by noise of variance var."""
    if normalize:
        signal = (signal - signal[train].mean(0)) / signal[train].std(0)
    return np.hstack([signal, np.sqrt(var) * noise])


# ---------------------------------------------------------------- linear algebra

def cov(x):
    z = x - x.mean(0)
    return z.T @ z / len(x)


def eig_desc(s):
    """Eigenpairs of a symmetric PSD matrix, largest first, with numerical zeros set to 0."""
    lam, v = np.linalg.eigh(s)
    lam, v = lam[::-1], v[:, ::-1]
    return np.where(lam > RTOL * lam[0], lam, 0.0), v


# ---------------------------------------------------------------- classifiers

def nn_curve(xtr, ytr, xte, yte):
    """1-NN accuracy on the first 1..D columns. Columns: train, train leave-one-out, test."""
    dtr = np.zeros((len(xtr), len(xtr)))
    dte = np.zeros((len(xte), len(xtr)))
    no_self = np.diag(np.full(len(xtr), np.inf))
    out = np.empty((xtr.shape[1], 3))
    for j in range(xtr.shape[1]):
        dtr += (xtr[:, None, j] - xtr[None, :, j]) ** 2
        dte += (xte[:, None, j] - xtr[None, :, j]) ** 2
        out[j] = (np.mean(ytr[dtr.argmin(1)] == ytr),
                  np.mean(ytr[(dtr + no_self).argmin(1)] == ytr),
                  np.mean(ytr[dte.argmin(1)] == yte))
    return out


def md_fit(x, y):
    """Class means and eigendecompositions of the class covariances (ML, divided by n_c)."""
    return [(x[y == c].mean(0), *eig_desc(cov(x[y == c]))) for c in np.unique(y)]


def md_dist2(model, q, ridge=0.0):
    """Squared Mahalanobis distance to each class mean (classes x queries).

    A singular covariance uses its pseudo-inverse, i.e. directions with zero variance are ignored.
    """
    d2 = []
    for mu, lam, v in model:
        inv = 1.0 / (lam + ridge) if ridge > 0 else np.divide(1.0, lam, out=np.zeros_like(lam), where=lam > 0)
        d2.append(((q - mu) @ v) ** 2 @ inv)
    return np.array(d2)


def md_predict(model, q, ridge=0.0):
    return md_dist2(model, q, ridge).argmin(0)


def md_acc(xtr, ytr, xte, yte, ridges=(0.0,)):
    """(train, test) accuracy of the Mahalanobis classifier for each covariance ridge."""
    model = md_fit(xtr, ytr)
    q = np.vstack([xtr, xte])
    out = []
    for r in ridges:
        pred = md_predict(model, q, r)
        out.append((np.mean(pred[:len(xtr)] == ytr), np.mean(pred[len(xtr):] == yte)))
    return np.array(out)


# ---------------------------------------------------------------- PCA and LDA

def pca_fit(x):
    return x.mean(0), *eig_desc(cov(x))


def lda_fit(x, y, gamma=0.0):
    """Solve S_b w = lambda (S_w + gamma I) w. With gamma = 0 the search stays in the range of S_w."""
    mu = x.mean(0)
    sw = np.zeros((x.shape[1], x.shape[1]))
    sb = np.zeros_like(sw)
    for c in np.unique(y):
        xc = x[y == c]
        p = len(xc) / len(x)
        sw += p * cov(xc)
        sb += p * np.outer(xc.mean(0) - mu, xc.mean(0) - mu)
    lam, v = eig_desc(sw)
    keep = lam > 0 if gamma == 0 else np.ones(len(lam), bool)
    b = v[:, keep] / np.sqrt(lam[keep] + gamma)  # b.T (S_w + gamma I) b = I
    _, u = eig_desc(b.T @ sb @ b)
    return mu, b @ u[:, :len(np.unique(y)) - 1]


def overlap(w, s):
    """Mean squared cosine between span(w) and the first s coordinate axes."""
    q, _ = np.linalg.qr(w)
    return np.sum(q[:s] ** 2) / q.shape[1]


# ---------------------------------------------------------------- experiments

def run_task(task):
    """One dataset setting, one split, one repetition: Parts 2, 3 and 4."""
    dataset, normalize, var, fraction, rep = task
    if dataset == "synthetic":
        signal, y, noise = synthetic(rep)
        informative = 2  # x3 has the same distribution in every class
    else:
        iris = load_iris()
        signal, y, noise = iris.data, iris.target, iris_noise(rep)
        informative = 4
    train, test = split(y, rep, fraction)
    x = features(signal, noise, var, train, normalize)
    xtr, ytr, xte, yte = x[train], y[train], x[test], y[test]
    s = signal.shape[1]
    with_nn = dataset == "synthetic"  # Part 5 asks for the Mahalanobis classifier only
    out = {}

    # Part 2: the s signal columns plus the first q noise columns, q = 0..100.
    if with_nn:
        out["raw_nn"] = nn_curve(xtr, ytr, xte, yte)[s - 1:]
    out["raw_md"] = np.array([md_acc(xtr[:, :s + q], ytr, xte[:, :s + q], yte, GAMMAS)
                              for q in range(N_NOISE + 1)])

    # Part 3: PCA fitted on the training set with all 100 noise columns.
    mu, lam, v = pca_fit(xtr)
    rank = np.count_nonzero(lam)
    utr, ute = (xtr - mu) @ v, (xte - mu) @ v
    utr[:, lam == 0] = 0.0  # exact zeros instead of round-off
    out["spectrum"] = lam
    pca_nn = np.full((1 + len(GAMMAS), N_NOISE, 3), np.nan)
    pca_md = np.full((1 + len(GAMMAS), N_NOISE, 2), np.nan)
    for m, gamma in enumerate((None,) + GAMMAS):  # None: plain PCA, no rescaling
        kmax = min(rank, N_NOISE) if gamma == 0 else N_NOISE  # whitening needs lambda > 0
        scale = 1.0 if gamma is None else 1.0 / np.sqrt(lam[:kmax] + gamma)
        ztr, zte = utr[:, :kmax] * scale, ute[:, :kmax] * scale
        if with_nn:
            pca_nn[m, :kmax] = nn_curve(ztr, ytr, zte, yte)
        for k in range(1, kmax + 1):
            pca_md[m, k - 1] = md_acc(ztr[:, :k], ytr, zte[:, :k], yte)[0]
    out["pca_md"] = pca_md
    if with_nn:
        out["pca_nn"] = pca_nn

    # Part 4: LDA (two Fisher directions for three classes) with ridge on S_w.
    lda_nn = np.full((len(GAMMAS), 2, 3), np.nan)
    lda_md = np.full((len(GAMMAS), 2, 2), np.nan)
    lda_overlap = np.empty(len(GAMMAS))
    for g, gamma in enumerate(GAMMAS):
        m0, w = lda_fit(xtr, ytr, gamma)
        ztr, zte = (xtr - m0) @ w, (xte - m0) @ w
        if with_nn:
            lda_nn[g] = nn_curve(ztr, ytr, zte, yte)
        for l in (1, 2):
            lda_md[g, l - 1] = md_acc(ztr[:, :l], ytr, zte[:, :l], yte)[0]
        lda_overlap[g] = overlap(w, informative)
    out["lda_md"] = lda_md
    if with_nn:
        out["lda_nn"] = lda_nn
    out["overlap"] = np.append(lda_overlap, overlap(v[:, :2], informative))  # last entry: PCA2
    return out


def tag_of(dataset, normalize, var):
    return "syn" if dataset == "synthetic" else f"iris_n{int(normalize)}_v{var:g}"


def run_all(jobs):
    tasks = [("synthetic", False, NOISE_VAR, f, r) for f in FRACTIONS for r in range(REPEATS)]
    tasks += [("iris", n, v, f, r) for n in (False, True) for v in IRIS_VARS
              for f in FRACTIONS for r in range(REPEATS)]
    with ProcessPoolExecutor(jobs) as pool:
        outs = list(pool.map(run_task, tasks, chunksize=4))
    res = {}
    for (dataset, normalize, var, fraction, rep), out in zip(tasks, outs):
        for name, arr in out.items():
            key = f"{tag_of(dataset, normalize, var)}/{name}"
            if key not in res:
                res[key] = np.full((len(FRACTIONS), REPEATS) + np.shape(arr), np.nan)
            res[key][FRACTIONS.index(fraction), rep] = arr
    return res


# ---------------------------------------------------------------- figures

TEXT_WIDTH = 6.85  # inches; figures are drawn at their printed size
INK, INK2, MUTED, GRID, AXIS, SHADE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#f0efec"
# Every figure uses the same meanings: 1-NN blue, MD orange, reference lines grey, dashed = training data.
# A lighter tint marks the second condition (the 20/80 split, or z-scored Iris features).
NN, NN_TINT, MD, MD_TINT, REF, REF_TINT = "#2a78d6", "#86b6ef", "#eb6834", "#f19a64", INK2, "#a9a7a1"
NN_RAMP = ("#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281")  # gamma = 0 ... 10, light to dark
MD_RAMP = ("#f19a64", "#e97c46", "#d4602a", "#a8461b", "#7a3210")
GREY_RAMP = ("#a9a7a1", "#6f6d68", INK)
CLASS_COLORS = ("#1baf7a", "#6250d6", "#eda100")
SPLIT_NAMES = ("50/50", "20/80")
TRAIN_TEST = (("train", "--"), ("test", "-"))


def style():
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Noto Sans", "DejaVu Sans"], "axes.unicode_minus": False,
        "mathtext.fontset": "dejavusans", "font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7,
        "xtick.labelsize": 6.5, "ytick.labelsize": 6.5, "legend.fontsize": 6.3,
        "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "axes.axisbelow": True,
        "axes.titlelocation": "left", "axes.titlepad": 3, "lines.linewidth": 1.1,
        "legend.frameon": False, "legend.handlelength": 1.8, "legend.borderaxespad": 0.3,
        "legend.labelspacing": 0.3, "legend.columnspacing": 0.9,
        "xtick.major.size": 2, "ytick.major.size": 2, "pdf.fonttype": 42, "savefig.dpi": 300,
    })
    import matplotlib.pyplot as plt
    return plt


def save(fig, out, name):
    fig.savefig(out / f"{name}.pdf")
    fig.savefig(out / f"{name}.png", dpi=200)
    import matplotlib.pyplot as plt
    plt.close(fig)


def mean_line(ax, x, runs, color, label=None, ls="-", band=False, lw=1.1, **kw):
    """Mean over repetitions in percent; optional band of +-1 standard deviation."""
    ok = ~np.isnan(runs).all(axis=0)  # whitening without ridge stops at the PCA rank
    x, runs = np.asarray(x)[ok], 100 * runs[:, ok]
    ax.plot(x, runs.mean(0), color=color, ls=ls, lw=lw, label=label, **kw)
    if band:
        m, s = runs.mean(0), runs.std(0, ddof=1)
        ax.fill_between(x, m - s, m + s, color=color, alpha=0.13, lw=0)


def plain_log_ticks(axis):
    """Label a log axis 0.01, 0.1, 1, 10 instead of powers of ten."""
    from matplotlib.ticker import FuncFormatter
    axis.set_major_formatter(FuncFormatter(lambda t, _: f"{t:g}"))


def keys(ax, colors=(), styles=(), **kw):
    """Legend in which color and line style carry separate meanings."""
    from matplotlib.lines import Line2D
    handles = [Line2D([], [], color=c, label=l) for l, c in colors]
    handles += [Line2D([], [], color=INK2, ls=s, label=l) for l, s in styles]
    ax.legend(handles=handles, **kw)


def gamma_keys(ax, ramp, **kw):
    keys(ax, [("no whitening", REF)] + [(r"$\gamma$ = " + f"{g:g}", c) for g, c in zip(GAMMAS, ramp)], **kw)


def shade_singular(ax, start, label=False):
    """Grey band from the first dimension at which the class covariances are singular."""
    ax.axvspan(start - 0.5, 100.5, color=SHADE, lw=0, zorder=0)
    if label:
        ax.text(start + 1.5, 3, r"$\hat\Sigma_c$ singular", color=MUTED, fontsize=6.3, va="bottom")


def ellipse_2d(ax, z, color):
    """Equal-Mahalanobis-distance contours (1, 2, 3) of the class sample mean and covariance."""
    mu, (lam, v) = z.mean(0), np.linalg.eigh(cov(z))
    t = np.linspace(0, 2 * np.pi, 200)
    unit = v @ (np.sqrt(lam)[:, None] * np.vstack([np.cos(t), np.sin(t)]))
    for r in (1, 2, 3):
        ax.plot(*(mu[:, None] + r * unit), color=color, lw=0.6)


def class_keys(ax, **kw):
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], ls="", marker="o", ms=3.5, color=c, label=f"class {i + 1}")
                       for i, c in enumerate(CLASS_COLORS)], **kw)


def fig_part1(out):
    from scipy.stats import chi2
    plt = style()
    signal, y, noise = synthetic(0)
    x = np.hstack([signal, np.sqrt(NOISE_VAR) * noise])
    basis, _ = np.linalg.qr(np.random.default_rng([SEED, 99]).standard_normal((x.shape[1], 2)))
    views = [(x[:, [0, 1]], "$x_1$", "$x_2$"), (x[:, [1, 2]], "$x_2$", "$x_3$"),
             (x[:, [0, 3]], "$x_1$", "noise 1"), (x @ basis, "random direction 1", "random direction 2")]
    fig = plt.figure(figsize=(TEXT_WIDTH, 2.95))
    outer = fig.add_gridspec(1, 2, width_ratios=(1, 1.05), wspace=0.0, left=0.065, right=1.0,
                             bottom=0.16, top=0.95)
    inner = outer[0].subgridspec(2, 2, wspace=0.5, hspace=0.62)
    for i, (z, xl, yl) in enumerate(views):
        ax = fig.add_subplot(inner[i // 2, i % 2])
        for c in range(3):
            ax.scatter(*z[y == c].T, s=1.2, color=CLASS_COLORS[c], alpha=0.5, lw=0)
            ellipse_2d(ax, z[y == c], CLASS_COLORS[c])
        ax.set_aspect("equal", adjustable="datalim")
        ax.set_xlabel(xl, labelpad=1)
        ax.set_ylabel(yl, labelpad=0)
        ax.set_title("(" + "abcd"[i] + ")")
    ax = fig.add_subplot(outer[1], projection="3d")
    r2 = chi2.ppf(0.95, 3)
    u, w = np.meshgrid(np.linspace(0, 2 * np.pi, 25), np.linspace(0, np.pi, 13))
    sphere = np.stack([np.cos(u) * np.sin(w), np.sin(u) * np.sin(w), np.cos(w)])
    inside = []
    for c in range(3):
        s = signal[y == c]
        mu, (lam, v) = s.mean(0), np.linalg.eigh(cov(s))
        shell = mu[:, None, None] + np.sqrt(r2) * np.einsum("ij,jkl->ikl", v * np.sqrt(lam), sphere)
        ax.plot_wireframe(*shell, color=CLASS_COLORS[c], lw=0.3, alpha=0.55)
        ax.scatter(*s.T, s=2, color=CLASS_COLORS[c], alpha=0.9, lw=0, depthshade=False)
        d = s - mu
        inside.append(int(np.sum(np.einsum("ij,jk,ik->i", d, np.linalg.inv(cov(s)), d) <= r2)))
    ax.set_box_aspect(np.ptp(signal, axis=0), zoom=1.1)
    ax.view_init(elev=28, azim=-62)
    ax.set_xlabel("$x_1$", labelpad=-5)
    ax.set_ylabel("$x_2$", labelpad=-5)
    ax.set_zlabel("$x_3$", labelpad=-7)
    ax.tick_params(pad=-2, labelsize=6.3)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.set_pane_color((1, 1, 1, 0))
        axis._axinfo["grid"].update(color=GRID, linewidth=0.4)
    ax.set_title("(e)", y=0.93, x=0.08)
    class_keys(ax, loc="upper right", bbox_to_anchor=(0.97, 0.9))
    save(fig, out, "fig1_views")
    return inside, float(r2), np.sum(basis[:2] ** 2, axis=0).tolist()


def fig_part2(res, out):
    plt = style()
    q = np.arange(N_NOISE + 1)
    fig, axes = plt.subplots(1, 2, figsize=(TEXT_WIDTH, 1.9), sharey=True)
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.2, top=0.9, wspace=0.08)
    for f, ax in enumerate(axes):
        nn, md = res["syn/raw_nn"][f], res["syn/raw_md"][f][:, :, 0]
        n_c = round(100 * FRACTIONS[f])
        shade_singular(ax, n_c - 3, label=True)
        mean_line(ax, q, nn[..., 0], NN, ls="--")
        mean_line(ax, q, nn[..., 1], NN, ls=":")
        mean_line(ax, q, nn[..., 2], NN, band=True)
        mean_line(ax, q, md[..., 0], MD, ls="--")
        mean_line(ax, q, md[..., 1], MD, band=True)
        ax.set(xlim=(0, 100), ylim=(0, 102), xlabel="added noise dimensions $q$")
        ax.set_title(f"({'ab'[f]}) {SPLIT_NAMES[f]} split, $n_c$ = {n_c}")
    axes[0].set_ylabel("accuracy (%)")
    keys(axes[1], (("1-NN", NN), ("MD", MD)),
         (("train", "--"), ("1-NN leave-one-out", ":"), (r"test, mean $\pm$ 1 SD", "-")),
         loc="lower left", bbox_to_anchor=(0.0, 0.08), ncol=2)
    save(fig, out, "fig2_hughes")


def population_spectrum():
    mu0 = MEANS.mean(0)
    sb = sum(np.outer(m - mu0, m - mu0) for m in MEANS) / 3
    top = np.linalg.eigvalsh(SIGMA[:2, :2] + sb[:2, :2])[::-1]
    return np.concatenate([top, np.full(N_NOISE + 1, NOISE_VAR)])


def fig_part3(res, out):
    plt = style()
    k = np.arange(1, N_NOISE + 1)
    fig, axes = plt.subplots(2, 3, figsize=(TEXT_WIDTH, 3.6))
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.1, top=0.95, wspace=0.28, hspace=0.5)
    ax = axes[0, 0]
    full = np.mean([eig_desc(cov(np.hstack([s, np.sqrt(NOISE_VAR) * n])))[0]
                    for s, _, n in map(synthetic, range(REPEATS))], axis=0)
    rank = np.arange(1, full.size + 1)
    ax.semilogy(rank, population_spectrum(), color=INK, lw=0.8, ls=":", label="population")
    ax.semilogy(rank, full, color=GREY_RAMP[2], label="all 300 samples")
    for f, color in ((0, GREY_RAMP[1]), (1, GREY_RAMP[0])):
        spec = res["syn/spectrum"][f].mean(0)
        ax.semilogy(rank[spec > 0], spec[spec > 0], color=color,
                    label=f"training set, N = {round(300 * FRACTIONS[f])}")
    ax.set(xlabel="rank", ylabel="eigenvalue", xlim=(0, 104), ylim=(0.008, 10))
    plain_log_ticks(ax.yaxis)
    ax.set_title("(a) eigenvalues, descending")
    ax.legend(loc="lower left")
    for col, name, colors in ((1, "pca_nn", (NN, NN_TINT)), (2, "pca_md", (MD, MD_TINT))):
        ax = axes[0, col]
        for f in (0, 1):
            runs = res[f"syn/{name}"][f][:, 1]  # gamma = 0
            mean_line(ax, k, runs[..., 0], colors[f], ls="--")
            mean_line(ax, k, runs[..., -1], colors[f])
        ax.set(xlabel="retained components $k$", ylim=(0, 102), xlim=(1, 100))
    mean_line(axes[0, 1], k, res["syn/pca_nn"][0][:, 0, :, 2], REF, lw=0.9)
    axes[0, 1].set_title("(b) PCA whitening + 1-NN")
    axes[0, 2].set_title("(c) PCA whitening + MD")
    keys(axes[0, 1], (("50/50", NN), ("20/80", NN_TINT), ("50/50, no whitening", REF)), TRAIN_TEST,
         loc="lower right", ncol=2)
    keys(axes[0, 2], (("50/50", MD), ("20/80", MD_TINT)), TRAIN_TEST, loc="lower left")
    axes[0, 1].set_ylabel("accuracy (%)")
    for col, name, ramp in ((0, "pca_nn", NN_RAMP), (1, "pca_md", MD_RAMP)):
        ax = axes[1, col]
        runs = res[f"syn/{name}"][0]
        mean_line(ax, k, runs[:, 0, :, -1], REF, lw=0.9)
        for g, color in enumerate(ramp):
            mean_line(ax, k, runs[:, g + 1, :, -1], color)
        ax.set(xlabel="retained components $k$", ylim=(0, 102), xlim=(1, 100))
        gamma_keys(ax, ramp, loc="lower left", ncol=2)
    axes[1, 0].set_title(r"(d) 1-NN test, ridge $\gamma$ in PCA, 50/50")
    axes[1, 1].set_title(r"(e) MD test, ridge $\gamma$ in PCA, 50/50")
    axes[1, 0].set_ylabel("test accuracy (%)")
    shade_singular(axes[1, 1], 50)
    ax = axes[1, 2]
    q = np.arange(N_NOISE + 1)
    shade_singular(ax, 47)
    for g, color in enumerate(MD_RAMP):
        mean_line(ax, q, res["syn/raw_md"][0][:, :, g, 1], color)
    ax.set(xlabel="added noise dimensions $q$", ylim=(0, 102), xlim=(0, 100))
    ax.set_title(r"(f) MD test with $\hat\Sigma_c+\gamma I$, no PCA, 50/50")
    keys(ax, [(r"$\gamma$ = " + f"{g:g}", c) for g, c in zip(GAMMAS, MD_RAMP)], loc="lower right", ncol=2)
    save(fig, out, "fig3_pca")


def fig_part4(res, out):
    plt = style()
    fig = plt.figure(figsize=(TEXT_WIDTH, 1.9))
    grid = fig.add_gridspec(1, 5, width_ratios=(1.15, 1, 1, 1, 0.6), wspace=0.36,
                            left=0.065, right=0.995, bottom=0.21, top=0.88)
    ax = fig.add_subplot(grid[0])
    pos = np.arange(len(GAMMAS))
    for f, (nn_c, md_c, ref_c) in enumerate(((NN, MD, REF), (NN_TINT, MD_TINT, REF_TINT))):
        ax.axhline(100 * res["syn/pca_md"][f][:, 1, 1, 1].mean(), color=ref_c, lw=1.0)
        ax.plot(pos, 100 * res["syn/lda_md"][f][:, :, 1, 1].mean(0), color=md_c, marker="o", ms=2.5)
        ax.plot(pos, 100 * res["syn/lda_nn"][f][:, :, 1, 2].mean(0), color=nn_c, marker="o", ms=2.5)
    ax.set_xticks(pos, [f"{g:g}" for g in GAMMAS])
    ax.set(xlabel=r"ridge $\gamma$ on $S_w$", ylabel="test accuracy (%)", ylim=(50, 100))
    ax.set_title("(a) two output dimensions")
    keys(ax, (("LDA + MD", MD), ("LDA + 1-NN", NN), ("PCA2 + MD", REF), ("lighter: 20/80", REF_TINT)),
         loc="lower right")
    signal, y, noise = synthetic(0)
    train, test = split(y, 0, 0.5)
    x = features(signal, noise, NOISE_VAR, train)
    mu, lam, v = pca_fit(x[train])
    maps = [(r"(b) PCA, $k$ = 2, whitened", lambda z: (z - mu) @ v[:, :2] / np.sqrt(lam[:2]))]
    for title, gamma in (("(c) LDA", 0.0), (r"(d) rLDA, $\gamma$ = 1", 1.0)):
        m0, w = lda_fit(x[train], y[train], gamma)
        maps.append((title, lambda z, m0=m0, w=w: (z - m0) @ w))
    for i, (title, f) in enumerate(maps, start=1):
        ax = fig.add_subplot(grid[i])
        for c in range(3):
            ztr, zte = f(x[train][y[train] == c]), f(x[test][y[test] == c])
            ax.scatter(*zte.T, s=2.2, color=CLASS_COLORS[c], alpha=0.8, lw=0)
            ax.scatter(*ztr.T, s=5, facecolors="none", edgecolors=CLASS_COLORS[c], lw=0.4, alpha=0.9)
        ax.set_title(title)
        ax.set_xlabel("axis 1", labelpad=1)
        ax.set_ylabel("axis 2", labelpad=1)
    from matplotlib.lines import Line2D
    ax = fig.add_subplot(grid[4])
    ax.axis("off")
    handles = [Line2D([], [], ls="", marker="o", ms=3.5, color=c, label=f"class {i + 1}")
               for i, c in enumerate(CLASS_COLORS)]
    handles += [Line2D([], [], ls="", marker="o", ms=3.5, mfc="none", mec=INK2, mew=0.6, label="training"),
                Line2D([], [], ls="", marker="o", ms=2.5, color=INK2, label="test")]
    ax.legend(handles=handles, loc="center left", borderaxespad=0, handletextpad=0.2)
    save(fig, out, "fig4_lda")


def fig_part5(res, out):
    plt = style()
    fig, axes = plt.subplots(2, 3, figsize=(TEXT_WIDTH, 3.55))
    fig.subplots_adjust(left=0.07, right=0.99, bottom=0.1, top=0.95, wspace=0.28, hspace=0.52)
    q, k = np.arange(N_NOISE + 1), np.arange(1, N_NOISE + 1)
    norm_keys = (("original", MD), ("z-scored", MD_TINT))
    for f, ax in enumerate(axes[0, :2]):
        shade_singular(ax, round(50 * FRACTIONS[f]) - 4, label=True)
        for n, color in ((0, MD), (1, MD_TINT)):
            runs = res[f"iris_n{n}_v0.5/raw_md"][f][:, :, 0]
            mean_line(ax, q, runs[..., 0], color, ls="--")
            mean_line(ax, q, runs[..., 1], color)
        ax.set(xlabel="added noise dimensions $q$", ylim=(0, 102), xlim=(0, 100))
        ax.set_title(f"({'ab'[f]}) MD, {SPLIT_NAMES[f]}, " + r"$\sigma^2$ = 0.5")
        keys(ax, norm_keys, TRAIN_TEST, loc="upper right")
    axes[0, 0].set_ylabel("accuracy (%)")
    ax = axes[0, 2]
    for var, color in zip((0.05, 0.5, 5.0), GREY_RAMP):
        spec = res[f"iris_n0_v{var:g}/spectrum"][0].mean(0)
        r = np.arange(1, spec.size + 1)
        ax.semilogy(r[spec > 0], spec[spec > 0], color=color, label=r"$\sigma^2$ = " + f"{var:g}")
    iris_var = np.linalg.eigvalsh(cov(load_iris().data))[-1]
    ax.axhline(iris_var, color=MD, lw=0.9, ls=(0, (4, 2)), label=f"Iris PC1 variance {iris_var:.2f}")
    ax.set(xlabel="rank", ylabel="eigenvalue", xlim=(0, 76))
    plain_log_ticks(ax.yaxis)
    ax.set_title("(c) eigenvalues, original features, 50/50")
    ax.legend(loc="lower left")
    ax = axes[1, 0]
    shade_singular(ax, 25)
    for n, color in ((0, MD), (1, MD_TINT)):
        runs = res[f"iris_n{n}_v0.5/pca_md"][0][:, 1]
        mean_line(ax, k, runs[..., 0], color, ls="--")
        mean_line(ax, k, runs[..., 1], color)
    ax.set(xlabel="retained components $k$", ylabel="accuracy (%)", ylim=(0, 102), xlim=(1, 100))
    ax.set_title(r"(d) PCA whitening + MD, 50/50, $\sigma^2$ = 0.5")
    keys(ax, norm_keys, TRAIN_TEST, loc="upper right")
    ax = axes[1, 1]
    shade_singular(ax, 25)
    runs = res["iris_n0_v0.5/pca_md"][0]
    mean_line(ax, k, runs[:, 0, :, 1], REF, lw=0.9)
    for g, color in enumerate(MD_RAMP):
        mean_line(ax, k, runs[:, g + 1, :, 1], color)
    ax.set(xlabel="retained components $k$", ylim=(0, 102), xlim=(1, 100))
    ax.set_title(r"(e) MD test, ridge $\gamma$ in PCA, 50/50")
    gamma_keys(ax, MD_RAMP, loc="upper right", ncol=2)
    ax = axes[1, 2]
    v = np.array(IRIS_VARS)
    curves = ((("#eb6834", "#f19a64"), "o", "MD, 104 dims", "raw_md", lambda a: a[:, 100, 0, 1]),
              (("#6250d6", "#a39be8"), "s", "PCA2 + MD", "pca_md", lambda a: a[:, 1, 1, 1]),
              (("#008300", "#6fb86f"), "^", "LDA + MD", "lda_md", lambda a: a[:, 0, 1, 1]),
              (("#d55181", "#e99ab8"), "D", "rLDA + MD", "lda_md", lambda a: a[:, 3, 1, 1]))  # rLDA: gamma = 1
    from matplotlib.lines import Line2D
    handles = []
    for (dark, light), marker, name, key, pick in curves:
        for n, color in ((0, dark), (1, light)):
            acc = [100 * pick(res[f"iris_n{n}_v{s:g}/{key}"][0]).mean() for s in v]
            ax.semilogx(v, acc, color=color, marker=marker, ms=2.4, lw=1.0)
        handles.append(Line2D([], [], color=dark, marker=marker, ms=2.4, label=name))
    handles.append(Line2D([], [], color=REF_TINT, lw=1.0, label="lighter: z-scored"))
    ax.set(xlabel=r"noise variance $\sigma^2$", ylabel="test accuracy (%)", ylim=(0, 102))
    plain_log_ticks(ax.xaxis)
    ax.set_title("(f) 100 noise dimensions, 50/50")
    ax.legend(handles=handles, loc="lower left", fontsize=6.0, handlelength=1.6, labelspacing=0.12, borderaxespad=0.15)
    save(fig, out, "fig5_iris")


def make_figures(out):
    res = dict(np.load(out / "results.npz"))
    figdir = out / "figures"
    figdir.mkdir(exist_ok=True)
    inside, r2, random_inplane = fig_part1(figdir)
    fig_part2(res, figdir)
    fig_part3(res, figdir)
    fig_part4(res, figdir)
    fig_part5(res, figdir)
    (out / "part1.json").write_text(json.dumps(dict(inside_95=inside, chi2_3_95=r2,
                                                    random_directions_in_x1x2=random_inplane), indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("--plots-only", action="store_true")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.plots_only:
        start = time.perf_counter()
        res = run_all(args.jobs)
        np.savez_compressed(args.out / "results.npz", **res)
        info = dict(seed=SEED, repeats=REPEATS, fractions=FRACTIONS, gammas=GAMMAS,
                    iris_noise_variances=IRIS_VARS, synthetic_noise_variance=NOISE_VAR,
                    eigenvalue_rtol=RTOL, seconds=round(time.perf_counter() - start, 1),
                    python=platform.python_version(), numpy=np.__version__,
                    scipy=scipy.__version__, scikit_learn=sklearn.__version__)
        (args.out / "run_info.json").write_text(json.dumps(info, indent=2) + "\n")
        print(f"experiments done in {info['seconds']} s")
    make_figures(args.out)
    print(f"figures written to {args.out / 'figures'}")


if __name__ == "__main__":
    main()
