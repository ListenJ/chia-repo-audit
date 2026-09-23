#!/bin/bash
# Wait for the grid and the reference runs, then check the artifact and report.
set -uo pipefail
cd /home/listen/CHIA/chia-repo-audit || exit 1
log() { echo "$(date -Is) $*"; }

log "watch start"
while :; do
  grid=$(docker inspect -f '{{.State.Status}}' chia-grid 2>/dev/null || echo none)
  base=$(docker inspect -f '{{.State.Status}}' chia-baseline 2>/dev/null || echo none)
  [ "$grid" = "exited" ] && [ "$base" = "exited" ] && break
  [ "$grid" = "exited" ] && [ "$base" = "none" ] && \
    grep -q "grid blocked" .tmp/grid_chain_status.log && break
  sleep 60
done
log "grid=$grid baseline=$base"

docker logs chia-grid 2>&1 | grep -E "grid_rc=|Traceback|Error" | tail -5
log "grid tail above"

if [ -s .tmp/baseline_probe.jsonl ]; then
  cp .tmp/baseline_probe.jsonl results/reference_designs_2026-09-22.jsonl
  log "reference evidence copied"
fi

if [ -f results/grid_v6/raw.json ]; then
  ARGS=(--raw results/grid_v6/raw.json)
  [ -s results/reference_designs_2026-09-22.jsonl ] &&
    ARGS+=(--reference results/reference_designs_2026-09-22.jsonl)
  python3 scripts/check_grid_evidence.py "${ARGS[@]}" > .tmp/grid_check.json 2>&1
  log "checker rc=$? written to .tmp/grid_check.json"
  python3 - <<'PY'
import json
out = json.load(open('.tmp/grid_check.json'))
print("passed:", out["passed"], "rows:", out["n_rows"], "designs:", out["n_designs"],
      "distinct binaries:", out["n_distinct_binaries"])
for name, items in out["failures"].items():
    print(f"  FAIL {name}: {items[:3]}{' ...' if len(items) > 3 else ''}")
PY
else
  log "no raw.json: grid never ran"
  tail -3 .tmp/grid_chain_status.log
fi
log "watch end"
