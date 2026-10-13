"""Fail if private strings, or trailers and generated-with lines in commit messages, would leave with the next push.

Usage (repository root):
  uv run tools/scan_private.py [--secret TEXT ...]

Secrets default to every text or number in the repository's *.local.json files. Checked, ignoring case: staged
files as they are in the index (contents, PDF text, metadata and compressed objects, zip members, file names) and
every commit not yet on the upstream branch (all files in it, file names, message, author and committer). Text is
also compared with whitespace removed and full-width digits folded, so for 123456789 the forms "123 456 789" and
"１２３４５６７８９" count too. From any folder it checks the whole index and every unpushed commit; it does not read
untracked files or unstaged changes, except files added with git add -N. Its output never shows a secret.
"""
import argparse
import functools
import io
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path

# trailers such as Co-authored-by: or Signed-off-by:, and "generated with/by/using" lines that carry a link or
# start with a symbol; a plain "Generated with uv run pr_hw2.py" line (how results were made) passes
ATTRIBUTION = re.compile(r"^\W*[\w-]+-by\s*:"
                         r"|^\W*generated\s+(with|by|using)\b.*(\]\(|https?://)"
                         r"|^[^\w\s]+\s*generated\s+(with|by|using)\b", re.I | re.M)
MIN_SECRET = 4  # a shorter value would match nearly every file
TIMEOUT = 300  # seconds for one poppler call; a PDF that takes longer counts as unreadable


def git(root, *args, check=True):
    """stdout of git -C root args; a failure stops the scan instead of letting it pass."""
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if check and p.returncode:
        sys.exit(f"scan_private: git {' '.join(args)} failed: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout if p.returncode == 0 else b""


def local_secrets(root):
    """Every text or integer value in the *.local.json files under root, outside hidden folders such as .git and .venv."""
    found = set()
    for f in root.rglob("*.local.json"):
        if not any(p.startswith(".") for p in f.relative_to(root).parts[:-1]):  # e.g. an editor's settings.local.json
            data = json.loads(f.read_text())
            if isinstance(data, dict):
                found |= {str(x).strip() for x in data.values()
                          if isinstance(x, (str, int)) and not isinstance(x, bool) and len(folded(str(x))) >= MIN_SECRET}
    return found


def mask(text, secrets, token="<secret>"):
    """text with every secret replaced, also when spaced out or in full-width forms (such lines are shown in NFKC)."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if any(folded(s) in folded(line) for s in secrets):
            line = unicodedata.normalize("NFKC", line)
            for s in secrets:
                line = re.sub(r"\s*".join(re.escape(c) for c in folded(s)), token, line, flags=re.I)
            lines[i] = line
    return "\n".join(lines)


def folded(text):
    """Text with full-width forms folded (NFKC), all whitespace removed, and case folded."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).casefold()


@functools.cache
def byte_forms(secret):
    """The secret as bytes in the encodings files use (numpy stores str arrays as UTF-32), plain and as hex.
    The hex forms cover the secret as written, in lower case and in upper case: lowering a file changes no hex digit."""
    encodings = ("utf-8", "utf-16-be", "utf-16-le", "utf-32-le")
    forms = {secret.lower().encode(enc) for enc in encodings}
    return forms | {s.encode(enc).hex().encode() for s in {secret, secret.lower(), secret.upper()} for enc in encodings}


def has_bytes(data, secret):
    """Case-insensitive search for any byte form of the secret."""
    low = bytes(data).lower()
    return any(f in low for f in byte_forms(secret))


def pdf_text(path):
    """Extracted text, including text placed off the page, plus the Info dictionary and XMP metadata; None on a hang."""
    wide = ["-x", "-20000", "-y", "-20000", "-W", "40000", "-H", "40000"]
    out = []
    for cmd in (["pdftotext", *wide, str(path), "-"], ["pdfinfo", str(path)], ["pdfinfo", "-meta", str(path)]):
        try:
            out.append(subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=TIMEOUT).stdout)
        except subprocess.TimeoutExpired:
            return None
        except FileNotFoundError:
            sys.exit(f"scan_private: {cmd[0]} not found; PDFs cannot be checked without poppler-utils")
    return "".join(out)


def pdf_chunks(raw):
    """The PDF itself and every Flate stream in it, decompressed (object streams, embedded files, XMP)."""
    yield raw
    for m in re.finditer(rb"stream\r?\n", raw):
        end = raw.find(b"endstream", m.end())
        try:
            yield zlib.decompressobj().decompress(memoryview(raw)[m.end():end if end > 0 else None])
        except zlib.error:
            continue


def pdf_strings(chunk):
    """Literal (...) and hex <...> strings in PDF syntax, unescaped and decoded (UTF-16 with a BOM, else Latin-1)."""
    escapes = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}

    def unescape(m):
        e = m.group(1)
        if re.fullmatch(rb"[0-7]{1,3}", e):
            return bytes([int(e, 8) & 0xFF])
        return b"" if e in (b"\r\n", b"\n", b"\r") else escapes.get(e, e)  # an unknown escape keeps the character

    def decode(b):
        return b[2:].decode("utf-16-be", "replace") if b[:2] == b"\xfe\xff" else b.decode("latin-1")

    for m in re.finditer(rb"\((?:\\.|[^\\()])*\)", chunk, re.S):
        yield decode(re.sub(rb"\\([0-7]{1,3}|\r\n|.)", unescape, m.group()[1:-1], flags=re.S))
    for m in re.finditer(rb"(?<!<)<([0-9A-Fa-f\s]+)>(?!>)", chunk):
        h = re.sub(rb"\s", b"", m.group(1))
        yield decode(bytes.fromhex((h + b"0" * (len(h) % 2)).decode()))


