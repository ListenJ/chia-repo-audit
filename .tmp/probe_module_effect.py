"""Does the generated prefetcher module actually change the simulated machine?

Prints the sha256 of the built binary and the parsed metrics for three designs
over the same trace window. Run inside the official image with Ray started.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/workspace")

from chia.base.ChiaFunction import get
from chia.simulators.champsim import ChampSimNode

TRACE = "/traces/SPEC17-649.fotonik3d_s-1B.champsimtrace.xz"

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


def report(name, source, module, *, incremental, warmup, sim):
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
        binary=binary, trace=TRACE, warmup_instructions=warmup,
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
    candidate = json.loads(Path("/workspace/.tmp/cand/gen_default_s0.json").read_text())
    llm_source = candidate["design"]["prefetcher_source"]
    warmup, sim = 1_000_000, 2_000_000
    report("noop", NOOP, "probe_noop", incremental=True, warmup=warmup, sim=sim)
    report("next_line", NEXT_LINE, "probe_next_line", incremental=True, warmup=warmup, sim=sim)
    report("llm_gen_default_s0", llm_source, "gen_default_s0", incremental=True,
           warmup=warmup, sim=sim)
    report("noop_cold", NOOP, "probe_noop", incremental=False, warmup=warmup, sim=sim)
    report("next_line_cold", NEXT_LINE, "probe_next_line", incremental=False,
           warmup=warmup, sim=sim)
    report("noop_small_window", NOOP, "probe_noop", incremental=True,
           warmup=200_000, sim=400_000)


if __name__ == "__main__":
    main()
