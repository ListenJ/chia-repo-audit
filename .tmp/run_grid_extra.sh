#!/bin/bash
# Measure the three factorial designs the rectangle rule dropped, so the semantic
# audit set has measurement-grounded labels for six designs instead of three.
# Two configs, each a complete seed x prompt rectangle: directory mode falls back to
# the whole pool for a cell with no matching candidate, which would silently score the
# wrong design, so no non-rectangular config is used here.
set -uo pipefail
cd /workspace || exit 1
git rev-parse HEAD > .tmp/grid_git_sha 2>/dev/null || echo no-git > .tmp/grid_git_sha
sha256sum .tmp/cfg/grid_x_a.json .tmp/cfg/grid_x_b.json > .tmp/grid_config_sha
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats

run_one () {
  local cfg="$1" out="$2" expect="$3"
  date -Is > .tmp/grid_start
  python3 chia_loop/loops/audit_repro.py \
    --version 6 \
    --config "/workspace/.tmp/cfg/${cfg}" \
    --backend champsim_node \
    --generator-mode directory \
    --execution local \
    --output-dir "/workspace/results/${out}"
  local rc=$?
  date -Is > .tmp/grid_end
  local cells
  cells=$(python3 -c "
import json,sys
try:
    d=json.load(open('/workspace/results/${out}/raw.json'))
    c=d['cells'] if isinstance(d,dict) and 'cells' in d else d
    print(len(c))
except Exception as exc:
    print(0)
" 2>/dev/null)
  echo "cfg=${cfg} rc=${rc} cells=${cells} expected=${expect}"
  if [ "$cells" != "$expect" ]; then
    echo "FATAL: ${out} produced ${cells} cells, expected ${expect}" >&2
    return 1
  fi
  return 0
}

fail=0
run_one grid_x_a.json grid_x_fill_only_s2s3 6 || fail=1
run_one grid_x_b.json grid_x_aggressive_s3 3 || fail=1
ray stop >/dev/null 2>&1 || true
[ "$fail" -eq 0 ] || { echo "FATAL: a measurement stage under-delivered" >&2; exit 3; }
echo "EXTRA_MEASUREMENTS_OK"
