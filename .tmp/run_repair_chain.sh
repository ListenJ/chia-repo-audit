#!/bin/bash
# Chain: finish the cand2 screening, generate one compile-feedback repair per
# failure, then screen the repairs. Status is appended to .tmp/chain_status.log.
set -uo pipefail
cd /home/listen/CHIA/chia-repo-audit || exit 1
st() { echo "$(date -Is) $*" >> .tmp/chain_status.log; }

count_compiled() {
  python3 - "$1" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip().startswith('{"design')]
print(f"{sum(1 for r in rows if r.get('build_success'))}/{len(rows)} compiled")
PY
}

st "chain start"
while [ "$(docker inspect -f '{{.State.Running}}' chia-screen2 2>/dev/null)" = "true" ]; do sleep 20; done
docker logs chia-screen2 2>&1 | grep -o '^{"design.*' > .tmp/screen2.jsonl
st "screen2 finished: $(count_compiled .tmp/screen2.jsonl)"

if ! ls .tmp/cand3/gen_*.json >/dev/null 2>&1; then
  python3 scripts/real_candidate_generate.py \
    --out-dir .tmp/cand3 \
    --cells "default:0,default:1,default:2,aggressive_offset:0,aggressive_offset:1,aggressive_offset:2" \
    --repair-from .tmp/screen2.jsonl --source-dir .tmp/cand2 > .tmp/gen3.log 2>&1
  st "repairs generated: $(ls .tmp/cand3/gen_*.json 2>/dev/null | wc -l) rc=$?"
fi

if ls .tmp/cand3/gen_*.json >/dev/null 2>&1; then
  docker rm -f chia-screen3 >/dev/null 2>&1
  docker run -d --name chia-screen3 --memory=10g --memory-swap=20g --shm-size=2g \
    -v /home/listen/CHIA/chia-repo-audit:/workspace \
    -v /home/listen/下载:/traces:ro -w /workspace \
    ghcr.io/ucb-bar/chia-champsim:latest bash -c \
    'ray stop >/dev/null 2>&1; ray start --head --port=6379 --resources="{\"champsim\":1}" --disable-usage-stats >/dev/null 2>&1; python3 scripts/module_effect_control.py --candidate /workspace/.tmp/cand3 --trace /traces/SPEC17-649.fotonik3d_s-1B.champsimtrace.xz; echo "screen_rc=$?"; ray stop >/dev/null 2>&1'
  st "screen3 launched"
else
  st "no repairs to screen"
fi
st "chain end"
