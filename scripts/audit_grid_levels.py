#!/usr/bin/env python3
"""Check that every published grid cell measures the design its labels claim.

A cell carries two independent witnesses of which candidate was actually run:
``generator_seed`` (copied from the candidate file) and the candidate's own
``candidate_id`` / ``design.module_name``, which follow the ``gen_<prompt>_s<seed>``
naming convention.  The cell's ``prompt`` and ``seed`` are the grid's labels.  When
the witnesses disagree with the labels the cell is a substitute: some other design
was measured and reported under this factor level's name.

Exit code is non-zero when a grid has substitute cells that its own summary does
not disclose, because a variance axis computed over substituted cells is a
measurement of one design under several names.

Three witnesses are used and each is reported only where it applies.  Catalog mode
records its pool in ``raw.json``, so pool membership can be checked directly;
directory mode does not, so it is judged on the two remaining witnesses.  A design
name that carries no level (the stub fixture) is inconclusive rather than guilty.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^gen_(?P<prompt>.+)_s(?P<seed>\d+)")


def cell_design(cell: dict) -> str:
    design = cell.get("design") or {}
    return design.get("module_name") or cell.get("candidate_id") or ""


def label_of(name: str) -> tuple[str, int] | None:
    match = NAME_RE.match(name)
    if not match:
        return None
    return match.group("prompt"), int(match.group("seed"))


def audit_grid(path: Path) -> dict:
    raw = json.loads(path.read_text(encoding="utf-8"))
    pool = raw.get("config", {}).get("candidate_catalog") or []
    labelled = {(c.get("generator_seed"), c.get("prompt")) for c in pool
                if c.get("generator_seed") is not None or c.get("prompt") is not None}
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for cell in raw["cells"].values():
        groups[(cell["prompt"], cell["seed"])].append(cell)

    rows = []
    for (prompt, seed), cells in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        reasons = []
        for cell in cells:
            if cell.get("generator_seed") != seed:
                reasons.append(
                    f"generator_seed={cell.get('generator_seed')} != cell seed={seed}")
                break
        if labelled and (seed, prompt) not in labelled:
            reasons.append("no candidate in the recorded pool carries this level")
        names = sorted({cell_design(c) for c in cells})
        if len(names) > 1:
            reasons.append(f"traces measured {len(names)} distinct designs: {names}")
        for name in names:
            own = label_of(name)
            if own is not None and own != (prompt, seed):
                reasons.append(f"design {name!r} encodes level {own[0]!r}/{own[1]}, "
                               f"cell is labelled {prompt!r}/{seed}")
        digests = {c.get("candidate_sha256") for c in cells}
        # candidate_sha256 covers the candidate's own labels, so two files that
        # differ only in those labels look distinct. design_sha256 digests what was
        # actually compiled, which is the thing a factor level is supposed to vary.
        design_digests = {c.get("design_sha256") for c in cells}
        rows.append({
            "design": f"{prompt}/{seed}",
            "n_cells": len(cells),
            "digests": sorted(d for d in digests if d),
            "design_digests": sorted(d for d in design_digests if d),
            "name_encodes_level": all(label_of(n) is not None for n in names),
            "substituted": bool(reasons),
            "reasons": sorted(set(reasons)),
        })

    provenance = path.parent / "provenance.json"
    text = provenance.read_text(encoding="utf-8") if provenance.exists() else ""
    owners: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        for digest in row["design_digests"] or [""]:
            owners[digest].append(row["design"])
    shared = {d: sorted(names) for d, names in owners.items() if len(names) > 1}
    n_distinct = len({d for d in owners if d})
    # The stub fixture drives its cycles from (seed, prompt) arithmetic in
    # StubBackend, not from the design dict, so its 9 labelled cells legitimately
    # reuse 4 design dictionaries. Demand distinct compiled designs only where a
    # level is supposed to mean a distinct artifact: directory mode on real runs.
    enforced = raw.get("backend") != "stub"
    return {
        "grid": path.parent.name,
        "n_design_levels": len(rows),
        "n_distinct_designs": len({cell_design(c) for c in raw["cells"].values()}),
        "n_distinct_digests": n_distinct,
        "design_distinctness_enforced": enforced,
        "shared_digest_levels": shared if enforced else {},
        "levels_not_distinct": (len(rows) - n_distinct) if enforced else 0,
        "n_substituted": sum(1 for r in rows if r["substituted"]),
        "disclosed": "substitut" in text.lower(),
        "rows": rows,
    }


def main(argv: list[str]) -> int:
    grids = sorted((REPO / "results").glob("grid*/raw.json"))
    grids.append(REPO / "results/raw.json")
    if "--raw" in argv:
        grids = [Path(v) for v in argv[argv.index("--raw") + 1:]]
    results = [audit_grid(path) for path in grids if path.exists()]
    if not results:
        print("no grids found", file=sys.stderr)
        return 1
    if "--json" in argv:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0
    failed = False
    for res in results:
        clean = res["n_substituted"] == 0 and res["levels_not_distinct"] == 0
        flag = "OK " if clean or res["disclosed"] else "FAIL"
        print(f"{flag} {res['grid']}: {res['n_substituted']}/{res['n_design_levels']} "
              f"levels substituted, {res['n_distinct_digests']} distinct compiled designs "
              f"for {res['n_design_levels']} levels (disclosed={res['disclosed']})")
        for digest, names in sorted(res["shared_digest_levels"].items()):
            print(f"     = {digest[:12]} is the design behind {names}")
        for row in res["rows"]:
            if row["substituted"]:
                print(f"     - {row['design']}: {'; '.join(row['reasons'])}")
        if flag == "FAIL":
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
