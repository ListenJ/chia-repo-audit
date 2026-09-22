"""Per-trace no-op and next-line reference runs for the ChampSim backend.

The compile screening shows that a candidate can compile, enter the simulated
machine under a distinct binary digest, and still reproduce the no-op cycle
count exactly. A ranking over generated candidates is therefore only readable
against a reference design measured on the same trace and the same instruction
budget. This script builds each reference design once and runs that binary on
every trace, because the binary is trace independent, so the reference costs two
cold builds rather than two builds per trace.

Run inside the official image with Ray started, as
scripts/module_effect_control.py does.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/workspace")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chia.base.ChiaFunction import get
from chia.simulators.champsim import ChampSimNode
from module_effect_control import NEXT_LINE, NOOP

DESIGNS = (("noop", NOOP, "probe_noop"), ("next_line", NEXT_LINE, "probe_next_line"))


def emit(record: dict) -> None:
    print(json.dumps(record, ensure_ascii=False), flush=True)


def build_and_run(node, source: str, module: str, traces: list[str], *,
                  warmup: int, sim: int) -> dict:
    started = time.monotonic()
    build = get(node.build_champsim.chia_remote(
        "/home/ray/champsim", source, module,
        cache_level="L2C", timeout_s=2400, incremental=False))
    out = {"module": module, "incremental": False,
           "build_success": bool(getattr(build, "success", False)),
           "build_s": round(time.monotonic() - started, 1)}
    if not out["build_success"]:
        out["diagnostics_tail"] = str(getattr(build, "build_diagnostics", ""))[-1500:]
        return out
    binary = getattr(build, "binary", b"")
    out["binary_sha256"] = hashlib.sha256(binary).hexdigest()[:16]
    out["base_rev"] = getattr(build, "base_rev", None)
    for trace in traces:
        started = time.monotonic()
        run = get(node.run_champsim.chia_remote(
            binary=binary, trace=trace, warmup_instructions=warmup,
            simulation_instructions=sim, timeout_s=2400))
        out["runs"] = out.get("runs", [])
        row = {"trace": Path(trace).name, "run_s": round(time.monotonic() - started, 1),
               "success": bool(getattr(run, "success", False)),
               "instructions": getattr(run, "instructions", None),
               "cycles": getattr(run, "cycles", None),
               "ipc": getattr(run, "ipc", None)}
        if not row["success"]:
            row["stdout_tail"] = str(getattr(run, "stdout_tail", ""))[-800:]
        out["runs"].append(row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", action="append", required=True,
                        help="repeat once per trace; the same binary runs each one")
    parser.add_argument("--warmup-instructions", type=int, default=1_000_000)
    parser.add_argument("--simulation-instructions", type=int, default=4_000_000)
    args = parser.parse_args()

    node = ChampSimNode(require_colocated=False)
    failed = 0
    for name, source, module in DESIGNS:
        out = build_and_run(node, source, module, args.trace,
                            warmup=args.warmup_instructions,
                            sim=args.simulation_instructions)
        emit({"design": name, **out})
        if not out["build_success"]:
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
