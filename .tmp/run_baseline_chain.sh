#!/bin/bash
# Launch the reference-design container only once the host has room for a second
# concurrent cold build: every screening finished and only the grid is running.
set -uo pipefail
cd /home/listen/CHIA/chia-repo-audit || exit 1
st() { echo "$(date -Is) $*" >> .tmp/baseline_chain_status.log; }
st "baseline chain start"
while :; do
  screens=$(docker ps --format '{{.Names}}' | grep -c '^chia-screen' || true)
  heavies=$(docker ps --format '{{.Names}}' | grep -c '^chia-' || true)
  avail=$(free -m | awk 'NR==2{print $7}')
  if [ "$screens" = "0" ] && [ "$heavies" -le 1 ] && [ "$avail" -ge 6000 ]; then break; fi
  sleep 60
done
st "room found: heavies=$heavies available=${avail}MiB"
docker rm -f chia-baseline >/dev/null 2>&1
docker run -d --name chia-baseline --memory=10g --memory-swap=20g --shm-size=2g \
  -v /home/listen/CHIA/chia-repo-audit:/workspace \
  -v /home/listen/下载:/traces:ro -w /workspace \
  ghcr.io/ucb-bar/chia-champsim:latest bash /workspace/.tmp/run_baselines.sh >/dev/null
st "baseline container launched"
