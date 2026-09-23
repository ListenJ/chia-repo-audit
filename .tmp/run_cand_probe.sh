#!/bin/bash
set -uo pipefail
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
python3 /workspace/.tmp/one_cold.py \
  --candidate /workspace/.tmp/cand/gen_default_s0.json \
  --trace /traces/SPEC17-649.fotonik3d_s-1B.champsimtrace.xz \
  --tag gen_default_s0_parallel
echo "one_cold_rc=$?"
ray stop >/dev/null 2>&1 || true
