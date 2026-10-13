"""Compare two results.npz files key by key (NaN equals NaN).

Usage:  uv run .agents/skills/homework-max-review/scripts/compare_npz.py saved.npz rerun.npz [--atol 0]
Exit status 1 if any key is missing or any array differs beyond --atol.
"""
import argparse
import sys

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("a")
ap.add_argument("b")
ap.add_argument("--atol", type=float, default=0.0)
args = ap.parse_args()
A, B = np.load(args.a), np.load(args.b)
bad = sorted(set(A.files) ^ set(B.files))
for key in bad:
    print(f"only in one file: {key}")
worst = 0.0
for key in sorted(set(A.files) & set(B.files)):
    x, y = A[key], B[key]
    if x.shape != y.shape:
        print(f"{key}: shape {x.shape} vs {y.shape}")
        bad.append(key)
        continue
    same_nan = np.array_equal(np.isnan(x), np.isnan(y))
    diff = np.nanmax(np.abs(x - y)) if np.isfinite(x).any() else 0.0
    worst = max(worst, diff)
    if not same_nan or diff > args.atol:
        print(f"{key}: max |diff| = {diff:.3g}, NaN pattern equal: {same_nan}")
        bad.append(key)
print(f"{len(A.files)} keys compared, largest difference {worst:.3g}, {len(bad)} problems")
sys.exit(1 if bad else 0)
