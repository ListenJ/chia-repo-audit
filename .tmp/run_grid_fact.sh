#!/bin/bash
# Run the prompt-factorial grid inside the official image on GCP.
# Mirrors .tmp/run_grid_gcp.sh; the config changes seeds x prompts from 3x1 to 1x3,
# so the prompt axis is measured for the first time.
set -uo pipefail
cd /workspace || exit 1
git rev-parse HEAD > .tmp/grid_git_sha 2>/dev/null || echo "no-git" > .tmp/grid_git_sha
sha256sum .tmp/cfg/grid_fact.json > .tmp/grid_config_sha
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
date -Is > .tmp/grid_start
python3 chia_loop/loops/audit_repro.py \
  --version 6 \
  --config /workspace/.tmp/cfg/grid_fact.json \
  --backend champsim_node \
  --generator-mode directory \
  --execution local \
  --output-dir /workspace/results/grid_fact_prompt
echo "grid_rc=$?"
date -Is > .tmp/grid_end
ray stop >/dev/null 2>&1 || true
