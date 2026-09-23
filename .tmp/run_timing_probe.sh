#!/bin/bash
set -uo pipefail
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
date +%s > /workspace/.tmp/t0
for spec in "probe_seed:out_seed" "probe_prompt:out_prompt"; do
  cfg=${spec%%:*}; out=${spec##*:}
  echo "=== $cfg start $(date -Is)"
  python3 chia_loop/loops/audit_repro.py --version 6 --config /workspace/.tmp/cfg/$cfg.json --backend champsim_node --generator-mode directory --execution local --output-dir /workspace/.tmp/out_$out
  echo "=== $cfg rc=$? end $(date -Is)"
done
date +%s > /workspace/.tmp/t1
ray stop >/dev/null 2>&1 || true
