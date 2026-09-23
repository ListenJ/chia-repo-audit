#!/bin/bash
# Host-side chain: wait for the v7 grid container to exit, then screen the factorial.
# Deliberately serial - running both at once would double both wall clocks and the
# grid's wall_clock_s is itself evidence.
set -uo pipefail
IMG=ghcr.io/ucb-bar/chia-champsim@sha256:610951d382f9e6cdfc51a4526ba70e36c80f3375b1dc19d60117bc47f20e94c4
STATUS=/home/devstar7744/screen_fact_status.json
LOG=/home/devstar7744/screen_fact.log

echo "{\"state\":\"waiting_for_v7\",\"at\":\"$(date -Is)\"}" > "$STATUS"
while sudo docker ps --format '{{.Names}}' | grep -q '^chia-grid7$'; do sleep 60; done
echo "{\"state\":\"running\",\"at\":\"$(date -Is)\"}" > "$STATUS"

sudo docker run --rm --name chia-screen -e OMP_NUM_THREADS=8 \
  -v /home/devstar7744/repo:/workspace \
  -v /home/devstar7744/traces:/traces:ro \
  --memory 12g "$IMG" bash /workspace/.tmp/screen_fact.sh >> "$LOG" 2>&1
rc=$?
echo "{\"state\":\"done\",\"rc\":$rc,\"at\":\"$(date -Is)\"}" > "$STATUS"
