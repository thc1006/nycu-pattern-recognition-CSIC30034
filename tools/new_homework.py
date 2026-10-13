"""Start homework N from common/skeleton/:  uv run tools/new_homework.py N

Creates homeworkN/PR_HWN/ with its file names, imports, paths and \\assignment numbered for this homework.
Writes nothing unless every file can be numbered. results/, __pycache__/ and hidden files are not copied.
"""
import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKELETON = ROOT / "common" / "skeleton"
# N is the homework number where it directly follows homework, HW, hw, \assignment{ or build_report.py (also
# build\_report.py in LaTeX): homeworkN, PR_HWN, check_hwN, \assignment{N}, build_report.py N.
NUMBER = re.compile(r"(?:(?<=homework)|(?<=HW)|(?<=hw)|(?<=\\assignment\{)|(?<=build_report\.py )|(?<=build\\_report\.py ))"
                    r"N(?![A-Za-z0-9])")
# Any other lone N (HW N, 第 N 次, PR_HW{N}) is a number NUMBER does not reach.
LEFTOVER = re.compile(r"(?<![A-Za-z0-9\\])N(?![A-Za-z0-9_])")
SKIP = {"__pycache__", "results"}  # what running the skeleton in place leaves behind


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("n", type=int, help="homework number")
    n = ap.parse_args().n
    if n < 1:
        sys.exit("new_homework: the homework number must be 1 or more")
    dest = ROOT / f"homework{n}" / f"PR_HW{n}"
    if dest.parent.is_symlink():  # git would keep the link, not the homework
        sys.exit(f"new_homework: {dest.parent.relative_to(ROOT)} is a symbolic link; make it an ordinary folder")
    if dest.parent.exists() and not dest.parent.is_dir():
        sys.exit(f"new_homework: {dest.parent.relative_to(ROOT)} exists and is not a folder")
    if dest.exists() or dest.is_symlink():
        sys.exit(f"new_homework: {dest.relative_to(ROOT)} already exists")
    files, left = {}, []
    for src in sorted(SKELETON.rglob("*")):
        rel = src.relative_to(SKELETON)
        if not src.is_file() or any(p in SKIP or p.startswith(".") for p in rel.parts):
            continue
        out = NUMBER.sub(str(n), str(rel))
        data = src.read_bytes()
        try:
            text = NUMBER.sub(str(n), data.decode("utf-8"))
        except UnicodeDecodeError:  # copied as is
            text = None
        if LEFTOVER.search(f"{out}\n{text or ''}"):
            left.append(str(rel))
        files[out] = data if text is None else text.encode("utf-8")
    if not files:
        sys.exit(f"new_homework: {SKELETON.relative_to(ROOT)} has no files")
    if left:
        sys.exit(f"new_homework: nothing written; a lone N is left in {left}. "
                 "Write N right after homework, HW, hw, \\assignment{ or build_report.py, as in PR_HWN or check_hwN.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    # a folder of this run's own, renamed to dest once every file is written; a second run cannot touch it
    part = Path(tempfile.mkdtemp(prefix=f".{dest.name}.part-", dir=dest.parent))
    umask = os.umask(0)
    os.umask(umask)
    try:
        part.chmod(0o777 & ~umask)  # mkdtemp makes it owner-only; the homework folder should be an ordinary one
        for out, data in files.items():
            (part / out).parent.mkdir(parents=True, exist_ok=True)
            (part / out).write_bytes(data)
        part.rename(dest)
    except BaseException:
        shutil.rmtree(part, ignore_errors=True)
        raise
    print(f"created {dest.relative_to(ROOT)}/: " + ", ".join(sorted(files)))
    print(f"next: save the assignment as homework{n}/PR_HW{n}.pdf and its text as homework{n}/PR_HW{n}_full_transcription.md,\n"
          f"      set \\title and \\pagelimit in report/template.tex and replace the placeholder experiment, then run\n"
          f"      uv run homework{n}/PR_HW{n}/check_hw{n}.py, uv run homework{n}/PR_HW{n}/pr_hw{n}.py and uv run tools/build_report.py {n}")


if __name__ == "__main__":
    main()
