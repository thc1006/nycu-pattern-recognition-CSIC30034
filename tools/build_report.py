"""Fill a homework report with its numbers, typeset it, and write the e3 copy and the public copy.

Run from the repository root after the experiments:  uv run tools/build_report.py N

Reads, under homeworkN/: PR_HWN/report_numbers.py (a dict v of text, one entry per <<key>> in the template),
PR_HWN/report/template.tex (written with common/prhw.cls) and PR_HWN_full_transcription.md (for the page limit).
Name and e-mail come from student.json, the student ID from student.local.json; without the ID only the public copy
is written. Writes homeworkN/submission/PR_HWN_<name>_<ID>.pdf (kept local) and homeworkN/public/PR_HWN_<name>.pdf,
both or neither. It stops on a LaTeX warning, an overfull or underfull box, a failed PDF check, or any value from a
*.local.json file in the public copy, its build files, or a file under homeworkN/ that git would push.
The ID is never printed; output shows <ID> instead.
"""
import argparse
import contextlib
import io
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

import check_pdf
import scan_private

ROOT = Path(__file__).resolve().parents[1]
KEY = re.compile(r"<<(\w+)>>")
COMMENT = re.compile(r"(?<!\\)((?:\\\\)*)%.*")
FILLED_HERE = {"name", "email", "sid", "code"}
LOG_PROBLEM = re.compile(r"Warning|Overfull|Underfull|Missing character")
MAX_RUNS = 4
HIDE = set()  # values from *.local.json, masked in everything this script prints


def say(message):
    """message with every *.local.json value masked, and any run of 4+ letters or digits that is part of one
    (a check's context window can cut the ID in half)."""
    message = scan_private.mask(message, HIDE, "<ID>")
    parts = [scan_private.folded(s) for s in HIDE]
    return re.sub(r"[0-9A-Za-z]{4,}", lambda m: "<ID>" if any(m.group().casefold() in p for p in parts) else m.group(),
                  message)


def code_and_comment(line):
    m = COMMENT.search(line)
    return (line, "") if not m else (line[:m.start()] + m.group(1), line[m.start() + len(m.group(1)):])


def fill(template, values):
    """Fill <<key>> outside comments; comments (and the rest of a verbatim line after %) are kept as written."""
    out = []
    for line in template.split("\n"):
        code, comment = code_and_comment(line)
        out.append(KEY.sub(lambda m: values[m.group(1)], code) + comment)
    return "\n".join(out)


def keys_outside_comments(text):
    return [k for line in text.split("\n") for k in KEY.findall(code_and_comment(line)[0])]


def fail(message):
    sys.exit(say(f"build_report: {message}"))


def git(*args):
    """Output of a git command run at the repository root, or None if it fails (e.g. outside a work tree)."""
    p = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, errors="surrogateescape")
    return p.stdout if p.returncode == 0 else None


def student():
    """Name, e-mail and student ID ("" without student.local.json)."""
    try:
        info = json.loads((ROOT / "student.json").read_text())
        name, email = info["name"].strip(), info["email"].strip()
    except (OSError, ValueError, KeyError, AttributeError) as err:
        fail(f"student.json needs text fields name and email ({err!r})")
    if not name or re.search(r"[\\{}$&#^%~_/]", name) or re.search(r"[\\{}$&#^%~]", email):
        fail("the name in student.json is empty or uses one of \\ { } $ & # ^ % ~ _ /, or the e-mail uses one of them")
    private = ROOT / "student.local.json"
    try:
        local = json.loads(private.read_text()) if private.exists() else {}
    except ValueError as err:
        fail(f"student.local.json is not valid JSON ({err})")
    if not isinstance(local, dict):
        fail('student.local.json must be an object such as {"student_id": "..."}')
    sid = local.get("student_id", "")
    if isinstance(sid, bool) or not isinstance(sid, (str, int)):
        fail("student_id in student.local.json must be text or a number")
    sid = str(sid).strip()
    if not re.fullmatch(r"[0-9A-Za-z]*", sid):
        fail("student_id in student.local.json must be letters and digits only")
    return name, email, sid


def numbers(hw):
    """The dict v from report_numbers.py, run with the homework folder on sys.path so it can import pr_hwN."""
    path = hw / "report_numbers.py"
    if not path.exists():
        return {}
    sys.path.insert(0, str(hw))
    spec = importlib.util.spec_from_file_location("report_numbers", path)
    module = importlib.util.module_from_spec(spec)
    buf = io.StringIO()
    with tempfile.TemporaryFile() as cap:  # file descriptors 1 and 2 too, for subprocesses and C extensions
        sys.stdout.flush(), sys.stderr.flush()
        saved = os.dup(1), os.dup(2)
        os.dup2(cap.fileno(), 1), os.dup2(cap.fileno(), 2)
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                spec.loader.exec_module(module)
        finally:
            os.dup2(saved[0], 1), os.dup2(saved[1], 2)
            os.close(saved[0]), os.close(saved[1])
            cap.seek(0)
            sys.stdout.write(say(cap.read().decode(errors="replace") + buf.getvalue()))
    v = getattr(module, "v", None)
    if not isinstance(v, dict):
        fail("report_numbers.py must define a dict v")
    if bad := sorted(k for k, x in v.items() if not isinstance(x, str)):
        fail(f"values in report_numbers.v must be text: {bad}")
    if bad := sorted(k for k, x in v.items() if COMMENT.search(x)):
        fail(f"values with an unescaped % would hide the rest of the line (write \\%): {bad}")
    return v


