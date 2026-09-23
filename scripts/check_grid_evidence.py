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
        measured = [value for value in cycles if value is not None]
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
            "n_unmeasured": len(cycles) - len(measured),
            "repeat_spread": (max(measured) - min(measured)) / statistics.mean(measured)
            if len(measured) > 1 and statistics.mean(measured) else 0.0,
        })
    return sorted(rows, key=lambda r: (r["design"], r["trace"]))


def verdicts(raw: dict, reference: list[dict] | None,
             image_binary: str = IMAGE_DEFAULT_BINARY) -> dict:
    rows = load_cells(raw)
    checks: dict[str, list[str]] = {}
    notes: list[str] = []

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
    # Nullity is a per-trace property, and "does nothing anywhere" and "does nothing on
    # this workload" are different findings. Reporting both under one flag made a normal
    # trace-dependent result indistinguishable from a design that never fires.
    null_on: dict[str, set] = {}
    comparable: dict[str, set] = {}
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
        if row["n_unmeasured"]:
            fail("all_repeats_measured",
                 f"{row['design']} on {row['trace']} has {row['n_unmeasured']} trial(s)"
                 " without cycles")
        if row["repeat_spread"] > 0.01:
            fail("repeats_agree", f"{row['design']} {row['trace']} spread={row['repeat_spread']:.4f}")
        if (row["instructions"] or 0) < SMOKE_INSTRUCTION_FLOOR:
            fail("above_smoke_floor", f"{row['design']} instructions={row['instructions']}")
        baseline = noop_cycles.get(row["trace"])
        if baseline is None:
            fail("reference_available", row["trace"])
        else:
            comparable.setdefault(row["design"], set()).add(row["trace"])
            if row["cycles"] == baseline:
                null_on.setdefault(row["design"], set()).add(row["trace"])

    total_null = {d: t for d, t in null_on.items() if t == comparable.get(d)}
    partial_null = {d: t for d, t in null_on.items() if t != comparable.get(d)}
    for design, traces in sorted(total_null.items()):
        fail("null_on_every_measured_trace",
             f"{design} equals the no-op on all {len(traces)} trace(s)")
    for design, traces in sorted(partial_null.items()):
        notes.append(f"{design} equals the no-op on {sorted(traces)[0]} only "
                     f"({len(traces)} of {len(comparable.get(design, []))} comparable "
                     "trace(s)): trace-dependent, not a null design")

    for digest, design_names in owners.items():
        if len(design_names) > 1:
            fail("one_design_per_binary",
                 f"{digest} measured for {sorted(design_names)}")
    return {
        "n_rows": len(rows),
        "n_designs": len(by_design),
        "n_distinct_binaries": len(owners),
        "reference_traces": sorted(noop_cycles),
        "nullity_notes": sorted(notes),
        "n_designs_null_on_every_trace": len(total_null),
        "n_designs_null_on_some_trace": len(partial_null),
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
