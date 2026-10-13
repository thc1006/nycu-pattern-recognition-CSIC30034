"""Fail if the next commit or push would carry private strings, or commit messages that are not plain text.

Usage (repository root):
  uv run tools/scan_private.py [--secret TEXT ...]   # before each commit and push
  uv run tools/scan_private.py --all-history         # before making the repository public
  uv run tools/scan_private.py --install-hooks       # once per clone, and again after this file changes
The hooks live in .git/hooks and run a copy of this file kept there: --staged before each commit, --message on each
commit message, and --pre-push REMOTE before each push.

Secrets are the --secret values plus every text or number of 4 or more characters in the *.local.json files of this
work tree and of the main work tree. Checked, ignoring case:
- staged files as they are in the index, and files added with git add -N (default mode and --staged);
- the author and committer git would give the next commit (default mode and --staged);
- every object the next push would send: what local branches, tags and HEAD hold that no remote-tracking branch has
  (with --all-history, everything on any ref but the stash; with --pre-push, what that push sends): file contents
  and names, folder names, commit messages, authors, committers and merged tags, annotated tags, and ref names;
- commit messages, which must be plain text: no lines such as Signed-off-by:, no trailers such as Change-Id: or
  Made-with:, no emoji, no Markdown links.
Each file is read as bytes and as text, and by kind: a PDF's text, metadata, objects and attached files; the members
of a zip, tar, gzip, bzip2 or xz file (a PDF inside a zip is read as a PDF); a bare zlib or legacy .lzma stream, as
joblib writes; a PNG's text chunks. Text is compared with whitespace and invisible characters removed and full-width
forms folded, so for 123456789 the forms "123 456 789" and "１２３４５６７８９" count too. A file in a format it knows
but cannot read (an encrypted or damaged PDF or zip, 7z, rar, zstd, lz4, lzip, .Z, a Git LFS pointer) counts as a
problem. Not read: text drawn inside an image, data compressed inside other formats (a compressed .mat, HDF5 or Parquet
file), and untracked files. The output never shows a secret.
"""
import argparse
import bz2
import functools
import gzip
import io
import json
import lzma
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
import zipfile
import zlib
from pathlib import Path

# commit messages stay plain text: no lines such as Signed-off-by: (also where git would not parse them as trailers),
# no emoji (keycaps and the emoji variation selector included) and no Markdown links
NOT_PLAIN = re.compile(r"^\W*[\w-]+-by\s*:|\[[^\]\n]*\]\([^)\s]+\)"
                       r"|[\u20e3\u231a\u231b\u23e9-\u23fa\u25fd\u25fe\u2600-\u27bf\u2b00-\u2bff\ufe0f\U0001f000-\U0001faff]",
                       re.I | re.M)
MIN_SECRET = 4  # a shorter value would match nearly every file
TIMEOUT = 300  # seconds for one poppler call; a PDF that takes longer counts as unreadable
LIMIT = 256 * 2**20  # bytes one file may unpack to, archives inside it included; past that it counts as unreadable
DEPTH = 3  # archives inside archives
PNG = b"\x89PNG\r\n\x1a\n"
LFS = b"version https://git-lfs.github.com/spec/"
UNSUPPORTED = {b"7z\xbc\xaf\x27\x1c": "7z", b"Rar!\x1a\x07": "rar", b"\x28\xb5\x2f\xfd": "zstd",
               b"\x04\x22\x4d\x18": "lz4", b"LZIP": "lzip", b"\x1f\x9d": "compress (.Z)"}
HOOKS = {"pre-commit": "--staged", "commit-msg": '--message "$1"', "pre-push": '--pre-push "$1"'}
MARK = "# Installed by tools/scan_private.py --install-hooks; it runs the copy saved next to it."
SIGNATURES = (b"%PDF-", b"PK\x03\x04", b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00", PNG, *UNSUPPORTED)  # files attached to a PDF
budget = [LIMIT]  # bytes the file being read may still unpack to
masked = set()  # secrets to hide in error messages, set by main()


class Unreadable(Exception):
    """A file whose content cannot be checked; it counts against the push."""


def git(root, *args, check=True, stdin=None):
    """stdout of git -C root args, without replace refs; a failure stops the scan instead of letting it pass."""
    p = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *args], capture_output=True, input=stdin)
    if check and p.returncode:  # git's message may name a ref that holds a secret
        sys.exit(f"scan_private: git {shown(' '.join(args), masked)} failed: "
                 f"{mask(p.stderr.decode(errors='replace').strip(), masked)}")
    return p.stdout if p.returncode == 0 else b""