def code_files(hw, n, published):
    """Every .py under the homework folder outside results/, report/ and hidden folders; experiment first.
    When the public copy will be pushed, a .py that git ignores (kept local) is left out of both copies."""
    names = sorted(str(p.relative_to(hw)) for p in hw.rglob("*.py")
                   if not any(d in ("__pycache__", "results", "report") or d.startswith(".")
                              for d in p.relative_to(hw).parts[:-1]))
    if published:
        listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", str(hw)) or ""
        pushed = {str((ROOT / f).relative_to(hw)) for f in listed.split("\0") if f.endswith(".py")}
        if ignored := [f for f in names if f not in pushed]:
            print(say(f"note: git ignores these, so the appendix leaves them out: {ignored}"))
        names = [f for f in names if f in pushed]
    # characters TeX reads as commands, and bytes that are not UTF-8 (report.tex cannot spell such a name)
    if odd := [f for f in names if re.search(r'[%#{}\\~$&^\n"\t\udc80-\udcff]| {2}', f)]:
        fail(f"rename these files, \\codefile cannot list them: {odd}")
    if clash := [f for f in names if f in ("build_report.py", "check_pdf.py", "scan_private.py")]:
        fail(f"rename these files, they shadow the tools in tools/: {clash}")
    first = [f for f in (f"pr_hw{n}.py", f"check_hw{n}.py", "report_numbers.py") if f in names]
    return first + [f for f in names if f not in first]


def stated_limit(transcription):
    """The page limit in the assignment text ("limited to N pages"), or None."""
    if transcription.exists():
        m = re.search(r"limited\s+to\s+(\d+)\s+pages?\b", transcription.read_text(), re.I)
        return int(m.group(1)) if m else None
    return None


def typeset(report):
    """Run xelatex until it stops asking for a rerun; return the final log."""
    # report/ first and common/ only for prhw.cls; long log lines so paths and warnings are not wrapped
    env = {**os.environ, "TEXINPUTS": f".:{ROOT / 'common'}:", "max_print_line": "10000"}
    for _ in range(MAX_RUNS):
        try:
            run = subprocess.run(["xelatex", "-interaction=nonstopmode", "-halt-on-error", "report.tex"],
                                 cwd=report, env=env, capture_output=True, text=True, errors="replace")
        except FileNotFoundError:
            fail("xelatex not found")
        log_file = report / "report.log"
        log = log_file.read_text(errors="replace") if log_file.exists() else ""
        if run.returncode:
            errors = [line for line in log.splitlines() if line.startswith("!")] or run.stdout.splitlines()[-10:]
            fail(f"xelatex stopped, see {log_file}:\n  " + "\n  ".join(errors[:5]))
        if not re.search(r"Rerun to get|Label\(s\) may have changed", log):
            return log
    fail(f"cross-references still changing after {MAX_RUNS} xelatex runs")


