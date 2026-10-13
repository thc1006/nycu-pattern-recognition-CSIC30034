"""Checks on a typeset report PDF (needs poppler-utils: pdfinfo, pdffonts, pdftotext, pdftoppm).

Usage (repository root):
  uv run tools/check_pdf.py homeworkN/PR_HWN/report/report.pdf --aux homeworkN/PR_HWN/report/report.aux \\
      --max-pages 5 --require NAME

The body ends at label prhw@body-end, which \\codeappendix in common/prhw.cls writes; --max-pages needs --aux.
After tools/build_report.py, report/report.pdf is the public copy; that tool runs the same checks on every PDF it
writes. HW1 does not use the class: check it with --label body-end and the aux file of its own build,
homework1/PR_HW1/report/report.aux, which is not in git.
"""
import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TIMEOUT = 300  # seconds for one poppler call


def run(*cmd):
    try:
        p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, errors="replace", timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        return -1, "", f"{cmd[0]} took longer than {TIMEOUT} s"
    except FileNotFoundError:
        return -1, "", f"{cmd[0]} not found (install poppler-utils)"
    return p.returncode, p.stdout, p.stderr


def check(pdf, aux=None, label="prhw@body-end", max_pages=None, require=()):
    """Return (pages, last page of the body or None when it is unknown, problems)."""
    code, info, err = run("pdfinfo", pdf)
    m = re.search(r"^Pages:\s+(\d+)", info, re.M)
    if code or not m:
        return 0, None, [f"pdfinfo cannot read {pdf}: {err.strip() or 'no page count'}"]
    pages = int(m.group(1))
    problems = []
    body = pages
    if aux:
        text = Path(aux).read_text(encoding="utf-8", errors="replace") if Path(aux).is_file() else ""
        found = re.findall(r"\\newlabel\{" + re.escape(label) + r"\}\{\{[^}]*\}\{(\d+)\}", text)
        body = int(found[0]) if len(found) == 1 else None
        if body is None:
            problems.append(f"label {label} appears {len(found)} times in {aux}, expected once" if Path(aux).is_file()
                            else f"aux file not found: {aux}")
        elif not 1 <= body < pages:  # the code appendix follows the body, so the body ends before the last page
            problems.append(f"body ends on page {body} but the PDF has {pages} pages: stale aux or no appendix")
            body = None
        elif max_pages is not None and body > max_pages:
            problems.append(f"body has {body} pages, limit is {max_pages}")

    _, fonts, _ = run("pdffonts", pdf)
    for line in fonts.splitlines()[2:]:
        cols = line.split()
        if "Type 3" in line:
            problems.append(f"Type 3 font (bitmap-like): {cols[0]}")
        if len(cols) >= 5 and cols[-5] == "no":
            problems.append(f"font not embedded: {cols[0]}")
    with tempfile.TemporaryDirectory() as tmp:  # render every page; poppler reports font and stream problems here
        code, _, err = run("pdftoppm", "-r", "20", "-png", pdf, f"{tmp}/p")
    problems += [f"renderer: {line}" for line in sorted(set(err.splitlines()))]
    if code:
        problems.append(f"pdftoppm exited with status {code}")

    _, first, _ = run("pdftotext", "-f", "1", "-l", "1", "-layout", pdf, "-")
    problems += [f"page 1 lacks {text!r}" for text in require if text not in first]
    _, text, _ = run("pdftotext", "-f", "1", "-l", str(body), "-layout", pdf, "-") if body else (0, "", "")
    for pattern, why in ((r"\?\?", "unresolved reference (??)"),
                         (r"<<\w+>>|«[^»\n]{0,40}»", "unfilled template key (TeX prints << >> as « »)"),
                         (r"\\[a-zA-Z]+", "raw LaTeX command in text"), ("\ufffd", "replacement character")):
        for m in re.finditer(pattern, text):
            problems.append(f"{why}: …{text[max(m.start() - 20, 0):m.end() + 20]!r}…")
    return pages, body, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--aux", help="aux file holding the label that marks the end of the body")
    ap.add_argument("--label", default="prhw@body-end")
    ap.add_argument("--max-pages", type=int, help="page limit for the body")
    ap.add_argument("--require", action="append", default=[], help="text that must appear on page 1")
    a = ap.parse_args()
    if a.max_pages is not None and not a.aux:
        ap.error("--max-pages needs --aux: the body ends at a label in the aux file")
    pages, body, problems = check(a.pdf, a.aux, a.label, a.max_pages, a.require)
    print(f"pages: {pages}")
    if a.aux and body:
        print(f"body ends on page {body}")
    print("\n".join(f"PROBLEM: {p}" for p in problems) or "all checks passed")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