def has_object(root, sha):
    return subprocess.run(["git", "--no-replace-objects", "-C", str(root), "cat-file", "-e", sha],
                          capture_output=True).returncode == 0


def local_secrets(root):
    """Every text or integer value in the *.local.json files under root, outside hidden folders such as .git and .venv."""
    found = set()
    for f in root.rglob("*.local.json"):
        if not any(p.startswith(".") for p in f.relative_to(root).parts[:-1]):
            try:
                data = json.loads(f.read_text())
            except ValueError as err:
                sys.exit(f"scan_private: {f} is not valid JSON ({err})")
            if isinstance(data, dict):
                found |= {str(x).strip() for x in data.values()
                          if isinstance(x, (str, int)) and not isinstance(x, bool) and len(folded(str(x))) >= MIN_SECRET}
    return found


def common_dir(root):
    """The repository's .git folder, which its linked work trees share."""
    return Path(git(root, "rev-parse", "--path-format=absolute", "--git-common-dir").decode().strip())


def main_worktree(root):
    """The main work tree of the repository at root (where *.local.json lives when root is a linked work tree)."""
    common = common_dir(root)
    return common.parent if common.name == ".git" else root


@functools.cache
def format_chars():
    """Characters that show as nothing: format characters (Unicode category Cf) such as zero-width spaces, the other
    default-ignorable ones such as variation selectors and Hangul fillers, and the blank Braille pattern."""
    other = {0x34F, 0x115F, 0x1160, 0x17B4, 0x17B5, *range(0x180B, 0x1810), 0x2065, 0x2800, 0x3164, *range(0xFE00, 0xFE10),
             0xFFA0, *range(0xFFF0, 0xFFF9), *range(0xE0000, 0xE1000)}
    return {c: None for c in range(0x110000) if c in other or unicodedata.category(chr(c)) == "Cf"}


@functools.cache
def gap():
    return "[\\s" + re.escape("".join(map(chr, format_chars()))) + "]*"


def spread(secret):
    """A pattern for secret in NFKC text, whitespace and invisible characters allowed between its characters (use re.I)."""
    return gap().join(re.escape(c) for c in folded(secret))


def mask(text, secrets, token="<secret>"):
    """text with every secret replaced, also when spaced out or in full-width forms (such lines are shown in NFKC)."""
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if any(folded(s) in folded(line) for s in secrets):
            line = unicodedata.normalize("NFKC", line)
            for s in secrets:
                line = re.sub(spread(s), token, line, flags=re.I)
            lines[i] = line
    return "\n".join(lines)


def shown(name, secrets, token="<secret>"):
    """A file or ref name fit to print: secrets masked (also across line breaks in the name), control characters
    escaped."""
    name = unicodedata.normalize("NFKC", name)
    for s in secrets:
        name = re.sub(spread(s), token, name, flags=re.I)
    return re.sub(r"[\x00-\x1f\x7f]", lambda m: f"\\x{ord(m.group()):02x}", name)


def folded(text):
    """Text with full-width forms folded (NFKC), whitespace and invisible format characters removed, and case folded."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text).translate(format_chars())).casefold()


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


def spend(size, what):
    """Count size unpacked bytes against the file's budget."""
    budget[0] -= size
    if budget[0] < 0:
        raise Unreadable(f"{what} that unpacks past {LIMIT >> 20} MB")


