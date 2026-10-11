#!/bin/bash
# run.sh CELLD_BINARY PORT: `celld dev` must refuse the config and name `environment`.
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
timeout 30 "$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1
grep -o "sets \`environment\`[^;]*" "$STATE/dev.log" || (curl -s --max-time 5 "http://127.0.0.1:$PORT/"; echo " (accepted)")
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
