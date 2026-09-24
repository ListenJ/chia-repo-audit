#!/usr/bin/env python3
"""Per-file inventory: what mechanically vouches for each tracked file.

"没有错漏" is only defensible if you can say which files some check actually reads.
This script does not claim a file is correct; it reports which of five independent
vouches currently cover it, and names the files with none.

Vouches, from strongest to weakest, deliberately kept separate:
  claimed   a scripts/verify_paper_claims.py check re-derives a number from this file
  tested    a unit test module imports or reads it
  cited     paper/paper.tex names it
  logged    docs/operations-log.md names it
  indexed   CANDIDATES.md or a README/ROADMAP/COMPUTE_WINDOW doc points at it

`claimed` and `tested` are machine vouches. `cited`/`logged`/`indexed` only prove the
file is talked about, which is not the same as being checked -- so a file whose only
vouch is prose is reported as `prose-only`, not as covered.
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
import tokenize
from collections import Counter
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parent.parent


def strip_py_comments(text: str) -> str:
    """Drop `#` comments from Python source, leaving string literals alone.

    `claimed` means a check re-derives a number from the file. A comment that happens
    to name the file proves no such thing, yet substring matching over raw source counts
    it -- measured: writing the filename of a `.tmp/` note inside a comment in
    verify_paper_claims.py moved that file from code-unreferenced to machine-vouched and
    turned five published numbers stale while every gate stayed green. That also falsified
    this report's own sentence "writing about a file cannot change this table".
    tokenize is used rather than a regex so a `#` inside a path string survives.
    """
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return text
    return tokenize.untokenize(
        t for t in toks if t.type != tokenize.COMMENT)

GENERATED_MARKERS = (
    "results/", "paper/fig_", "CANDIDATES.md", "paper/paper.aux", "paper/paper.log",
    "paper/paper.out", "paper/paper.pdf",
)

# Directory names too generic to establish that code reads this file's set.
GENERIC_DIRS = {".tmp", "results", "scripts", "docs", "chia_loop", "paper", "."}


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True,
                         text=True, encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise SystemExit(f"git ls-files failed: {out.stderr.strip()}")
    return [line.replace("\\", "/") for line in out.stdout.splitlines() if line.strip()]


def read(rel: str) -> str:
    path = REPO / rel
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true",
                    help="print the census as JSON instead of a summary")
    ap.add_argument("--markdown", metavar="PATH",
                    help="write the census to PATH as a markdown report")
    # The caller passes sys.argv[1:] already, so slice once here.
    opts = ap.parse_args(argv)
    verifier = strip_py_comments(read("scripts/verify_paper_claims.py"))
    paper = read("paper/paper.tex").replace("\\_", "_")
    opslog = read("docs/operations-log.md")
    tests = {p: strip_py_comments(read(str(p.relative_to(REPO))))
             for p in (REPO / "chia_loop/tests").glob("*.py")}
    index = "".join(read(rel) for rel in
                    ("CANDIDATES.md", "README.md", "ROADMAP.md", "COMPUTE_WINDOW.md",
                     "PRECOMPUTE.md", "KAGGLE_VALIDATION.md", "chia_loop/README.md",
                     "decision_chain/README.md"))
    everything = [Path(f) for f in tracked_files()]
    # This script's own source names the directories it inspects, so counting it as a
    # consumer would make everything reachable by self-reference.
    here = str(Path(__file__).resolve().relative_to(REPO)).replace("\\", "/")
    sources = {str(p.relative_to(REPO)).replace("\\", "/"):
               strip_py_comments(read(str(p.relative_to(REPO))))
               for p in REPO.rglob("*.py")
               if ".git" not in p.parts and "__pycache__" not in p.parts
               and str(p.relative_to(REPO)).replace("\\", "/") != here}

    rows = []
    for path in everything:
        rel = str(path).replace("\\", "/")
        name = Path(rel).name
        stem = Path(rel).stem
        # Artifacts are usually referred to by stem: a candidate .json is named in
        # CANDIDATES.md by its module name, a log by its run name. Matching only the
        # filename invents "unvouched" rows.
        tokens = {t for t in (name, stem) if len(t) > 3}

        def mentioned(corpus: str) -> bool:
            return any(t in corpus for t in tokens)

        vouches = []
        if any(t in verifier for t in tokens):
            vouches.append("claimed")
        if any(stem and stem in body for body in tests.values()) or rel.startswith("chia_loop/tests/"):
            vouches.append("tested")
        if mentioned(paper):
            vouches.append("cited")
        if mentioned(opslog):
            vouches.append("logged")
        if mentioned(index):
            vouches.append("indexed")
        # A case file inside a set that some script reads wholesale is never named in
        # prose, so name-mention would call it unwatched. Record the weaker, honest
        # fact instead: the directory it lives in is referenced by executable code.
        # Generic names do not qualify -- one mention of ".tmp" would otherwise mark
        # every file under it reachable.
        parent = PurePosixPath(rel).parent
        qualified: set[str] = set()
        if parent.name not in GENERIC_DIRS:
            qualified |= {str(parent), parent.name}
        elif len(parent.parts) > 1:
            qualified.add(str(parent))
        reachable_by = sorted({str(src) for src, body in sources.items()
                              if any(q and q in body for q in qualified)})
        if reachable_by and not rel.endswith(".py"):
            vouches.append(f"reachable")
        machine = [v for v in vouches if v in ("claimed", "tested")]
        # Tiers come from code-side evidence only. Prose mentions are still recorded,
        # but they may not classify: reporting on a file would vouch for it, so writing
        # this census would change it and the published rate could never settle.
        rows.append({
            "file": rel,
            "bytes": (REPO / rel).stat().st_size if (REPO / rel).exists() else -1,
            "kind": ("generated" if any(m in rel for m in GENERATED_MARKERS)
                     else "test" if rel.startswith("chia_loop/tests/")
                     else "source" if rel.endswith(".py")
                     else "doc" if rel.endswith(".md")
                     else "other"),
            "vouches": vouches,
            "named_in_prose": bool({"cited", "logged", "indexed"} & set(vouches)),
            "reachable_by": reachable_by[:4],
            "tier": ("machine" if machine else
                     "reachable" if "reachable" in vouches else "code-unreferenced"),
        })

    counts = Counter(r["tier"] for r in rows)
    total = len(rows)
    by_kind = {k: Counter(r["tier"] for r in rows if r["kind"] == k) for k in
               sorted({r["kind"] for r in rows})}
    unref = [r for r in rows if r["tier"] == "code-unreferenced"]
    report = {
        "files_tracked": total,
        "tiers": dict(counts),
        "machine_vouched_rate": round(counts["machine"] / total, 4) if total else 0.0,
        "unvouched_rate": round(len(unref) / total, 4) if total else 0.0,
        "by_kind": {k: dict(v) for k, v in by_kind.items()},
        "unvouched": [r["file"] for r in unref],
        "unvouched_named_in_prose": [r["file"] for r in unref if r["named_in_prose"]],
        "prose_only": [r["file"] for r in rows
                       if r["tier"] != "machine" and r["named_in_prose"]],
        "generated_files": [r["file"] for r in rows if r["kind"] == "generated"],
    }
    if opts.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if opts.markdown:
        out = Path(opts.markdown)
        lines = [
            "# Review coverage",
            "",
            "Generated by `scripts/inventory_vouches.py`; re-run instead of editing.",
            f"Every tracked file ({total}) is classified by what currently vouches for it.",
            "",
            "| tier | files | share | what it means |",
            "| --- | --- | --- | --- |",
            f"| machine-vouched | {counts['machine']} | {counts['machine'] / total:.1%} "
            "| a `verify_paper_claims.py` check re-derives from it, or a unit test loads it |",
            f"| reachable-only | {counts['reachable']} | {counts['reachable'] / total:.1%} "
            "| executable code references the set it belongs to, but nothing checks this file |",
            f"| code-unreferenced | {counts['code-unreferenced']} | "
            f"{counts['code-unreferenced'] / total:.1%} "
            "| nothing executable reads or names it |",
            "",
            "Tiers are computed from code-side evidence only, and `#` comments are "
            "stripped before matching, so *writing about* a file cannot change this "
            "table -- naming it in the paper, the ops log or an index, or in a comment "
            "inside the verifier, all leave the tiers alone. What does change them is "
            "real code: a check that starts reading the file, or a test that loads it. "
            "Prose mentions are still recorded: "
            f"{len(report['unvouched_named_in_prose'])} of the code-unreferenced files "
            "are at least named somewhere in the paper, ops log or an index.",
            "",
            "**What this does not claim.** A machine vouch means a check reads the file, "
            "not that a human read it; `reachable-only` means some script globs its "
            "directory, which is weaker still. Nothing here is a correctness statement.",
            "",
            "## Files with no vouch at all",
            "",
        ] + [f"- `{f}`" for f in report["unvouched"]] + [
            "",
            "## Known limits of this census",
            "",
            "- **A script invoked as a command counts as unreferenced.** Nothing imports",
            "  `scripts/verify_paper_claims.py`, `rescore_grid.py`, `local_gate.py` or the",
            "  other entry points; they are run, not read. Reachability deliberately skips",
            "  `.py`/`.sh` for that reason, so every one of them has to be judged by hand.",
            "  That is why the list is published per file and the percentage is not the",
            "  headline.",
            "- `reachable-only` is weak: it says a script globs the directory this file",
            "  sits in, which would also be true of a file that script then ignores.",
            "- Nothing here is a correctness claim. A machine vouch means a check reads the",
            "  file, not that anyone reviewed what it says.",
        ]
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {out} ({len(lines)} lines)")
        return 0
    print(f"tracked files:        {total}")
    for tier, label in (("machine", "machine-vouched     "),
                        ("reachable", "reachable-only      "),
                        ("code-unreferenced", "no code reference   ")):
        n = counts[tier]
        print(f"{label} {n:>4}  ({n / total:.1%})" if total else f"{label} 0")
    print(f"                     of the unreferenced, {len(report['unvouched_named_in_prose'])} "
          "are named in prose")
    for kind, tiers in by_kind.items():
        print(f"  {kind:<9} {dict(tiers)}")
    print("\nfiles with no vouch at all:")
    for f in report["unvouched"]:
        print(f"  - {f}")
    print(f"\ngenerated artifacts (must be reproducible, not reviewed): "
          f"{len(report['generated_files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