def pdf_text(raw):
    """Text (also placed off the page), the Info dictionary with custom keys, and XMP metadata; None when poppler
    fails on the file or takes longer than TIMEOUT, or the file is encrypted (its objects cannot be read)."""
    wide = ["-x", "-20000", "-y", "-20000", "-W", "40000", "-H", "40000"]
    out = []
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(raw)
        tmp.flush()
        for cmd in (["pdftotext", *wide, tmp.name, "-"], ["pdfinfo", tmp.name], ["pdfinfo", "-custom", tmp.name],
                    ["pdfinfo", "-meta", tmp.name]):
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=TIMEOUT)
            except subprocess.TimeoutExpired:
                return None
            except FileNotFoundError:
                sys.exit(f"scan_private: {cmd[0]} not found; PDFs cannot be checked without poppler-utils")
            if p.returncode:
                return None
            out.append(p.stdout)
    return None if re.search(r"^Encrypted:\s+yes", out[1], re.M) else "".join(out)


def inflate_pdf(data):
    """A PDF Flate stream decompressed as far as it goes, b"" for data with no zlib header. The checksum at the end is
    not checked: zlib drops all it got from the call that finds a bad one, and poppler shows such streams anyway."""
    if len(data) < 2 or data[0] & 0x0F != 8 or (data[0] << 8 | data[1]) % 31:
        return b""
    d, out = zlib.decompressobj(-15), bytearray()  # raw deflate, from after the 2-byte header
    for i in range(2, len(data), 1 << 16):
        try:
            out += d.decompress(data[i:i + (1 << 16)], LIMIT + 1 - len(out))
        except zlib.error:
            break
        if len(out) > LIMIT:
            raise Unreadable(f"PDF stream that unpacks past {LIMIT >> 20} MB")
        if d.eof:
            break
    spend(len(out), "PDF")
    return bytes(out)


def pdf_chunks(raw):
    """The PDF itself and its streams: Flate data decompressed (object streams, attached files, XMP), and other data
    that starts like a file, such as an attachment stored as it is. Images are skipped: their data holds no text, and
    decompressed it can run to hundreds of MB."""
    yield raw
    for m in re.finditer(rb"(?<!end)stream\r?\n", raw):
        head = raw[max(0, m.start() - 4096):m.start()]
        head = head[head.rfind(b"obj"):]  # the stream's own dictionary
        if re.search(rb"/Subtype\s*/Image\b", head):
            continue
        size = re.search(rb"/Length\s+(\d+)\b(?!\s+\d+\s+R)", head)
        stop = m.end() + int(size.group(1)) if size else -1
        if not size or not raw[stop:stop + 12].lstrip().startswith(b"endstream"):  # /Length missing, indirect or wrong
            stop = raw.find(b"endstream", m.end())  # which cuts an attached PDF at its own first endstream
        data = memoryview(raw)[m.end():stop if stop > 0 else None]
        if out := inflate_pdf(data):
            yield out
        elif bytes(data[:8]).startswith(SIGNATURES):
            yield bytes(data)


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


def inflate(opener, raw, what):
    """raw decompressed, several concatenated streams included, at most LIMIT bytes."""
    try:
        with opener(io.BytesIO(raw)) as f:
            out = f.read(LIMIT + 1)
    except (OSError, EOFError, ValueError, lzma.LZMAError, zlib.error) as err:
        raise Unreadable(f"{what} that cannot be read") from err
    if len(out) > LIMIT:
        raise Unreadable(f"{what} that unpacks past {LIMIT >> 20} MB")
    spend(len(out), what)
    return out


def inflate_zlib(data, what):
    """One zlib stream, decompressed, at most LIMIT bytes."""
    d = zlib.decompressobj()
    try:
        out = d.decompress(data, LIMIT + 1)
    except zlib.error as err:
        raise Unreadable(f"{what} that cannot be read") from err
    if len(out) > LIMIT or not d.eof:
        raise Unreadable(f"{what} that cannot be read")
    spend(len(out), what)
    return out


