"""One design, one cold build, one run: used to parallelise the control.

Runs scripts/module_effect_control.py's report() for a single candidate so a
second container can produce the "does a real candidate compile and move the
cycle count" answer while the sequential control is still building its
controls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/scripts")

from module_effect_control import report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--warmup-instructions", type=int, default=1_000_000)
    parser.add_argument("--simulation-instructions", type=int, default=2_000_000)
    parser.add_argument("--tag", default="llm_cold")
    args = parser.parse_args()
    cand = json.loads(Path(args.candidate).read_text())
    report(args.tag, cand["design"]["prefetcher_source"], cand["design"]["module_name"],
           trace=args.trace, incremental=False, warmup=args.warmup_instructions,
           sim=args.simulation_instructions)
