#!/bin/bash
# Reference designs: build each once, then run that binary on every trace.
set -uo pipefail
cd /workspace || exit 1
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
T=/traces
python3 scripts/baseline_probe.py \
  --trace "$T/SPEC17-649.fotonik3d_s-1B.champsimtrace.xz" \
  --trace "$T/ligra_BFSCC.com-lj.ungraph.gcc_6.3.0_O3.drop_15500M.length_250M.champsimtrace.xz" \
  --trace "$T/638.imagick_s-4128B.champsimtrace.xz" \
  > /workspace/.tmp/baseline_probe.jsonl 2> /workspace/.tmp/baseline_probe.err
echo "baseline_rc=$?"
ray stop >/dev/null 2>&1 || true
