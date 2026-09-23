#!/usr/bin/env python3
"""Build audit cases from real generated candidates, not from hand-written dicts.

The checked-in gold/adversarial sets differ only in dictionary keys, which makes the
classifier's job tautological. Here the visible payload is real C++ prefetcher source
and the expected label is grounded in two independent signals: what the official
simulator measured, and what changed structurally in the source. A pair whose class
cannot be derived from those signals is emitted as unclassifiable rather than given a
label we cannot defend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

MEMBER_DECL = re.compile(
    r"^\s{2,}(?:const\s+|static\s+|unsigned\s+|signed\s+)*"
    r"[A-Za-z_][\w:]*(?:<[^;{}]*>)?\s+[*&]?\s*([A-Za-z_]\w*)\s*(?:\(|=|;)",
    re.M)
NOT_A_MEMBER = {"struct", "return", "if", "for", "while", "using", "void", "break", "continue"}
NUM_LITERAL = re.compile(r"(?<![\w.])\d+(?![\w.])")
COMPARATORS = re.compile(r"(<=|>=|<|>)")
PREPROC = re.compile(r"^[ \t]*#.*$", re.M)
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"//[^\n]*")


def code_only(source: str) -> str:
    """Keep only what the compiler treats as design.

    ``#include <vector>`` carries two angle brackets, and the comparator extractor
    read them as comparison operators: three design pairs were labelled E2 "direction
    error" purely because one candidate included more headers than the other.
    Preprocessor lines, comments and implicit-object qualifiers are not design.
    """
    text = PREPROC.sub("", source)
    text = BLOCK_COMMENT.sub(" ", text)
    text = LINE_COMMENT.sub("", text)
    return text.replace("this->", "")


def normalize(source: str, module_name: str) -> str:
    """Strip the identity of the module so a rename cannot masquerade as a design change."""
    text = re.sub(rf"\b{re.escape(module_name)}\b", "MODULE", code_only(source))
    return re.sub(r"\s+", " ", text).strip()


CLASS_MEMBER_DECL = re.compile(
    r"^(?:const\s+|static\s+|unsigned\s+|signed\s+)*"
    r"[A-Za-z_][\w:]*(?:<[^<>]*(?:<[^<>]*>)?[^<>]*>)?\s+[*&]?\s*([A-Za-z_]\w*)\s*(?:\(|=|;)",
    re.M)
NOT_A_MEMBER = {"struct", "return", "if", "for", "while", "using", "void", "break", "continue"}


def class_members(source: str) -> set[str]:
    """Declarations at class scope only.

    Depth matters: a local variable inside a method body is not a component of the
    design, and comparing locals across two implementations labels almost every pair
    as both adding and dropping state, which carries no signal.
    """
    out: set[str] = set()
    depth = 0
    for line in source.splitlines():
        stripped = line.strip()
        if depth == 1 and stripped and not stripped.startswith(("//", "/*", "*")):
            match = CLASS_MEMBER_DECL.match(stripped)
            if match and match.group(1) not in NOT_A_MEMBER:
                out.add(match.group(1))
        depth += line.count("{") - line.count("}")
    return out


def members(source: str) -> set[str]:
    return class_members(code_only(source))


def comparators(source: str) -> list[str]:
    return COMPARATORS.findall(code_only(source))


def literals(source: str) -> list[str]:
    return NUM_LITERAL.findall(code_only(source))


def measured_cycles(raw: dict | None, candidate_id: str) -> dict:
    if not raw:
        return {}
    out = {}
    for key, cell in raw.items():
        if cell.get("candidate_id") != candidate_id:
            continue
        cycles = [t.get("cycles") for t in cell.get("trials", []) if t.get("cycles") is not None]
        if cycles:
            out[cell["trace"]] = min(cycles) if len(set(cycles)) == 1 else sorted(cycles)[len(cycles) // 2]
    return out


def classify(design_src: str, ref_src: str, design_name: str, ref_name: str,
             d_cyc: dict, r_cyc: dict) -> tuple[str, list[str], str]:
    """Return (verdict, error classes, evidence note). Unclassifiable keeps verdict but no class."""
    same_source = normalize(design_src, design_name) == normalize(ref_src, ref_name)
    shared = sorted(set(d_cyc) & set(r_cyc))
    if shared:
        same_measured = all(d_cyc[t] == r_cyc[t] for t in shared)
    else:
        same_measured = same_source

    if same_source and same_measured:
        return "equivalent", [], f"source equal after rename+whitespace; cycles equal on {len(shared)} trace(s)"
    if shared and same_measured:
        # Measurement outranks text: two sources that differ in every cosmetic way and
        # take the same number of cycles on every shared trace are equivalent designs.
        # This is the nullity escape, and the old code fell through and called it not_equivalent.
        return ("equivalent", [],
                f"cycles equal on all {len(shared)} shared trace(s) despite textual difference")

    added = members(design_src) - members(ref_src)
    removed = members(ref_src) - members(design_src)
    errors: list[str] = []
    note = []
    if added:
        errors.append("E4")
        note.append(f"design adds state {sorted(added)}")
    if removed:
        errors.append("E3")
        note.append(f"design drops state {sorted(removed)}")
    if not added and not removed:
        d_lit, r_lit = literals(design_src), literals(ref_src)
        if sorted(d_lit) != sorted(r_lit):
            errors.append("E1")
            note.append("numeric literals differ")
        if (not errors and comparators(design_src) != comparators(ref_src)):
            errors.append("E2")
            note.append("comparison polarity differs")
    if not errors:
        if not shared:
            # No measurement on either side and nothing structural to point at: the two
            # sources differ, but not in a property any rule can call a design change.
            # Guessing "not_equivalent" here asserted a behavioral difference from text.
            return ("unlabellable", [], "no shared trace measurement; sources differ only in "
                    "names or formatting, so no verdict is derivable")
        note.append("class not derivable from member/literal/operator diff")
    measured = ("cycles differ" if shared and not same_measured
                else "cycles equal" if shared else "no shared trace measurement")
    return "not_equivalent", sorted(set(errors)), f"{measured}; " + "; ".join(note)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-dirs", nargs="+", required=True)
    parser.add_argument("--grid-raw", type=Path,
                        help="raw.json from a completed grid, used to ground the label in measurement")
    parser.add_argument("--out-dir", type=Path, default=REPO / "chia_loop/semantic")
    args = parser.parse_args()

    raw = None
    if args.grid_raw and args.grid_raw.is_file():
        raw = json.loads(args.grid_raw.read_text(encoding="utf-8")).get("cells")

    candidates = {}
    for directory in args.candidate_dirs:
        for path in sorted(Path(directory).glob("gen_*.json")):
            record = json.loads(path.read_text(encoding="utf-8"))
            module = record["design"]["module_name"]
            candidates[module] = {
                "source": record["design"]["prefetcher_source"],
                "cycles": measured_cycles(raw, module),
                "prompt": record.get("prompt"),
                "seed": record.get("generator_seed"),
            }
    if len(candidates) < 2:
        print(f"need at least two candidates, found {len(candidates)}", file=sys.stderr)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    names = sorted(candidates)
    written = 0
    for i, design in enumerate(names):
        for reference in names[i + 1:]:
            d, r = candidates[design], candidates[reference]
            verdict, errors, note = classify(d["source"], r["source"], design, reference,
                                             d["cycles"], r["cycles"])
            case = {
                "id": f"sem-{written + 1:02d}",
                "design": {"module_name": design, "prefetcher_source": d["source"]},
                "reference": {"module_name": reference, "prefetcher_source": r["source"]},
                "expected_verdict": verdict,
                "expected_errors": errors,
                "planting": f"real generated pair ({design} vs {reference}); {note}",
                "evidence": {
                    "design_source_sha256": hashlib.sha256(d["source"].encode()).hexdigest(),
                    "reference_source_sha256": hashlib.sha256(r["source"].encode()).hexdigest(),
                    "design_cycles": d["cycles"],
                    "reference_cycles": r["cycles"],
                    "label_basis": "measured cycles" if raw else "source structure only",
                },
            }
            (args.out_dir / f"sem-{written + 1:02d}.json").write_text(
                json.dumps(case, indent=1), encoding="utf-8")
            print(f"sem-{written + 1:02d} {design} vs {reference}: {verdict}|{','.join(errors) or '-'} "
                  f"[{note[:70]}]")
            written += 1
    print(f"cases={written} candidates={len(names)} label_basis={'measured' if raw else 'structure-only'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
