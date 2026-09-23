#!/bin/bash
set -uo pipefail
ray stop >/dev/null 2>&1 || true
ray start --head --port=6379 --resources='{"champsim":1}' --disable-usage-stats
python3 /workspace/.tmp/probe_module_effect.py
echo "probe_rc=$?"
ray stop >/dev/null 2>&1 || true
