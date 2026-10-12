"""Compute every number quoted in the report from results/, fill report/template.tex, and typeset it.

Run from the repository root after pr_hw1.py:  uv run homework1/PR_HW1/build_report.py
Always writes the public PDF, which has no student ID. If student.local.json exists, it first writes the
e3 copy with the ID on page 1. The asserts check the qualitative sentences of the report.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import numpy as np
from sklearn.datasets import load_iris

import pr_hw1 as hw

HERE = Path(__file__).resolve().parent
REPORT = HERE / "report"
PUBLIC_PDF = HERE.parent / "public" / "PR_HW1_蔡秀吉.pdf"  # pushed to GitHub
PRIVATE = HERE / "student.local.json"  # {"student_id": "..."}; ignored by git, never committed
R = dict(np.load(HERE / "results" / "results.npz"))
P1 = json.loads((HERE / "results" / "part1.json").read_text())
INFO = json.loads((HERE / "results" / "run_info.json").read_text())
G = {g: i for i, g in enumerate(hw.GAMMAS)}
GNAME = {0.0: "0", 0.01: "001", 0.1: "01", 1.0: "1", 10.0: "10"}
T50, T20 = 0, 1
v = {}


def pct(a):
    return 100 * np.nanmean(a)


def f1(x):
    return f"{x:.1f}"


def pm(a):
    return f"{100 * a.mean():.1f} $\\pm$ {100 * a.std(ddof=1):.1f}"


# Part 1
v["in1"], v["in2"], v["in3"] = map(str, P1["inside_95"])
v["chi3"] = f"{P1['chi2_3_95']:.2f}"

# Part 2: raw features, q = 0..100 noise columns
nn, md = R["syn/raw_nn"], R["syn/raw_md"]
for f, t in ((T50, "50"), (T20, "20")):
    te = md[f][:, :, 0, 1].mean(0)
    v[f"mdmin_{t}"], v[f"mdargmin_{t}"] = f1(100 * te.min()), str(te.argmin())
    assert te.argmin() == round(100 * hw.FRACTIONS[f]) - 4  # lowest at the last invertible dimension d = n_c - 1
    v[f"nnq100_{t}"] = f1(pct(nn[f][:, 100, 2]))
te50 = md[T50][:, :, 0, 1].mean(0)
assert md[T50][:, 46, 0, 0].mean() == 1, "50/50: MD fits the training set perfectly at its minimum"
v["nnq0_50"], v["mdq0_50"], v["mdq100_50"] = f1(pct(nn[T50][:, 0, 2])), f1(100 * te50[0]), f1(100 * te50[100])
tr20 = md[T20][:, :, 0, 0].mean(0)
zero_from = int(np.flatnonzero(tr20 == 0)[0])
assert np.all(tr20[zero_from:] == 0)
v["mdtrzero_20"] = str(zero_from)
ridge001 = md[T50][:, :, G[0.01], 1].mean(0)
assert ridge001[100] > ridge001[47:].min() + 0.05, "gamma = 0.01 also rebounds in the singular region"
assert max(te50[100], ridge001[100]) < te50[0] - 0.1, "both stay far below the 3-dimensional accuracy"
v["noisesd"] = f"{np.sqrt(1.5 * 100):.0f}"  # SD over training points of a sum of 100 terms (n_test - n_train)^2

# Part 3: PCA on the 103-dimensional data
spec50 = R["syn/spectrum"][T50].mean(0)
pop = hw.population_spectrum()
v["pop1"], v["pop2"] = f"{pop[0]:.2f}", f"{pop[1]:.2f}"
v["s3"], v["slast"] = f"{spec50[2]:.2f}", f"{spec50[-1]:.3f}"
v["amp"] = f"{0.5 / spec50[-1]:.0f}"
v["rank20"] = str(int(np.count_nonzero(R["syn/spectrum"][T20].mean(0))))
pnn, pmd = R["syn/pca_nn"], R["syn/pca_md"]
v["pnn2"], v["pmd2"] = f1(pct(pnn[T50][:, 1, 1, 2])), f1(pct(pmd[T50][:, 1, 1, 1]))
assert pnn[T50][:, 1, :, 2].mean(0).argmax() == 1, "1-NN after whitening peaks at k = 2"
plateau = pmd[T50][:, 1, 1:5, 1].mean(0)
assert plateau.max() - plateau.min() < 0.005 and pmd[T50][:, 1, :, 1].mean(0).argmax() <= 4
assert pct(pmd[T50][:, 1, 99, 0]) < 1, "MD training accuracy collapses again beyond n_c"
v["pnnplain100"] = f1(pct(pnn[T50][:, 0, 99, 2]))
for g in hw.GAMMAS:
    v[f"pnn100_{GNAME[g]}"] = f1(pct(pnn[T50][:, 1 + G[g], 99, 2]))
for f in (T50, T20):  # 1-NN at k = 100: larger gamma moves toward no whitening, in both splits
    ladder = [pct(pnn[f][:, 1 + G[g], 99, 2]) for g in hw.GAMMAS[1:]] + [pct(pnn[f][:, 0, 99, 2])]
    assert np.all(np.diff(ladder) > 0)
v["pnnk2lo"] = f1(min(pct(pnn[T50][:, m, 1, 2]) for m in range(6)))
v["pnnk2hi"] = f1(max(pct(pnn[T50][:, m, 1, 2]) for m in range(6)))
for f, n_c in ((T50, 50), (T20, 20)):
    sub = pmd[f][:, :, :n_c - 1, 1]  # every PCA scaling, k = 1 .. n_c - 1
    assert np.all(sub == sub[:, :1]), "MD after PCA ignores the scaling while invertible"
for g in (0.0, 1.0, 10.0):
    v[f"ridge100_{GNAME[g]}"] = f1(pct(md[T50][:, 100, G[g], 1]))
assert np.all(np.diff([pct(md[T50][:, 100, G[g], 1]) for g in hw.GAMMAS]) > 0), "covariance ridge helps MD"

# Part 4: LDA
lmd, ov = R["syn/lda_md"], R["syn/overlap"]
for g in hw.GAMMAS:
    v[f"lda_{GNAME[g]}"] = f1(pct(lmd[T50][:, G[g], 1, 1]))
assert abs(pct(lmd[T50][:, G[10.0], 1, 1]) - pct(pmd[T50][:, 1, 1, 1])) < 1, "rLDA(10) matches PCA2"
assert pct(lmd[T50][:, 0, 1, 0]) == 100, "LDA without ridge fits the training set perfectly"
v["ldagap"] = f1(pct(pmd[T50][:, 1, 1, 1]) - pct(lmd[T50][:, 0, 1, 1]))
v["lda20_0"], v["lda20_10"] = f1(pct(lmd[T20][:, 0, 1, 1])), f1(pct(lmd[T20][:, 4, 1, 1]))
v["pmd2_20"] = f1(pct(pmd[T20][:, 1, 1, 1]))
for g in (0.0, 1.0, 10.0):
    v[f"ov_{GNAME[g]}"] = f"{ov[T50][:, G[g]].mean():.2f}"
v["ovpca"] = f"{ov[T50][:, 5].mean():.2f}"
swmin = []
for rep in range(hw.REPEATS):
    s, y, n = hw.synthetic(rep)
    tr, _ = hw.split(y, rep, 0.5)
    x, yt = hw.features(s, n, hw.NOISE_VAR, tr)[tr], y[tr]
    swmin.append(hw.eig_desc(sum(np.mean(yt == c) * hw.cov(x[yt == c]) for c in range(3)))[0][-1])
v["swmin"] = f"{np.mean(swmin):.3f}"
rows = []
for f, split_name in ((T50, "50/50"), (T20, "20/80")):
    for raw, pca, lda, clf, label in ((nn[f], pnn[f][:, 1, 1], R["syn/lda_nn"][f][:, :, 1], 2, "1-NN"),
                                       (md[f][:, :, 0], pmd[f][:, 1, 1], lmd[f][:, :, 1], 1, "MD")):
        cells = [pm(raw[:, 0, clf]), pm(raw[:, 100, clf]), pm(pca[:, clf])]
        cells += [pm(lda[:, G[g], clf]) for g in (0.0, 1.0, 10.0)]
        rows.append(f"{split_name} & {label} & " + " & ".join(cells) + r" \\")
v["table1"] = "\n".join(rows)

# Part 5: Iris with 100 noise dimensions
iris, target = load_iris(return_X_y=True)
I = lambda n, s, key: R[f"iris_n{n}_v{s:g}/{key}"]
MD100, PCA1, PCA2 = (lambda a: a[:, 100, 0, 1]), (lambda a: a[:, 1, 0, 1]), (lambda a: a[:, 1, 1, 1])
LDA = lambda g: lambda a: a[:, G[g], 1, 1]
acc = lambda n, s, key, pick, f=T50: pct(pick(I(n, s, key)[f]))
te = I(0, 0.5, "raw_md")[T50][:, :, 0, 1].mean(0)
v["iq0_50"], v["iqlast_50"], v["iqarg_50"], v["iq100_o"] = f1(100 * te[0]), f1(100 * te[20]), "20", f1(100 * te[100])
assert te[100] == te[21:].min() and te[100] < te[20], "Iris does not recover in the singular region"
for f, n_c in ((T50, 25), (T20, 10)):
    stack = np.stack([I(n, s, "raw_md")[f][:, :n_c - 4, 0, 1] for n in (0, 1) for s in hw.IRIS_VARS])
    assert np.all(stack == stack[:1]), "invertible MD ignores the scaling of features and noise"
assert np.all(I(0, 0.5, "pca_md")[T50][:, :, :24, 1] == I(0, 0.5, "pca_md")[T50][:, :1, :24, 1])
v["irispc1"] = f"{np.linalg.eigvalsh(hw.cov(iris))[-1]:.2f}"
sp5 = I(0, 5.0, "spectrum")[T50].mean(0)
v["isp5lo"], v["isp5hi"] = f"{sp5[5]:.0f}", f"{sp5[0]:.0f}"
assert sp5[5] > float(v["irispc1"]), "with sigma2 = 5 the leading eigenvalues are all noise"
v["ipcamin02"] = f1(min(acc(0, s, "pca_md", PCA2) for s in hw.IRIS_VARS if s <= 0.2))
for s, key in ((0.01, "001"), (1.0, "1"), (2.0, "2"), (5.0, "5")):
    v[f"ipca_{key}"] = f1(acc(0, s, "pca_md", PCA2))
v["ilda_05"], v["irlda_05"] = f1(acc(0, 0.5, "lda_md", LDA(0.0))), f1(acc(0, 0.5, "lda_md", LDA(1.0)))
v["irlda_5"] = f1(acc(0, 5.0, "lda_md", LDA(1.0)))
lg = [acc(0, 0.5, "lda_md", LDA(g)) for g in hw.GAMMAS]
assert all(15 < x - lg[0] < 25 for x in lg[1:]), "every gamma > 0 gains about 20 points"
def four(s):
    """Test accuracy at q = 100 of the four MD pipelines (50/50, original features)."""
    return {"md": acc(0, s, "raw_md", MD100), "pca": acc(0, s, "pca_md", PCA2),
            "lda": acc(0, s, "lda_md", LDA(0.0)), "rlda": acc(0, s, "lda_md", LDA(1.0))}


for s in hw.IRIS_VARS:
    a = four(s)
    assert a["lda"] < a["rlda"], f"50/50: rLDA beats LDA at sigma2 = {s}"
    if s <= 0.5:
        assert max(a, key=a.get) == "pca", f"PCA2 is best at low noise (sigma2 = {s})"
    if s >= 2:
        assert max(a, key=a.get) == "rlda", f"rLDA is best at sigma2 = {s}"
lo, hi = four(0.01), four(0.5)
assert max(lo, key=lambda k: lo[k] - hi[k]) == "md", "MD on 104 dimensions falls fastest"
v["ilda20_005"], v["irlda20_005"] = (f1(acc(0, 0.05, "lda_md", LDA(0.0), T20)),
                                     f1(acc(0, 0.05, "lda_md", LDA(1.0), T20)))
assert float(v["ilda20_005"]) > float(v["irlda20_005"]), "20/80 at low noise: LDA edges out rLDA"
rows, table = [], (("MD，104 維", "raw_md", MD100), ("PCA2 + MD", "pca_md", PCA2),
                   ("LDA + MD", "lda_md", LDA(0.0)), (r"rLDA $\gamma=0.1$ + MD", "lda_md", LDA(0.1)),
                   (r"rLDA $\gamma=1$ + MD", "lda_md", LDA(1.0)), (r"rLDA $\gamma=10$ + MD", "lda_md", LDA(10.0)))
for name, key, pick in table:
    rows.append(f"{name} & " + " & ".join(f1(acc(0, s, key, pick, f)) for f in (T50, T20) for s in (0.05, 0.5, 5.0))
                + r" \\")
v["table2"] = "\n".join(rows)
lower = sum(acc(0, s, key, pick, T20) < acc(0, s, key, pick) for _, key, pick in table for s in (0.05, 0.5, 5.0))
assert lower > 3 * len(table) / 2, "most 20/80 entries of table 2 are lower than 50/50"
v["ipcaz_001"], v["ipca1_001"], v["ipcaz1_001"] = (f1(acc(1, 0.01, "pca_md", PCA2)), f1(acc(0, 0.01, "pca_md", PCA1)),
                                                   f1(acc(1, 0.01, "pca_md", PCA1)))
assert abs(acc(1, 0.01, "pca_md", PCA2) - acc(1, 0.01, "pca_md", PCA1)) < 0.5
assert all(acc(1, s, "pca_md", PCA2) < acc(0, s, "pca_md", PCA2) for s in hw.IRIS_VARS if s <= 0.2)
lamz, vecz = hw.eig_desc(hw.cov((iris - iris.mean(0)) / iris.std(0)))
v["zload"] = "、".join(f"${w:.2f}$" for w in vecz[:, 0] * np.sign(vecz[:, 0].sum()))
v["varpl"] = f"{iris[:, 2].var():.2f}"
P = np.bincount(target) / len(target)
for j, name in ((1, "fswidth"), (2, "fplength")):
    col = iris[:, j]
    within = sum(P[c] * col[target == c].var() for c in range(3))
    between = sum(P[c] * (col[target == c].mean() - col.mean()) ** 2 for c in range(3))
    v[name] = f"{between / within:.2f}" if between < within else f"{between / within:.1f}"

# Run details for the appendix
v["seconds"] = f"{INFO['seconds']:.0f}"
for key in ("python", "numpy", "scipy", "scikit_learn"):
    v[key] = INFO[key]
import matplotlib
v["matplotlib"] = matplotlib.__version__


def fill(template, extra):
    values = {**v, **extra}
    missing = set(re.findall(r"<<(\w+)>>", template)) - values.keys()
    assert not missing, f"no value for {sorted(missing)}"
    return re.sub(r"<<(\w+)>>", lambda m: values[m.group(1)], template)


def build(template, extra, dest):
    (REPORT / "report.tex").write_text(fill(template, extra))
    for _ in range(2):
        subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "report.tex"],
                       cwd=REPORT, check=True, stdout=subprocess.DEVNULL)
    aux = (REPORT / "report.aux").read_text()
    body = int(re.search(r"\\newlabel\{body-end\}\{\{[^}]*\}\{(\d+)\}", aux).group(1))
    assert body <= 5, "the report body must fit in five pages"
    shutil.copyfile(REPORT / "report.pdf", dest)
    print(f"{dest.name}: body ends on page {body}")


def leaks(pdf, secret):
    """True if secret shows up in the PDF text, its metadata, or its raw bytes (ASCII or UTF-16BE)."""
    text = "".join(subprocess.run([tool, str(pdf), *extra], capture_output=True, text=True).stdout
                   for tool, extra in (("pdftotext", ["-"]), ("pdfinfo", [])))
    raw = pdf.read_bytes()
    utf16 = secret.encode("utf-16-be")
    return secret in text or secret.encode() in raw or utf16 in raw or utf16.hex().upper().encode() in raw.upper()


def main():
    template = (REPORT / "template.tex").read_text()
    unused = set(v) - set(re.findall(r"<<(\w+)>>", template))
    assert not unused, f"computed but never quoted: {sorted(unused)}"
    sid = json.loads(PRIVATE.read_text())["student_id"] if PRIVATE.exists() else None
    if sid:  # submission copy for e3, kept local
        build(template, {"sid": "\u3000" + sid, "pdfsid": " " + sid}, HERE.parent / "submission" / f"PR_HW1_蔡秀吉_{sid}.pdf")
    build(template, {"sid": "", "pdfsid": ""}, PUBLIC_PDF)  # built last, so report/ ends without the ID
    if sid:
        assert not leaks(PUBLIC_PDF, sid), "the public PDF must not contain the student ID"
        assert all(sid not in f.read_text(errors="ignore") for f in REPORT.iterdir() if f.suffix != ".pdf")
        print(f"{PUBLIC_PDF.name}: no student ID in text, metadata or bytes")


if __name__ == "__main__":
    main()
