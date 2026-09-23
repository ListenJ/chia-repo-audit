#!/bin/bash
# Screen the 9 prompt x seed factorial candidates: one cold build and one run each.
# Same trace and instruction budget as the 2026-09-22 screening, so the compile-rate
# denominator stays comparable. Non-JSON noise is tolerated by make_grid_config.py,
# which only reads lines starting with {"design.
set -uo pipefail
cd /workspace || exit 1
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
TRACE=/traces/SPEC17-649.fotonik3d_s-1B.champsimtrace.xz
OUT=/workspace/.tmp/screen_fact.jsonl
PROBE=/workspace/.tmp/one_cold.py
: > "$OUT"
if [ ! -f "$PROBE" ]; then
  echo "FATAL: $PROBE missing; refusing to report success on zero work" >&2
  ray stop >/dev/null 2>&1 || true
  exit 2
fi
for f in /workspace/.tmp/cand_fact2/gen_*.json; do
  tag=$(basename "$f" .json)
  echo "=== $tag start $(date -Is) ==="
  python3 "$PROBE" \
    --candidate "$f" --trace "$TRACE" --tag "$tag" 2>&1 | tee -a "$OUT"
  echo "=== $tag end $(date -Is) rc=$? ==="
done
n=$(grep -c '{"design' "$OUT")
echo "screened_records=$n expected=9"
ray stop >/dev/null 2>&1 || true
# A container that exits 0 having measured nothing is the failure mode we are gating
# against, so the exit code carries the record count.
[ "$n" -eq 9 ] || { echo "FATAL: only $n of 9 candidates produced a record" >&2; exit 3; }
