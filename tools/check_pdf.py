"""Pre-submission checks for a XeLaTeX report PDF (needs poppler-utils: pdfinfo, pdffonts, pdftotext, pdftoppm).

Usage (repository root):
  uv run .agents/skills/xelatex-cjk-report/scripts/check_pdf.py REPORT.pdf --aux REPORT.aux \
      --label body-end --max-pages 5 --require 姓名 --require 學號
"""
import argparse
import re
import subprocess
import sys


def run(*cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    return p.stdout, p.stderr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--aux", help="aux file holding the label that marks the end of the body")
    ap.add_argument("--label", default="body-end")
    ap.add_argument("--max-pages", type=int, help="page limit for the body")
    ap.add_argument("--require", action="append", default=[], help="text that must appear on page 1")
    a = ap.parse_args()
    problems = []

    info, _ = run("pdfinfo", a.pdf)
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    print(f"pages: {pages}")

    body = pages
    if a.aux:
        aux = open(a.aux, encoding="utf-8").read()
        m = re.search(r"\\newlabel\{" + re.escape(a.label) + r"\}\{\{[^}]*\}\{(\d+)\}", aux)
        if not m:
            problems.append(f"label {a.label} not found in {a.aux}")
        else:
            body = int(m.group(1))
            print(f"body ends on page {body}")
            if a.max_pages and body > a.max_pages:
                problems.append(f"body has {body} pages, limit is {a.max_pages}")

    fonts, _ = run("pdffonts", a.pdf)
    for line in fonts.splitlines()[2:]:
        cols = line.split()
        if "Type 3" in line:
            problems.append(f"Type 3 font (bitmap-like): {cols[0]}")
        if len(cols) >= 5 and cols[-5] == "no":
            problems.append(f"font not embedded: {cols[0]}")
    _, err = run("pdftoppm", "-r", "20", "-png", a.pdf, "/dev/null")
    warnings = sorted(set(l for l in err.splitlines() if "Warning" in l or "Error" in l))
    problems += [f"renderer: {w}" for w in warnings]

    first, _ = run("pdftotext", "-f", "1", "-l", "1", "-layout", a.pdf, "-")
    for text in a.require:
        if text not in first:
            problems.append(f"page 1 lacks {text!r}")
    text, _ = run("pdftotext", "-f", "1", "-l", str(body), "-layout", a.pdf, "-")
    for pattern, why in ((r"\?\?", "unresolved reference (??)"), (r"<<\w+>>", "unfilled template key"),
                         (r"\\[a-zA-Z]+", "raw LaTeX command in text"), ("\ufffd", "replacement character")):
        for m in re.finditer(pattern, text):
            problems.append(f"{why}: …{text[max(m.start() - 20, 0):m.end() + 20]!r}…")

    print("\n".join(f"PROBLEM: {p}" for p in problems) or "all checks passed")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