def unpack(raw):
    """(kind, [(name, bytes)]) for the members of a zip or tar file or the content of gzip, bzip2, xz, legacy lzma or
    zlib data; None for anything else. Raises Unreadable for formats it cannot open and for damaged or oversized ones."""
    for magic, kind in UNSUPPORTED.items():
        if raw.startswith(magic):
            raise Unreadable(f"{kind} file, which cannot be checked")
    if raw[:2] == b"\x1f\x8b":
        return "gzip", [("content", inflate(lambda f: gzip.GzipFile(fileobj=f), raw, "gzip file"))]
    if raw[:3] == b"BZh" and raw[3:4] in b"123456789" and raw[4:10] in (b"1AY&SY", b"\x17rE8P\x90"):
        return "bzip2", [("content", inflate(bz2.BZ2File, raw, "bzip2 file"))]
    if raw[:6] == b"\xfd7zXZ\x00":
        return "xz", [("content", inflate(lzma.LZMAFile, raw, "xz file"))]
    tar = raw[257:262] == b"ustar"
    # .npz, .docx and the like start with PK; a zip found only from its end comes after tar, which may end with one
    if raw[:4] == b"PK\x03\x04" or not tar and zipfile.is_zipfile(io.BytesIO(raw)):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                infos = [i for i in z.infolist() if not i.is_dir()]
                spend(sum(i.file_size for i in infos), "zip")
                return "zip", [(member_name(i), z.read(i)) for i in infos]
        except (zipfile.BadZipFile, RuntimeError, NotImplementedError, EOFError, ValueError, OSError, zlib.error,
                lzma.LZMAError) as err:
            raise Unreadable("zip that cannot be read") from err  # unreadable means unchecked, so it counts
    if tar:
        try:
            with tarfile.open(fileobj=io.BytesIO(raw)) as t:
                files = [m for m in t.getmembers() if m.isfile()]
                spend(sum(m.size for m in files), "tar")
                return "tar", [(m.name, t.extractfile(m).read()) for m in files]
        except (tarfile.TarError, OSError, EOFError) as err:
            raise Unreadable("tar that cannot be read") from err
    # legacy .lzma and bare zlib data have weak or no magic, so only a stream that decodes to its end counts
    lzma_alone = raw[:3] == b"\x5d\x00\x00"
    zlib_header = len(raw) > 1 and raw[0] & 0x8F == 8 and (raw[0] << 8 | raw[1]) % 31 == 0
    for kind, d in (("lzma", lzma.LZMADecompressor(lzma.FORMAT_ALONE) if lzma_alone else None),
                    ("zlib", zlib.decompressobj() if zlib_header else None)):
        try:
            out = d.decompress(raw, LIMIT + 1) if d else b""
        except (lzma.LZMAError, zlib.error):
            continue
        if len(out) > LIMIT:
            raise Unreadable(f"{kind} data that unpacks past {LIMIT >> 20} MB")
        if d and d.eof:
            spend(len(out), f"{kind} data")
            return kind, [("content", out)]
    return None


def member_name(info):
    """A zip member's name; zip tools often store UTF-8 names without setting the flag that says so."""
    if not info.flag_bits & 0x800:
        try:
            return info.filename.encode("cp437").decode("utf-8")
        except UnicodeError:
            pass
    return info.filename


def png_texts(raw):
    """The text of every tEXt, zTXt and iTXt chunk, decompressed where it is compressed."""
    texts, pos = [], 8
    while pos + 8 <= len(raw):
        size, kind = int.from_bytes(raw[pos:pos + 4], "big"), raw[pos + 4:pos + 8]
        body = raw[pos + 8:pos + 8 + size]
        pos += 12 + size
        key, _, rest = body.partition(b"\0")
        if kind == b"tEXt":
            texts.append(key.decode("latin-1") + rest.decode("latin-1"))
        elif kind == b"zTXt":
            texts.append(key.decode("latin-1") + inflate_zlib(rest[1:], "PNG text").decode("latin-1"))
        elif kind == b"iTXt":
            compressed = rest[:1] == b"\1"
            _, _, rest = rest[2:].partition(b"\0")  # language tag
            translated, _, text = rest.partition(b"\0")
            text = inflate_zlib(text, "PNG text") if compressed else text
            texts.append(translated.decode("utf-8", "replace") + text.decode("utf-8", "replace"))
    return texts


def is_text(raw):
    try:
        raw.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False


