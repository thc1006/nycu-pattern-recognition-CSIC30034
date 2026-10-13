"""Every number quoted in the report, computed from results/; the asserts check its qualitative sentences.

tools/build_report.py runs this file and fills report/template.tex with v (key -> text).
"""
import platform

import matplotlib
import numpy as np
import scipy
import sklearn

import pr_hwN as hw

if not __debug__:
    raise SystemExit("report_numbers.py: the asserts are its checks; run without python -O or PYTHONOPTIMIZE")
R, INFO = hw.load()  # stops if results/ come from another grid than pr_hwN.py
now = dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
           scikit_learn=sklearn.__version__, matplotlib=matplotlib.__version__)
if drift := {k: f"{INFO[k]} -> {now[k]}" for k in now if INFO[k] != now[k]}:
    raise SystemExit(f"report_numbers.py: the environment changed since results/ were made {drift}; rerun pr_hwN.py")
v = {}

err = R["mean_error"].mean(0)  # placeholder numbers
v["n_first"], v["n_last"] = str(hw.SIZES[0]), str(hw.SIZES[-1])
v["err_first"], v["err_last"] = f"{err[0]:.3f}", f"{err[-1]:.3f}"
assert err[-1] < err[0], "the error shrinks as the sample grows"

# Run details for the appendix
v["repeats"] = str(hw.REPEATS)
v["jobs"] = str(INFO["jobs"])
v["seconds"] = f"{INFO['seconds']:.0f}"
for key in ("python", "numpy", "scipy", "scikit_learn", "matplotlib"):
    v[key] = INFO[key]
