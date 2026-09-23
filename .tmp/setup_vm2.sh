#!/bin/bash
# One-shot environment setup for the second measurement VM.
set -uo pipefail
S=/home/devstar7744/setup2_status.json
L=/home/devstar7744/setup2.log
echo "{\"state\":\"start\",\"at\":\"$(date -Is)\"}" > "$S"

export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq >> "$L" 2>&1 || { echo "{\"state\":\"apt_failed\"}" > "$S"; exit 1; }
sudo apt-get install -y -qq docker.io git >> "$L" 2>&1 || { echo "{\"state\":\"install_failed\"}" > "$S"; exit 1; }
sudo systemctl enable --now docker >> "$L" 2>&1
echo "{\"state\":\"docker_ok\",\"at\":\"$(date -Is)\"}" > "$S"

git clone -q -b codex/colab-cpu-validation https://github.com/ListenJ/chia-repo-audit.git \
  /home/devstar7744/repo >> "$L" 2>&1 || { echo "{\"state\":\"clone_failed\"}" > "$S"; exit 1; }
echo "{\"state\":\"cloned\",\"sha\":\"$(git -C /home/devstar7744/repo rev-parse HEAD)\",\"at\":\"$(date -Is)\"}" > "$S"

sudo docker pull ghcr.io/ucb-bar/chia-champsim:latest >> "$L" 2>&1 \
  || { echo "{\"state\":\"pull_failed\"}" > "$S"; exit 1; }
echo "{\"state\":\"image_pulled\",\"at\":\"$(date -Is)\"}" > "$S"
sudo docker image inspect --format '{{.Id}} {{.RepoDigests}}' ghcr.io/ucb-bar/chia-champsim:latest >> "$L" 2>&1
