#!/usr/bin/env python3
"""Re-score a completed grid from its retained raw.json, without re-simulating.

A gate fix is worthless if correcting a verdict means spending another grid run:
this recomputes the audit report from the evidence that is already on disk, so a
published scorecard can be re-derived and superseded in place. It reuses
audit_repro._compute_audit rather than reimplementing the metrics, so the two paths
cannot drift.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "chia_loop" / "loops"))

import audit_repro  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True,
                        help="raw.json from a completed grid")
    parser.add_argument("--grid-dir", type=Path, default=None,
                        help="directory holding the grid outputs; defaults to the raw file parent")
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--version", type=int, default=6)
    parser.add_argument("--write", action="store_true",
                        help="overwrite scorecard.txt and audit_report.json in the grid dir")
    args = parser.parse_args()

    raw = json.loads(args.raw.read_text(encoding="utf-8"))
    grid_dir = args.grid_dir or args.raw.parent
    dblind_path = grid_dir / "dblind_report.json"
    dblind = json.loads(dblind_path.read_text(encoding="utf-8")) if dblind_path.is_file() else {}

    config = {"version": args.version, "acceptance_threshold": args.threshold,
              "kappa_gate": 0.7}
    report = audit_repro._compute_audit(raw, config, dblind)
    scorecard = audit_repro._format_scorecard(report, config) if hasattr(
        audit_repro, "_format_scorecard") else None

    print(json.dumps({
        "grid": grid_dir.name,
        "axis_levels": report.get("axis_levels"),
        "unexercised_axes": report.get("unexercised_axes"),
        "verdict": report["verdict"],
        "publish_gate": report["publish_gate"],
        "publish_blockers": report["publish_blockers"],
        "max_seed_cv": report["max_seed_cv"],
        "max_repeat_cv": report["max_repeat_cv"],
        "max_prompt_spread": report["max_prompt_spread"],
        "max_trace_cv": report["max_trace_cv"],
    }, indent=1))

    if args.write:
        (grid_dir / "audit_report.json").write_text(json.dumps(report, indent=1),
                                                    encoding="utf-8")
        if scorecard:
            (grid_dir / "scorecard.txt").write_text(scorecard, encoding="utf-8")
        print(f"rewrote {grid_dir}/audit_report.json"
              + (" and scorecard.txt" if scorecard else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