def leaks(path, secret):
    """Where secret shows up in the file: raw bytes, text, zip members, or for a PDF its text, metadata and objects."""
    raw = Path(path).read_bytes()
    where = ["raw bytes"] if has_bytes(raw, secret) else []
    want = folded(secret)
    if raw[:5] == b"%PDF-":
        text = pdf_text(path)
        if text is None:
            where.append("PDF could not be read in time")
        elif want in folded(text):
            where.append("PDF text or metadata")
        if any(has_bytes(c, secret) or any(want in folded(s) for s in pdf_strings(c)) for c in pdf_chunks(raw)):
            where.append("PDF objects")
    elif raw[:4] == b"PK\x03\x04" or zipfile.is_zipfile(io.BytesIO(raw)):  # .npz, .docx and the like, broken ones too
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                where += [f"zip member {i.filename}" for i in z.infolist()
                          if has_bytes(z.read(i), secret) or want in folded(i.filename)]
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, zlib.error):
            where.append("zip that cannot be read")  # unreadable means unchecked, so it counts against the push
    else:
        try:
            if want in folded(raw.decode("utf-8")) and not where:
                where.append("text")
        except UnicodeDecodeError:
            pass
    return where


def in_name(name, secrets):
    return any(folded(s) in folded(name) for s in secrets)


def in_content(data, secrets):
    """Where any secret shows up in one file version (written to a temporary file for the PDF tools)."""
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(data)
        tmp.flush()
        return sorted({where for s in secrets for where in leaks(tmp.name, s)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret", action="append", default=[])
    args = ap.parse_args()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode:
        sys.exit("scan_private: not inside a git repository")
    root = Path(top.stdout.strip())
    secrets = {s.strip() for s in args.secret if s.strip()} | local_secrets(root)
    if not secrets:
        sys.exit("scan_private: no secrets; pass --secret or create a *.local.json file")
    problems = []

    # Each staged file as the next commit will contain it: ":old_mode new_mode old_sha new_sha status\0path\0".
    raw = git(root, "diff", "--cached", "--raw", "-z", "--no-renames", "--no-abbrev", "--diff-filter=d")
    fields = raw.decode(errors="surrogateescape").split("\0")  # keeps non-UTF-8 names usable as paths
    for info, rel in zip(fields[0::2], fields[1::2]):
        _, mode, _, sha, status = info.split()
        if in_name(rel, secrets):
            problems.append(f"staged file name: {rel}")
        if status == "U":
            problems.append(f"staged {rel}: unmerged; resolve the conflict and scan again")
        elif mode != "160000":  # a submodule entry is a commit, not file content
            problems += [f"staged {rel}: {w}" for w in in_content(git(root, "cat-file", "blob", sha), secrets)]
    # git add -N entries are left out of --cached, and commit -a would take their work-tree content
    added = git(root, "diff", "--name-only", "--diff-filter=A", "-z").decode(errors="surrogateescape").split("\0")
    for rel in filter(None, added):
        if in_name(rel, secrets):
            problems.append(f"staged file name: {rel}")
        if (root / rel).is_file():
            problems += [f"staged {rel} (git add -N): {w}" for w in in_content((root / rel).read_bytes(), secrets)]

    if git(root, "rev-parse", "--verify", "-q", "HEAD", check=False):
        upstream = git(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}", check=False).decode().strip()
        seen = {}
        for rev in git(root, "rev-list", f"{upstream}..HEAD" if upstream else "HEAD").decode().split():
            message = git(root, "log", "-1", "--format=%B", rev).decode(errors="replace")
            people = git(root, "log", "-1", "--format=%an <%ae>%n%cn <%ce>", rev).decode(errors="replace")
            if ATTRIBUTION.search(message):
                problems.append(f"commit {rev[:7]}: message has a trailer such as Co-authored-by: or a generated-with line")
            trailers = git(root, "-c", "trailer.separators=:", "log", "-1", "--format=%(trailers:only,unfold)", rev)
            trailers = trailers.decode(errors="replace")  # the separator is pinned: a configured one would hide Key: value
            if keys := sorted({line.split(":", 1)[0].strip() for line in trailers.splitlines() if ":" in line}):
                problems.append(f"commit {rev[:7]}: message ends with trailers ({', '.join(keys)})")  # as git parses them
            if in_name(f"{message}\n{people}", secrets):
                problems.append(f"commit {rev[:7]}: secret in message, author or committer")
            for entry in filter(None, git(root, "ls-tree", "-r", "-z", "--full-tree", rev).decode(errors="replace").split("\0")):
                info, name = entry.split("\t", 1)
                _, kind, sha = info.split()
                if kind != "blob":
                    continue
                if in_name(name, secrets):
                    problems.append(f"commit {rev[:7]}: secret in file name {name}")
                if sha not in seen:  # a file unchanged across commits is read once
                    seen[sha] = in_content(git(root, "cat-file", "blob", sha), secrets)
                problems += [f"commit {rev[:7]} {name}: {w}" for w in seen[sha]]

    report = mask("\n".join(sorted(set(problems))), secrets)  # file names can hold a secret; keep it out of the output
    report = report.encode("utf-8", "surrogateescape").decode("utf-8", "replace")  # printable non-UTF-8 names
    print(report or f"clean: {len(secrets)} secret(s) checked")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
