"""Fail if private strings or co-author trailers would leave the machine with the next push.

Usage (repository root):
  uv run .agents/skills/privacy-safe-commits/scripts/scan_private.py [--secret TEXT ...]

Secrets default to every value in the repository's *.local.json files. Checked: staged files
(contents, raw PDF bytes, PDF text and metadata, file names) and every commit not yet on the
upstream branch (tree contents, PDFs inside it, file names, commit messages).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ATTRIBUTION = re.compile(r"co-authored-by|assisted-by|generated (with|by)", re.I)


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def local_secrets(root):
    found = set()
    for f in root.rglob("*.local.json"):
        if not {".git", ".venv"} & set(f.parts):
            found |= {str(x).strip() for x in json.loads(f.read_text()).values() if str(x).strip()}
    return found


def leaks(path, secret):
    raw = path.read_bytes()
    u16 = secret.encode("utf-16-be")
    where = []
    if secret.encode() in raw or u16 in raw or u16.hex().upper().encode() in raw.upper():
        where.append("raw bytes")
    if raw[:5] == b"%PDF-":
        text = "".join(subprocess.run([tool, str(path), *extra], capture_output=True, text=True).stdout
                       for tool, extra in (("pdftotext", ["-"]), ("pdfinfo", [])))
        if secret in text:
            where.append("PDF text or metadata")
    return where


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", action="append", default=[])
    root = Path(git("rev-parse", "--show-toplevel").strip())
    secrets = set(ap.parse_args().secret) | local_secrets(root)
    if not secrets:
        sys.exit("no secrets: pass --secret or create a *.local.json file")
    problems = []

    for rel in filter(None, git("diff", "--cached", "--name-only", "-z").split("\0")):
        path = root / rel
        for s in secrets:
            if s in rel:
                problems.append(f"staged file name: {rel}")
            if path.is_file():
                problems += [f"staged {rel}: {w}" for w in leaks(path, s)]

    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}").strip()
    for rev in git("rev-list", f"{upstream}..HEAD" if upstream else "HEAD").split():
        message = git("log", "-1", "--format=%B", rev)
        if ATTRIBUTION.search(message):
            problems.append(f"commit {rev[:7]}: message has a co-author or generated-by line")
        names = list(filter(None, git("ls-tree", "-r", "-z", "--name-only", rev).split("\0")))  # -z: no quoting of non-ASCII names
        for s in secrets:
            if s in message:
                problems.append(f"commit {rev[:7]}: secret in message")
            problems += [f"commit {rev[:7]}: secret in file name {n}" for n in names if s in n]
            problems += [f"commit {rev[:7]}: secret in {n}" for n in filter(None, git("grep", "-z", "-a", "-l", "-F", s, rev).split("\0"))]
        for name in (n for n in names if n.lower().endswith(".pdf")):
            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
                tmp.write(subprocess.run(["git", "show", f"{rev}:{name}"], capture_output=True).stdout)
                tmp.flush()
                for s in secrets:
                    problems += [f"commit {rev[:7]} {name}: {w}" for w in leaks(Path(tmp.name), s)]

    print("\n".join(sorted(set(problems))) or f"clean: {len(secrets)} secret(s) checked")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
