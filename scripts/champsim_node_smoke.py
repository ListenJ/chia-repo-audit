#!/usr/bin/env python3
"""Run the official CHIA ChampSimNode build/run path in one container."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


NEXT_LINE_SOURCE = r"""
#include <cstdint>
#include "address.h"
#include "modules.h"

struct evolved_pf : public champsim::modules::prefetcher {
  using prefetcher::prefetcher;

  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip,
                                     uint8_t cache_hit, bool useful_prefetch,
                                     access_type type, uint32_t metadata_in) {
    champsim::block_number pf_addr{addr};
    prefetch_line(champsim::address{pf_addr + 1}, true, metadata_in);
    return metadata_in;
  }

  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way,
                                  uint8_t prefetch, champsim::address evicted_addr,
                                  uint32_t metadata_in) {
    return metadata_in;
  }
};
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--champsim-root", default="/home/ray/champsim")
    parser.add_argument(
        "--trace",
        default="/home/ray/champsim/test/traces/smoke.champsimtrace.gz",
    )
    parser.add_argument("--module-name", default="evolved_pf")
    parser.add_argument("--cache-level", default="L2C")
    parser.add_argument("--warmup-instructions", type=int, default=1000)
    parser.add_argument("--simulation-instructions", type=int, default=5000)
    parser.add_argument("--start-ray", action="store_true")
    parser.add_argument("--source-file", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def start_local_ray() -> None:
    subprocess.run(["ray", "stop"], check=False)
    subprocess.run(
        [
            "ray",
            "start",
            "--head",
            "--port=6379",
            "--resources={\"champsim\":1}",
            "--disable-usage-stats",
        ],
        check=True,
    )


def main() -> dict:
    args = parse_args()
    if args.start_ray:
        start_local_ray()

    from chia.base.ChiaFunction import get
    from chia.simulators.champsim import ChampSimNode

    node = ChampSimNode(require_colocated=False)
    source = (
        args.source_file.read_text()
        if args.source_file is not None
        else NEXT_LINE_SOURCE
    )
    build = get(
        node.build_champsim.chia_remote(
            args.champsim_root,
            source,
            args.module_name,
            cache_level=args.cache_level,
            timeout_s=1800,
            incremental=True,
        )
    )
    if not build.success:
        raise RuntimeError(
            f"ChampSimNode build failed: {build.build_diagnostics}"
        )

    run = get(
        node.run_champsim.chia_remote(
            binary=build.binary,
            trace=args.trace,
            warmup_instructions=args.warmup_instructions,
            simulation_instructions=args.simulation_instructions,
            timeout_s=300,
        )
    )
    if not run.success:
        raise RuntimeError(f"ChampSimNode run failed: {run.stdout_tail}")

    result = {
        "build_success": build.success,
        "run_success": run.success,
        "module_name": args.module_name,
        "cache_level": args.cache_level,
        "base_rev": build.base_rev,
        "instructions": run.instructions,
        "cycles": run.cycles,
        "ipc": run.ipc,
        "trace": args.trace,
    }
    print(json.dumps(result, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    try:
        main()
    finally:
        if "--start-ray" in sys.argv:
            subprocess.run(["ray", "stop"], check=False)
