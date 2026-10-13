"""Checks pr_hwN.py against direct formulas, SciPy and scikit-learn.

Run from the repository root:  uv run homeworkN/PR_HWN/check_hwN.py
"""
import numpy as np

import pr_hwN as hw

if not __debug__:
    raise SystemExit("check_hwN.py: the checks are asserts; run without python -O or PYTHONOPTIMIZE")

# One block per function in pr_hwN.py: compare it with a formula or a library, then print what passed.
x = np.random.default_rng([hw.SEED, 0, 1]).standard_normal(hw.SIZES[-1])
assert np.allclose(hw.run_task(0)["mean_error"], [abs(x[:n].mean()) for n in hw.SIZES])
print("placeholder experiment matches a direct computation: ok")
