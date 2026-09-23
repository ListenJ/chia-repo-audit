#!/bin/bash
# Run the sized grid inside the official image, with Ray serving ChampSimNode.
set -uo pipefail
cd /workspace || exit 1
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
date -Is > .tmp/grid_start
python3 chia_loop/loops/audit_repro.py \
  --version 6 \
  --config /workspace/.tmp/cfg/grid.json \
  --backend champsim_node \
  --generator-mode directory \
  --execution local \
  --output-dir /workspace/results/grid_v6
echo "grid_rc=$?"
date -Is > .tmp/grid_end
ray stop >/dev/null 2>&1 || true
