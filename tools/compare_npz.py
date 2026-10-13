"""Compare two results.npz files key by key.

Usage:  uv run tools/compare_npz.py saved.npz rerun.npz [--atol 0]
Float arrays may differ by up to --atol, with NaN and inf in the same places; arrays of any other type
(integers, booleans, strings, dates) must be equal, NaT matching NaT. Record arrays are compared field by field.
Exit status 1 if any key is missing, unreadable, or different.
"""
import argparse
import sys

import numpy as np


def difference(x, y, atol):
    """(largest float difference, reason the arrays count as different or None)."""
    if x.shape != y.shape or x.dtype != y.dtype:  # a changed dtype is a changed result, even with equal values
        return 0.0, f"{x.dtype}{x.shape} vs {y.dtype}{y.shape}"
    if x.dtype.names:
        results = [difference(x[f], y[f], atol) for f in x.dtype.names]
        return max((d for d, _ in results), default=0.0), next((r for _, r in results if r), None)
    if x.dtype.kind not in "fc":
        return 0.0, None if np.array_equal(x, y, equal_nan=x.dtype.kind in "mM") else f"{x.dtype} values differ"
    if x.dtype.kind == "c":  # equal_nan treats complex(nan, 1) and complex(nan, 5) as equal, so compare the parts
        x, y = np.stack([x.real, x.imag]), np.stack([y.real, y.imag])
    fx, fy = np.isfinite(x), np.isfinite(y)
    same_special = np.array_equal(fx, fy) and np.array_equal(x[~fx], y[~fy], equal_nan=True)
    diff = float(np.abs(x[fx & fy] - y[fx & fy]).max()) if (fx & fy).any() else 0.0
    if not same_special or diff > atol:
        return diff, f"max |diff| = {diff:.3g}, NaN and inf in the same places: {same_special}"
    return diff, None


ap = argparse.ArgumentParser()
ap.add_argument("a")
ap.add_argument("b")
ap.add_argument("--atol", type=float, default=0.0)
args = ap.parse_args()
if not (np.isfinite(args.atol) and args.atol >= 0):
    ap.error("--atol must be a finite number >= 0")
A, B = np.load(args.a), np.load(args.b)
bad = sorted(set(A.files) ^ set(B.files))
for key in bad:
    print(f"only in one file: {key}")
worst = 0.0
for key in sorted(set(A.files) & set(B.files)):
    try:
        x, y = A[key], B[key]
    except ValueError as err:  # object arrays need pickle, which np.load refuses by default
        print(f"{key}: cannot read ({err})")
        bad.append(key)
        continue
    diff, reason = difference(x, y, args.atol)
    worst = max(worst, diff)
    if reason:
        print(f"{key}: {reason}")
        bad.append(key)
print(f"{len(set(A.files) | set(B.files))} keys compared, largest difference {worst:.3g}, {len(bad)} problems")
sys.exit(1 if bad else 0)