def pdf_leaks(raw, secret, want, depth):
    """Where secret shows up in a PDF: its text and metadata (through poppler), its objects and its attached files."""
    where = []
    text = pdf_text(raw)
    if text is None:
        where.append("PDF that cannot be read (encrypted, damaged or too slow)")
    elif want in folded(text):
        where.append("PDF text or metadata")
    for c in pdf_chunks(raw):
        if "PDF objects" not in where and (has_bytes(c, secret) or any(want in folded(s) for s in pdf_strings(c))):
            where.append("PDF objects")
        if c is not raw and c.startswith(SIGNATURES):
            if depth == 0:
                raise Unreadable("PDF attachment nested too deep to check")
            where += [f"PDF attachment: {w}" for w in leaks_in(c, secret, depth - 1)]
    return where


def leaks_in(raw, secret, depth=DEPTH):
    """Where secret shows up in one file's bytes: raw bytes, text, archive members, or a PDF's text, metadata and
    objects. A file that cannot be checked is reported too."""
    if depth == DEPTH:
        budget[0] = LIMIT
    where = ["raw bytes"] if has_bytes(raw, secret) else []
    want = folded(secret)
    try:
        if raw.startswith(LFS):
            raise Unreadable("Git LFS pointer; the file it stands for is not checked")
        if raw.startswith(b"%PDF-"):
            where += pdf_leaks(raw, secret, want, depth)
        elif raw.startswith(PNG):
            if any(want in folded(t) for t in png_texts(raw)):
                where.append("PNG text")
        elif unpacked := unpack(raw):  # before the loose PDF test: a tar may hold a PDF in its first 1024 bytes
            kind, members = unpacked
            if depth == 0:
                raise Unreadable(f"{kind} nested too deep to check")
            for name, data in members:
                if want in folded(name):
                    where.append(f"{kind} member name")
                where += [f"{kind} member {name}: {w}" for w in leaks_in(data, secret, depth - 1)]
        elif b"%PDF-" in raw[:1024] and not is_text(raw):  # bytes before the header, as some tools add
            where += pdf_leaks(raw, secret, want, depth)
        elif not where:
            text = raw.decode("utf-8", errors="replace")  # Latin-1 or Big5 text still shows an ASCII ID
            if want in folded(text) or "<" in text and want in folded(re.sub(r"<[^<>]*>", "", text)):
                where.append("text")  # markup such as <b>12</b>34 counts once its tags are dropped
    except Unreadable as err:
        where.append(str(err))
    return where


def leaks(path, secret):
    """Where secret shows up in the file at path (see leaks_in)."""
    return leaks_in(Path(path).read_bytes(), secret)


