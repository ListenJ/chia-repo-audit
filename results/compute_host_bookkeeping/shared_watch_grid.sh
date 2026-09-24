#!/usr/bin/env bash
# 等 audit_repro 退出，然后就地打包结果并留标记。不碰正在运行的仓库工作树。
set -u
cd "$HOME/repo"
GRID="$1"
PID="$2"
mkdir -p .tmp/done
while kill -0 "$PID" 2>/dev/null; do sleep 20; done
rc_file=".tmp/done/${GRID}.status"
if [ -f "results/${GRID}/raw.json" ]; then
  cells=$(python3 -c "import json;print(len(json.load(open('results/${GRID}/raw.json'))['cells']))" 2>/dev/null || echo ERR)
  tar czf ".tmp/done/${GRID}.tgz" "results/${GRID}" 2>/dev/null
  printf 'grid=%s\nfinished=%s\ncells=%s\ntar=%s\n' "$GRID" "$(date -u +%FT%TZ)" "$cells" "${GRID}.tgz" > "$rc_file"
else
  printf 'grid=%s\nfinished=%s\ncells=0\nnote=no raw.json produced\n' "$GRID" "$(date -u +%FT%TZ)" > "$rc_file"
fi
