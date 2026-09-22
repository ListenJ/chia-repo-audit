"""Turn a grid raw.json into gate verdicts, without re-deriving nothing by eye.

Checks what `results/grid_v6/raw.json` can prove on its own: the backend is the
real ChampSimNode adapter, each design was measured with its own binary digest,
no design inherited the binary the image ships, repeats agree, and the measured
instruction count is above the smoke floor. Cycle counts are compared against a
reference design measured on the same trace and instruction budget, because a
candidate can compile, enter the machine, and still do nothing.

Usage:
  python3 scripts/check_grid_evidence.py --raw results/grid_v6/raw.json \
      [--reference results/reference_designs_2026-09-22.jsonl] \
      [--image-binary 688278205d6c9fa4]
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

SMOKE_INSTRUCTION_FLOOR = 1_000_000
IMAGE_DEFAULT_BINARY = "688278205d6c9fa4"


def load_cells(raw: dict) -> list[dict]:
    rows = []
    for cell in raw["cells"].values():
        digests = {trial.get("binary_sha256") for trial in cell["trials"]}
        cycles = [trial["cycles"] for trial in cell["trials"]]
        instructions = cell["median"].get("instructions")
        if isinstance(instructions, float) and math.isnan(instructions):
            instructions = None
        rows.append({
            "design": f"{cell['prompt']}/{cell['seed']}",
            "module": cell["design"].get("module_name"),
            "trace": cell["trace"],
            "binary_sha256": sorted(d for d in digests if d)[0] if digests - {None, ""} else "",
            "digests_per_cell": len(digests - {None, ""}),
            "cycles": cell["median"]["cycles"],
            "ipc": cell["median"]["ipc"],
            "instructions": instructions,
            "repeat_spread": (max(cycles) - min(cycles)) / statistics.mean(cycles)
            if len(cycles) > 1 and statistics.mean(cycles) else 0.0,
        })
    return sorted(rows, key=lambda r: (r["design"], r["trace"]))


def verdicts(raw: dict, reference: list[dict] | None,
             image_binary: str = IMAGE_DEFAULT_BINARY) -> dict:
    rows = load_cells(raw)
    checks: dict[str, list[str]] = {}

    def fail(name: str, detail: str) -> None:
        checks.setdefault(name, []).append(detail)

    if raw.get("backend") != "champsim_node":
        fail("backend_is_real", f"backend={raw.get('backend')!r}")
    if not raw.get("git_sha"):
        fail("commit_sha_retained", "raw.json has no git_sha")
    if not raw.get("config_sha256"):
        fail("config_sha_retained", "raw.json has no config_sha256")

    noop_cycles = {}
    for record in reference or []:
        if record.get("design") == "noop":
            for run in record.get("runs", []):
                noop_cycles[Path(run["trace"]).name] = run["cycles"]

    by_design: dict[str, set] = {}
    owners: dict[str, set] = {}
    for row in rows:
        by_design.setdefault(row["design"], set()).add(row["binary_sha256"])
        if row["binary_sha256"]:
            owners.setdefault(row["binary_sha256"], set()).add(row["design"])
        if not row["binary_sha256"]:
            fail("binary_digest_recorded", row["design"])
        elif row["binary_sha256"] == image_binary:
            fail("not_the_image_default_binary", row["design"])
        if row["digests_per_cell"] > 1:
            fail("one_binary_per_design", f"{row['design']} used {row['digests_per_cell']}")
        if row["repeat_spread"] > 0.01:
            fail("repeats_agree", f"{row['design']} {row['trace']} spread={row['repeat_spread']:.4f}")
        if (row["instructions"] or 0) < SMOKE_INSTRUCTION_FLOOR:
            fail("above_smoke_floor", f"{row['design']} instructions={row['instructions']}")
        baseline = noop_cycles.get(row["trace"])
        if baseline is None:
            fail("reference_available", row["trace"])
        elif row["cycles"] == baseline:
            fail("moves_cycles_vs_reference",
                 f"{row['design']} on {row['trace']} equals noop at {baseline:g}")

    for digest, design_names in owners.items():
        if len(design_names) > 1:
            fail("one_design_per_binary",
                 f"{digest} measured for {sorted(design_names)}")
    return {
        "n_rows": len(rows),
        "n_designs": len(by_design),
        "n_distinct_binaries": len(owners),
        "reference_traces": sorted(noop_cycles),
        "failures": {name: sorted(set(items)) for name, items in sorted(checks.items())},
        "passed": not checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--reference", type=Path,
                        help="JSONL from scripts/baseline_probe.py")
    parser.add_argument("--image-binary", default=IMAGE_DEFAULT_BINARY)
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text())
    reference = [json.loads(line) for line in args.reference.read_text().splitlines()
                 if line.strip()] if args.reference else None
    out = verdicts(raw, reference, args.image_binary)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
