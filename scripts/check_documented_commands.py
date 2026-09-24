#!/usr/bin/env python3
"""Check that commands quoted in the paper and README work as written.

The coverage census reports entry-point scripts as unvouched: nothing imports them, so a
`python3 scripts/foo.py --bar` in the prose is verified by nobody. A reviewer's first
contact with this artifact is copying one of those lines, and a flag that does not exist
makes the whole reproduction claim look unchecked.

Two checks:
  compile -- every .py under scripts/ and chia_loop/ byte-compiles;
  flags    -- every --option quoted after a documented python3 invocation is actually
             accepted by that script's own --help output.
"""
from __future__ import annotations

import argparse
import py_compile
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CMD = re.compile(r"python3?\s+((?:scripts|chia_loop)/[A-Za-z0-9_./\-]+\.py)([^&|\n]*)")


def prose() -> str:
    """Return the prose with quoted command spans collapsed onto one line.

    A documented command is usually wrapped mid-flags by the LaTeX or Markdown source,
    so matching line by line silently checks only the first line of each command.
    """
    out = []
    for rel in ("README.md", "paper/paper.tex", "ROADMAP.md", "COMPUTE_WINDOW.md",
                "docs/handoff-2026-09-24.md", "decision_chain/README.md", "PRECOMPUTE.md",
                "KAGGLE_VALIDATION.md", "chia_loop/README.md"):
        p = REPO / rel
        if not p.exists():
            continue
        text = re.sub(r"\\_", "_", p.read_text(encoding="utf-8", errors="ignore"))
        spans = [m.group(1) for m in re.finditer(r"\\texttt\{([^{}]*)\}", text)]
        spans += [m.group(1) for m in re.finditer(r"`([^`\n]{8,})`", text)]
        # A fenced block is a sequence of shell lines, not one command: only a trailing
        # backslash continues it. Gluing the block together lets a `#` comment on the
        # next line donate --flags to the command above it.
        for block in re.findall(r"```[\w]*\n(.*?)```", text, re.S):
            kept, buf = [], ""
            for raw in block.splitlines():
                line = re.sub(r"(?<!\S)#.*$", "", raw).strip()
                if not line and not buf:
                    continue
                buf = f"{buf} {line}".strip() if buf or raw.rstrip().endswith("\\") else line
                if raw.rstrip().endswith("\\"):
                    buf = buf.rstrip("\\").rstrip()
                    continue
                kept.append(buf)
                buf = ""
            if buf:
                kept.append(buf)
            spans += kept
        text = "\n".join([text] + [re.sub(r"\s+", " ", s) for s in spans])
        out.append(text)
    return "\n".join(out)


def help_options(script: str) -> set[str] | None:
    """Every option string the script itself advertises, or None if it will not run."""
    try:
        r = subprocess.run([sys.executable, script, "--help"], cwd=REPO,
                           capture_output=True, text=True, timeout=120,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 and not (r.stdout or r.stderr):
        return None
    return set(re.findall(r"(?<![\w-])(--[A-Za-z][\w-]*)", r.stdout + r.stderr))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()

    bad_compile = []
    for py in sorted(list((REPO / "scripts").glob("*.py"))
                     + list((REPO / "chia_loop").rglob("*.py"))):
        try:
            py_compile.compile(str(py), doraise=True, cfile=Path(py.with_suffix(".pyc.tmp")))
        except py_compile.PyCompileError as exc:
            bad_compile.append(f"{py.relative_to(REPO)}: {exc.msg.splitlines()[0][:90]}")
        finally:
            Path(py.with_suffix(".pyc.tmp")).unlink(missing_ok=True)

    missing: dict[str, list[str]] = {}
    checked = set()
    body = prose()
    for script, tail in CMD.findall(body):
        script = script.rstrip(".,;)")
        if not (REPO / script).exists():
            missing.setdefault(script, ["<file missing>"])
            continue
        flags = {f for f in re.findall(r"(?<![\w-])(--[A-Za-z][\w-]*)", tail)}
        if not flags:
            continue
        opts = help_options(script)
        checked.add(script)
        if opts is None:
            missing.setdefault(script, ["--help did not run"])
            continue
        for f in sorted(flags - opts):
            missing.setdefault(script, []).append(f)

    print(f"byte-compiled: {len(list((REPO / 'scripts').glob('*.py'))) + len(list((REPO / 'chia_loop').rglob('*.py')))} files")
    print(f"scripts whose advertised options were compared: {len(checked)}")
    for script, why in sorted(missing.items()):
        print(f"  MISSING in {script}: {', '.join(sorted(set(why)))}")
    for b in bad_compile:
        print(f"  COMPILE FAIL {b}")
    return 1 if (missing or bad_compile) else 0


if __name__ == "__main__":
    raise SystemExit(main())
