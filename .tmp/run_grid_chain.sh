#!/bin/bash
# Chain: once every screening container has finished, freeze the compile evidence,
# build the grid config from the designs that actually compiled, and launch the
# grid. Collections are by container-name prefix so new screening batches need no
# edit here.
set -uo pipefail
cd /home/listen/CHIA/chia-repo-audit || exit 1
st() { echo "$(date -Is) $*" >> .tmp/grid_chain_status.log; }

st "grid chain start"
while :; do
  running=$(docker ps --format '{{.Names}}' | grep -c '^chia-screen' || true)
  [ "$running" = "0" ] && break
  sleep 30
done

: > .tmp/screens_all.jsonl
for c in $(docker ps -a --format '{{.Names}}' | grep '^chia-screen' | sort); do
  docker logs $c 2>&1 | grep -o '^{"design.*' >> .tmp/screens_all.jsonl || true
done
total=$(wc -l < .tmp/screens_all.jsonl)
built=$(grep -c '"build_success": true' .tmp/screens_all.jsonl || true)
st "screenings: $built compiled of $total designs"
cp .tmp/screens_all.jsonl results/candidate_compile_screening_2026-09-22.jsonl

if python3 scripts/make_grid_config.py --logs .tmp/screens_all.jsonl \
     --candidate-dirs .tmp/cand .tmp/cand2 .tmp/cand3 .tmp/cand4 \
     > .tmp/grid_config_out 2>&1; then
  st "config: $(tr '\n' ' ' < .tmp/grid_config_out)"
  docker rm -f chia-grid >/dev/null 2>&1
  docker run -d --name chia-grid --memory=10g --memory-swap=20g --shm-size=2g \
    -v /home/listen/CHIA/chia-repo-audit:/workspace \
    -v /home/listen/下载:/traces:ro -w /workspace \
    ghcr.io/ucb-bar/chia-champsim:latest bash /workspace/.tmp/run_grid.sh >/dev/null
  st "grid launched"
else
  st "grid blocked: $(tr '\n' ' ' < .tmp/grid_config_out)"
fi
st "grid chain end"
