"""Pattern Recognition HWN (NYCU, Fall 2026).

Run from the repository root (the environment is pinned by uv):
    uv run homeworkN/PR_HWN/pr_hwN.py               # experiments, then figures
    uv run homeworkN/PR_HWN/pr_hwN.py --plots-only  # figures from saved results
"""
import argparse
import json
import logging
import os
import platform
import time
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# One BLAS thread per worker; the parallelism comes from the process pool.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_var, "1")

import numpy as np
import scipy
import sklearn

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SEED = 2026
# Every draw comes from default_rng([SEED, rep, k]), one k >= 1 per stream. Keys of up to 4 numbers that differ
# only by trailing zeros give the same stream: [SEED, rep] = [SEED, rep, 0], and default_rng(SEED) = [SEED, 0].
REPEATS = 20
SIZES = np.arange(5, 101, 5)  # placeholder grid


def run_task(rep):
    """One repetition. Placeholder experiment: the error of the sample mean of standard normal data."""
    rng = np.random.default_rng([SEED, rep, 1])
    x = rng.standard_normal(SIZES[-1])
    return {"mean_error": np.array([abs(x[:n].mean()) for n in SIZES])}


def run_all(jobs):
    with ProcessPoolExecutor(jobs) as pool:
        outs = list(pool.map(run_task, range(REPEATS)))
    return {key: np.stack([out[key] for out in outs]) for key in outs[0]}  # first axis: repetition


# ---------------------------------------------------------------- figures

TEXT_WIDTH = 6.85  # inches; figures are drawn at their printed size


class _Raise(logging.Handler):
    def emit(self, record):
        raise RuntimeError(record.getMessage())


def style():
    """Shared figure style. A glyph missing from the fonts stops the script instead of drawing a box."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    font_manager.findfont("Noto Sans", fallback_to_default=False)  # raises if the font is not installed
    plt.style.use(["default", ROOT / "common" / "prhw.mplstyle"])  # "default": nothing from a matplotlibrc
    warnings.filterwarnings("error", r"Glyph \d+ .*missing from font")
    log = logging.getLogger("matplotlib.mathtext")
    if not any(isinstance(h, _Raise) for h in log.handlers):
        log.addHandler(_Raise(logging.WARNING))
    return plt


def save(fig, out, name):
    fig.savefig(out / f"{name}.pdf", metadata={"CreationDate": None})  # no date: a rerun writes the same file
    fig.savefig(out / f"{name}.png", dpi=200)
    import matplotlib.pyplot as plt
    plt.close(fig)


def plain_log_ticks(axis):
    """Label a log axis 0.01, 0.1, 1, 10, and 0.2, 0.5 on a short one: the default 10^{-1} and 2x10^{-1}
    labels need a minus sign Noto Sans lacks. Call it after set_xscale("log"), which resets the labels."""
    from matplotlib.ticker import FuncFormatter, LogFormatter

    class Plain(LogFormatter):  # matplotlib picks which minor ticks get a label
        def __call__(self, x, pos=None):
            return f"{x:g}" if super().__call__(x, pos) else ""

    axis.set_major_formatter(FuncFormatter(lambda t, _: f"{t:g}"))  # every major tick, also those from set_xticks
    if base := getattr(axis.get_transform(), "base", None):  # log and symlog axes
        axis.set_minor_formatter(Plain(base))


def load(out=HERE / "results"):
    """Saved results and run details; stops if they come from another SEED, REPEATS or SIZES than this file."""
    res = dict(np.load(out / "results.npz"))
    info = json.loads((out / "run_info.json").read_text())
    if (info["seed"], info["repeats"], info["sizes"]) != (SEED, REPEATS, SIZES.tolist()):
        raise SystemExit(f"{out} comes from another SEED, REPEATS or SIZES than {Path(__file__).name}; rerun it")
    return res, info


def make_figures(out):
    res, _ = load(out)
    plt = style()
    figdir = out / "figures"
    figdir.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(TEXT_WIDTH, 2.0), layout="constrained")
    ax.plot(SIZES, res["mean_error"].mean(0), label=f"mean of {REPEATS} runs")
    ax.set(xlabel="samples", ylabel="|sample mean|", title="(a) placeholder")
    ax.legend()
    save(fig, figdir, "fig1")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--jobs", type=int, default=os.process_cpu_count())
    parser.add_argument("--plots-only", action="store_true")
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be 1 or more")
    args.out.mkdir(parents=True, exist_ok=True)
    info_file = args.out / "run_info.json"
    if not args.plots_only:
        start = time.perf_counter()
        res = run_all(args.jobs)
        np.savez_compressed(args.out / "results.npz", **res)
        info = dict(seed=SEED, repeats=REPEATS, sizes=SIZES.tolist(), jobs=args.jobs,
                    seconds=round(time.perf_counter() - start, 1), python=platform.python_version(),
                    numpy=np.__version__, scipy=scipy.__version__, scikit_learn=sklearn.__version__)
        info_file.write_text(json.dumps(info, indent=2) + "\n")
        print(f"experiments done in {info['seconds']} s")
    make_figures(args.out)
    import matplotlib
    info = json.loads(info_file.read_text())
    info["matplotlib"] = matplotlib.__version__  # the version that drew the figures, also after --plots-only
    info_file.write_text(json.dumps(info, indent=2) + "\n")
    print(f"figures written to {args.out / 'figures'}")


if __name__ == "__main__":
    main()