def build(report, tex, require, stated, label):
    """Typeset tex in report/ and check the result; return (pages, last body page, page limit)."""
    (report / "report.pdf").unlink(missing_ok=True)  # a run that writes no PDF must not leave the last one behind
    (report / "report.tex").write_text(tex)
    log = typeset(report)
    if not (report / "report.pdf").exists():
        fail(f"{label}: xelatex wrote no PDF")
    problems = [f"log: {line.strip()}" for line in log.splitlines() if LOG_PROBLEM.search(line)]
    if f"({ROOT / 'common' / 'prhw.cls'}" not in log:
        problems.append("the report did not load common/prhw.cls; a prhw.cls next to report.tex shadows it")
    aux = (report / "report.aux").read_text(errors="replace")
    found = re.findall(r"\\newlabel\{prhw@body-end\}\{\{(\d+)\}\{(\d+)\}", aux)
    if len(found) != 1:
        fail(f"{label}: label prhw@body-end appears {len(found)} times in report.aux, expected once")
    limit, body = map(int, found[0])
    if stated is not None and limit != stated:
        problems.append(f"\\pagelimit{{{limit}}} in the template, but the assignment allows {stated} pages")
    pages, _, more = check_pdf.check(report / "report.pdf", report / "report.aux", "prhw@body-end", limit, require)
    if problems + more:
        fail(f"{label}:\n  " + "\n  ".join(problems + more))
    return pages, body, limit


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("n", type=int, help="homework number")
    n = ap.parse_args().n
    hw = ROOT / f"homework{n}" / f"PR_HW{n}"
    report = hw / "report"
    if not (report / "template.tex").exists():
        fail(f"homework{n}/PR_HW{n}/report/template.tex not found; start with uv run tools/new_homework.py {n}")
    template = (report / "template.tex").read_text()
    assigned = re.findall(r"\\assignment\s*\{\s*(\d+)\s*\}", "\n".join(code_and_comment(l)[0] for l in template.split("\n")))
    if [int(a) for a in assigned] != [n]:
        fail(f"template.tex sets \\assignment to {assigned or 'nothing'}, but this is homework {n}")
    name, email, sid = student()
    secrets = scan_private.local_secrets(ROOT) | ({sid} if sid else set())
    HIDE.update(secrets)
    if any(scan_private.folded(s) in scan_private.folded(text) for s in secrets for text in (name, email)):
        fail("a value from *.local.json is part of the name or e-mail, so the public copy cannot leave it out")

    in_git = git("rev-parse", "--is-inside-work-tree") is not None
    public = hw.parent / "public" / f"PR_HW{n}_{name}.pdf"
    published = in_git and git("check-ignore", "-q", str(public)) is None
    code = code_files(hw, n, published)  # before report_numbers.py runs, so a homework file named like a tool is caught first
    v = numbers(hw)
    keys = set(keys_outside_comments(template))
    for what, items in (("filled by this tool", v.keys() & FILLED_HERE), ("computed but never quoted", v.keys() - keys),
                        ("quoted but never computed", keys - v.keys() - FILLED_HERE)):
        if items:
            fail(f"report keys {what}: {sorted(items)}")
    if "code" not in keys:
        fail("the template must end with <<code>> after \\codeappendix")
    values = {**v, "name": name, "email": email, "code": "\n".join(rf"\codefile{{{f}}}" for f in code)}
    transcription = hw.parent / f"PR_HW{n}_full_transcription.md"
    stated = stated_limit(transcription)
    if stated is None:
        why = "has no \"limited to N pages\"" if transcription.exists() else "not found"
        print(f"note: homework{n}/PR_HW{n}_full_transcription.md {why}; using \\pagelimit")

    e3 = hw.parent / "submission" / f"PR_HW{n}_{name}_{sid}.pdf"
    if sid and in_git and git("check-ignore", "-q", str(e3)) is None:
        fail(f"git would not ignore {e3.relative_to(ROOT)}; keep homework*/submission/ in .gitignore")

    copies = ([(sid, e3)] if sid else []) + [("", public)]  # the e3 copy first, so report/ ends with the public build
    with tempfile.TemporaryDirectory() as tmp:
        built = []
        for this_sid, dest in copies:
            tex = fill(template, {**values, "sid": this_sid})
            if left := sorted({k for line in tex.split("\n") for k in re.findall(r"<<[^<>\n]*>>", code_and_comment(line)[0])}):
                fail(f"placeholders left after filling: {left}")
            pages, body, limit = build(report, tex, [name, this_sid] if this_sid else [name], stated, dest.name)
            kept = Path(tmp) / dest.name
            shutil.copyfile(report / "report.pdf", kept)
            built.append((kept, dest, f"{pages} pages, body ends on page {body} (limit {limit})"))
        if secrets:  # nothing is written until the public copy and everything git would push are clean
            files = [built[-1][0]] + [f for f in report.iterdir() if f.is_file() and f.suffix != ".log"]
            listed = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", str(hw.parent))
            paths = [ROOT / f for f in (listed or "").split("\0") if f]
            files += [f for f in paths if f.is_file() and not f.is_symlink() and f != public]
            hits = sorted({f"{f.name} ({where})" for f in files for s in secrets for where in scan_private.leaks(f, s)})
            hits += [f"{f.relative_to(ROOT)} (file name or link target)" for f in paths
                     if scan_private.in_name(f"{f.relative_to(ROOT)}\n{os.readlink(f) if f.is_symlink() else ''}", secrets)]
            if hits:
                fail("a value from *.local.json shows up in: " + ", ".join(hits))
        parts = []
        try:
            for kept, dest, summary in built:
                dest.parent.mkdir(exist_ok=True)
                parts.append(dest.with_name(dest.name + ".part"))
                shutil.copyfile(kept, parts[-1])
        except OSError as err:
            for part in parts:
                part.unlink(missing_ok=True)
            fail(f"nothing written: {err}")
        for part, (kept, dest, summary) in zip(parts, built):
            os.replace(part, dest)
            print(say(f"{dest.relative_to(ROOT)}: {summary}"))
    if not sid:
        print("note: no student_id in student.local.json at the repository root, so no e3 copy was written")
    if not secrets:
        print("note: no *.local.json values found, so nothing was checked for the student ID")
    elif in_git:
        print(f"public copy and the work-tree files under homework{n}/ that git would add: no value from *.local.json "
              "(staged and committed versions: run tools/scan_private.py)")
    else:
        print("public copy and its build files: no value from *.local.json (not a git work tree, pushable files unchecked)")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as err:  # fail() is already masked; a sys.exit("...") from report_numbers.py is not
        sys.exit(say(err.code) if isinstance(err.code, str) else err.code)
    except BaseException:  # report_numbers.py runs arbitrary code; Ctrl-C included
        sys.exit(say(traceback.format_exc()))