def decoded(data, encoding):
    """data as text in the given encoding (UTF-8 for one Python does not know), bad bytes replaced."""
    try:
        return data.decode(encoding, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def in_name(name, secrets):
    return any(folded(s) in folded(name) for s in secrets)


def in_content(data, secrets):
    """Where any secret shows up in one file version."""
    return sorted({shown(where, secrets) for s in secrets for where in leaks_in(data, s)})  # member names


def machine_key(key):
    """Whether a trailer key is commit metadata (Change-Id, Reviewed-on, Made-with, AI-assisted) rather than the start
    of a sentence or a result (Note:, k-NN:, Leave-one-out:)."""
    parts = key.lower().split("-")
    return len(parts) > 1 and (parts[-1] in ("by", "id", "on", "with") or parts[0] == "ai")


def message_problems(message, what, secrets, root):
    """The ways a commit message is not plain text."""
    problems = []
    if m := NOT_PLAIN.search(message):
        problems.append(f"{what}: message is not plain text at {shown(m.group().strip(), secrets)!r} "
                        "(a line such as Signed-off-by:, an emoji or a Markdown link)")
    # the separator is pinned (a configured one would hide Key: value); a commit keeps what follows a --- line
    trailers = git(root, "-c", "trailer.separators=:", "interpret-trailers", "--parse", "--no-divider",
                   stdin=message.encode()).decode(errors="replace")
    keys = {line.split(":", 1)[0].strip() for line in trailers.splitlines() if ":" in line}
    if keys := sorted(k for k in keys if machine_key(k)):
        problems.append(f"{what}: git reads the last paragraph as trailers ({shown(', '.join(keys), secrets)}); "
                        "reword those lines or add a sentence to that paragraph")
    return problems


def scan_staged(root, secrets):
    """Problems in the index (each staged file as the next commit will hold it) and in git add -N files; the count."""
    problems = []
    # ":old_mode new_mode old_sha new_sha status\0path\0" per staged file
    raw = git(root, "diff", "--cached", "--raw", "-z", "--no-renames", "--no-abbrev", "--diff-filter=d")
    fields = raw.decode(errors="surrogateescape").split("\0")  # keeps non-UTF-8 names usable as paths
    for info, rel in zip(fields[0::2], fields[1::2]):
        _, mode, _, sha, status = info.split()
        if in_name(rel, secrets):
            problems.append(f"staged file name: {shown(rel, secrets)}")
        if status == "U":
            problems.append(f"staged {shown(rel, secrets)}: unmerged; resolve the conflict and scan again")
        elif mode != "160000":  # a submodule entry is a commit, not file content
            problems += [f"staged {shown(rel, secrets)}: {w}" for w in in_content(git(root, "cat-file", "blob", sha), secrets)]
    # git add -N entries are left out of --cached, and commit -a would take their work-tree content
    added = list(filter(None, git(root, "diff", "--name-only", "--diff-filter=A", "-z").decode(errors="surrogateescape").split("\0")))
    for rel in added:
        if in_name(rel, secrets):
            problems.append(f"staged file name: {shown(rel, secrets)}")
        if (root / rel).is_file():
            problems += [f"staged {shown(rel, secrets)} (git add -N): {w}" for w in in_content((root / rel).read_bytes(), secrets)]
    return problems, len(fields) // 2 + len(added)


def scan_objects(root, rev_args, secrets):
    """Problems in every object `git rev-list --objects rev_args` lists (each object once); the number of commits."""
    listing = git(root, "rev-list", "--objects", *rev_args)
    if not listing.strip():
        return [], 0
    typed = git(root, "cat-file", "--batch-check=%(objectname) %(objecttype) %(rest)", stdin=listing)
    problems, commits = [], 0
    for line in typed.decode(errors="surrogateescape").splitlines():
        sha, kind, path = (line.split(" ", 2) + ["", ""])[:3]
        if kind == "commit":
            commits += 1
            data = git(root, "cat-file", "commit", sha)
            encoding = re.search(rb"^encoding (\S+)", data.partition(b"\n\n")[0], re.M)
            head, _, message = decoded(data, encoding.group(1).decode() if encoding else "utf-8").partition("\n\n")
            people = "\n".join(l for l in head.split("\n") if not l.startswith(("tree ", "parent ")))
            problems += message_problems(message, f"commit {sha[:7]}", secrets, root)
            parts = [part for part, text in (("message", message), ("author, committer or merged tag", people))
                     if in_name(text, secrets)]
            if parts or any(has_bytes(data, s) for s in secrets):
                problems.append(f"commit {sha[:7]}: secret in {' and '.join(parts) or 'its raw bytes'}")
        elif kind == "tag":
            data = git(root, "cat-file", "tag", sha)
            if in_name(data.decode(errors="replace"), secrets) or any(has_bytes(data, s) for s in secrets):
                problems.append(f"tag {shown(path, secrets) or sha[:7]}: secret in message or tagger")
        elif kind == "tree":
            for entry in filter(None, git(root, "ls-tree", "-z", sha).decode(errors="surrogateescape").split("\0")):
                name = entry.split("\t", 1)[1]
                if in_name(name, secrets):
                    problems.append(f"file or folder name {shown(name, secrets)} in {shown(path, secrets) or 'the top folder'}")
        elif kind == "blob":
            if found := in_content(git(root, "cat-file", "blob", sha), secrets):
                first = git(root, "log", "--reverse", "--format=%h", f"--find-object={sha}", *rev_args, check=False).split()
                added = f" (added in commit {first[0].decode()})" if first else ""
                problems += [f"{shown(path, secrets) or sha[:7]}{added}: {w}" for w in found]
    return problems, commits


def hooks_dir(root):
    """Git's own hooks folder of the repository; linked work trees share it, and it moves with the clone."""
    return common_dir(root) / "hooks"


def hooks_used(root):
    """The folder git takes hooks from: hooks_dir, unless core.hooksPath points elsewhere."""
    return Path(git(root, "rev-parse", "--path-format=absolute", "--git-path", "hooks").decode().strip())


def hooks_active(root):
    """Whether git runs the hooks --install-hooks wrote."""
    dest = hooks_dir(root)
    return hooks_used(root) == dest and (dest / "scan_private.py").is_file() and all(
        (dest / n).is_file() and os.access(dest / n, os.X_OK) and MARK in (dest / n).read_text(errors="replace")
        for n in HOOKS)


def install_hooks(root):
    """Write the hooks, and a copy of this file for them to run, into git's own hooks folder, so that they also run in
    linked work trees and old checkouts, which may lack tools/, and after the clone moves."""
    dest = hooks_dir(root)
    if hooks_used(root) != dest:
        sys.exit(f"scan_private: core.hooksPath is set, so git takes hooks from {hooks_used(root)}, not {dest}; "
                 "git config --show-origin --get core.hooksPath shows where; unset it there "
                 "(git config --global --unset core.hooksPath for a global one) and run this again")
    if other := [n for n in HOOKS if (dest / n).exists() and MARK not in (dest / n).read_text(errors="replace")]:
        sys.exit(f"scan_private: {dest} already has its own {', '.join(other)}; move it away and run this again")
    dest.mkdir(exist_ok=True)
    if Path(__file__).resolve() != (dest / "scan_private.py").resolve():
        shutil.copyfile(Path(__file__).resolve(), dest / "scan_private.py")
    uv = shutil.which("uv") or "uv"  # a full path: git clients started from a desktop may not have uv on PATH
    for name, args in HOOKS.items():
        hook = dest / name
        hook.write_text(f'#!/bin/sh\n{MARK}\nuv={shlex.quote(uv)}\n[ -x "$uv" ] || uv=uv\n'
                        f'exec "$uv" run --quiet --no-project "$(dirname "$0")/scan_private.py" {args}\n', newline="\n")
        hook.chmod(0o755)
    print(f"hooks installed in {dest}; run this again after tools/scan_private.py changes")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--secret", action="append", default=[], help="another value to look for")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--staged", action="store_true",
                      help="check the index and the next commit's author and committer (the pre-commit hook)")
    mode.add_argument("--all-history", action="store_true", help="check everything on any ref but the stash")
    mode.add_argument("--pre-push", metavar="REMOTE", help="check what git push sends to REMOTE (refs on stdin)")
    mode.add_argument("--message", metavar="FILE", help="check a commit message (the commit-msg hook)")
    mode.add_argument("--install-hooks", action="store_true", help="install the hooks for this clone")
    args = ap.parse_args()
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if top.returncode:
        sys.exit("scan_private: not inside a git repository")
    root = Path(top.stdout.strip())
    if args.install_hooks:
        return install_hooks(root)
    secrets = {s.strip() for s in args.secret if s.strip()} | local_secrets(root) | local_secrets(main_worktree(root))
    if not secrets:
        sys.exit("scan_private: no value of 4 or more characters in any *.local.json; create student.local.json "
                 '({"student_id": "..."}) or pass --secret')
    masked.update(secrets)
    here, mine, copy = Path(__file__).resolve(), root / "tools" / "scan_private.py", hooks_dir(root) / "scan_private.py"
    by_hook = here == copy.resolve()
    if by_hook or not (args.message or args.pre_push):  # a hook, or a scan run by hand
        if not by_hook and not hooks_active(root):
            print("scan_private: note: the git hooks are not active in this clone; run uv run tools/scan_private.py "
                  "--install-hooks", file=sys.stderr)
        elif mine.is_file() and copy.is_file() and mine.read_bytes() != copy.read_bytes():
            print("scan_private: note: tools/scan_private.py differs from the copy the hooks run; if tools/ holds the "
                  "newer one, run uv run tools/scan_private.py --install-hooks", file=sys.stderr)

    problems, staged, commits = [], 0, 0
    if args.message:
        encoding = git(root, "config", "--get", "i18n.commitEncoding", check=False).decode().strip() or "utf-8"
        text = decoded(Path(args.message).read_bytes(), encoding)
        text = re.split(r"^\S+ -{24} >8 -{24}$", text, maxsplit=1, flags=re.M)[0]  # git drops the diff of commit -v
        # "#" lines count, since git keeps them in a -m or -F message; git's "#\t<file>" status lines do not
        message = "\n".join(l for l in text.split("\n") if not l.startswith("#\t"))
        problems = message_problems(message, "commit message", secrets, root)
        if in_name(message, secrets):
            problems.append("commit message: holds a secret")
    elif args.pre_push:
        starts, haves, new_ref = [], [], False
        for line in sys.stdin.read().splitlines():  # "<local ref> <local sha> <remote ref> <remote sha>"
            if not line.strip():
                continue
            parts = line.rsplit(" ", 3)
            if len(parts) != 4 or not all(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", p) for p in (parts[1], parts[3])):
                problems.append(f"push: a ref line that cannot be read: {shown(line, secrets)}")
                continue
            local_ref, local_sha, remote_ref, remote_sha = parts
            if local_sha.strip("0"):  # all zeros deletes the remote ref, which also takes its name away
                problems += [f"ref name {shown(r, secrets)}" for r in (local_ref, remote_ref) if in_name(r, secrets)]
                starts.append(local_sha)
            if remote_sha.strip("0"):
                haves += [remote_sha] if has_object(root, remote_sha) else []
            else:
                new_ref = True
        if starts and new_ref:  # a new branch or tag: ask the remote what it has, or the whole history counts
            for line in git(root, "ls-remote", args.pre_push, check=False).decode(errors="replace").splitlines():
                sha = line.split("\t", 1)[0]
                haves += [sha] if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha) and has_object(root, sha) else []
        if starts:  # only what the remote does not have yet, by its own refs, not by remote-tracking branches
            found, commits = scan_objects(root, [*starts, "--not", *haves], secrets)
            problems += found
    else:
        problems, staged = scan_staged(root, secrets)
        people = [git(root, "var", v, check=False).decode(errors="replace") for v in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT")]
        if in_name("\n".join(people), secrets):
            problems.append("the next commit's author or committer holds a secret "
                            "(fix git config user.name and user.email; when amending, add --reset-author)")
        if not args.staged:
            head = ["HEAD"] if git(root, "rev-parse", "--verify", "-q", "HEAD", check=False) else []
            rev_args = (["--exclude=refs/stash", "--all"] if args.all_history
                        else ["--branches", "--tags", *head, "--not", "--remotes"])
            found, commits = scan_objects(root, rev_args, secrets)
            refs = git(root, "for-each-ref", "--format=%(refname)", "refs/heads", "refs/tags",
                       *(["refs/remotes"] if args.all_history else [])).decode(errors="surrogateescape").splitlines()
            problems += found + [f"ref name {shown(r, secrets)}" for r in refs if in_name(r, secrets)]

    report = mask("\n".join(sorted(set(problems))), secrets)  # names were masked; this catches anything else
    report = report.encode("utf-8", "surrogateescape").decode("utf-8", "replace")  # printable non-UTF-8 names
    scope = ("the commit message" if args.message else f"{commits} commit(s) to push" if args.pre_push
             else f"{staged} staged file(s)" + ("" if args.staged else f" and {commits} commit(s)"))
    print(report or f"clean: {len(secrets)} secret(s) checked in {scope}")
    if problems and by_hook:
        print("scan_private: " + ("nothing was pushed; fix the commits listed above (出事時 in "
                                  ".agents/skills/privacy-safe-commits/SKILL.md) and push again" if args.pre_push
                                  else "the commit was not made; fix the message and commit again" if args.message
                                  else "the commit was not made; take files out with git restore --staged PATH, "
                                  "or fix what is listed, and commit again"), file=sys.stderr)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
