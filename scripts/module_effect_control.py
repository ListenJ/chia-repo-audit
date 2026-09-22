"""Control: does a candidate module actually enter the simulated machine?

Builds a no-op prefetcher, a known next-line prefetcher and one real LLM
candidate over the same trace window, then prints the sha256 of every delivered
binary plus the parsed metrics. Identical binary digests or identical cycle
counts mean the measurement is not sensitive to the candidate, so no ranking
claim may be made from that backend. Run inside the official image with Ray
started, as scripts/champsim_node_smoke.py does.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/workspace")

from chia.base.ChiaFunction import get
from chia.simulators.champsim import ChampSimNode

DEFAULT_TRACE = "/traces/SPEC17-649.fotonik3d_s-1B.champsimtrace.xz"

NOOP = r"""
#include <cstdint>
#include "address.h"
#include "modules.h"

struct probe_noop : public champsim::modules::prefetcher {
  using prefetcher::prefetcher;

  uint32_t prefetcher_cache_operate(champsim::address addr, champsim::address ip,
                                    uint8_t cache_hit, bool useful_prefetch,
                                    access_type type, uint32_t metadata_in) {
    return metadata_in;
  }

  uint32_t prefetcher_cache_fill(champsim::address addr, long set, long way,
                                  uint8_t prefetch, champsim::address evicted_addr,
                                  uint32_t metadata_in) {
    return metadata_in;
  }
};
"""

NEXT_LINE = r"""
#include <cstdint>
#include "address.h"
#include "modules.h"

struct probe_next_line : public champsim::modules::prefetcher {
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


def report(name, source, module, *, trace, incremental, warmup, sim):
    node = ChampSimNode(require_colocated=False)
    started = time.monotonic()
    build = get(node.build_champsim.chia_remote(
        "/home/ray/champsim", source, module,
        cache_level="L2C", timeout_s=2400, incremental=incremental))
    build_s = round(time.monotonic() - started, 1)
    out = {"design": name, "module": module, "incremental": incremental,
           "build_success": bool(getattr(build, "success", False)), "build_s": build_s}
    if not out["build_success"]:
        out["diagnostics_tail"] = str(getattr(build, "build_diagnostics", ""))[-1500:]
        print(json.dumps(out, ensure_ascii=False), flush=True)
        return out
    binary = getattr(build, "binary", b"")
    out["binary_sha256"] = hashlib.sha256(binary).hexdigest()[:16]
    out["binary_bytes"] = len(binary)
    out["base_rev"] = getattr(build, "base_rev", None)
    started = time.monotonic()
    run = get(node.run_champsim.chia_remote(
        binary=binary, trace=trace, warmup_instructions=warmup,
        simulation_instructions=sim, timeout_s=2400))
    out["run_s"] = round(time.monotonic() - started, 1)
    out["success"] = bool(getattr(run, "success", False))
    out["instructions"] = getattr(run, "instructions", None)
    out["cycles"] = getattr(run, "cycles", None)
    out["ipc"] = getattr(run, "ipc", None)
    if not out["success"]:
        out["stdout_tail"] = str(getattr(run, "stdout_tail", ""))[-800:]
    print(json.dumps(out, ensure_ascii=False), flush=True)
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", default=DEFAULT_TRACE)
    parser.add_argument("--candidate", default="/workspace/.tmp/cand/gen_default_s0.json",
                        help="candidate JSON, or a directory of them to screen")
    parser.add_argument("--warmup-instructions", type=int, default=1_000_000)
    parser.add_argument("--simulation-instructions", type=int, default=2_000_000)
    args = parser.parse_args()
    trace, warmup, sim = args.trace, args.warmup_instructions, args.simulation_instructions
    candidate_path = Path(args.candidate)
    if candidate_path.is_dir():
        # Screening: a compile failure is a result, not a crash, so keep going.
        paths = sorted(candidate_path.glob("*.json"))
        designs = [(json.loads(p.read_text()), p.stem) for p in paths]
    else:
        designs = [(json.loads(candidate_path.read_text()), None)]
    failed = 0
    for candidate, label in designs:
        source = candidate["design"]["prefetcher_source"]
        module = candidate["design"]["module_name"]
        if label is not None:
            out = report(label, source, module, trace=trace, incremental=False,
                         warmup=warmup, sim=sim)
            failed += 0 if out.get("build_success") else 1
            continue
        for incremental in (True, False):
            report("noop", NOOP, "probe_noop", trace=trace, incremental=incremental,
                   warmup=warmup, sim=sim)
            report("next_line", NEXT_LINE, "probe_next_line", trace=trace,
                   incremental=incremental, warmup=warmup, sim=sim)
            out = report("llm_candidate", source, module, trace=trace,
                         incremental=incremental, warmup=warmup, sim=sim)
            failed += 0 if out.get("build_success") else 1
    if failed:
        print(f"{failed} design(s) failed to build", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
