#!/bin/bash
# The experiment that varies the generation seed and the prompt in the same grid.
# seeds{1,3} x prompts{aggressive_offset, fill_only_conservative} is the largest
# rectangle the compiled factorial candidates support, so both axes are exercised
# and neither can be reported as a vacuous zero.
set -uo pipefail
cd /workspace || exit 1
# The mount is owned by the host user while the container runs as ray, so git
# refuses the repository and the stage-entry capture used to write "no-git".
git config --global --add safe.directory /workspace
git rev-parse HEAD > .tmp/grid_git_sha
sha256sum .tmp/cfg/grid_both_axes.json > .tmp/grid_config_sha
cat .tmp/grid_git_sha
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
date -Is > .tmp/grid_start
python3 chia_loop/loops/audit_repro.py \
  --version 6 \
  --config /workspace/.tmp/cfg/grid_both_axes.json \
  --backend champsim_node \
  --generator-mode directory \
  --execution local \
  --output-dir /workspace/results/grid_both_axes
echo "grid_rc=$?"
date -Is > .tmp/grid_end
ray stop >/dev/null 2>&1 || true
