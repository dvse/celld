#!/bin/bash
# run.sh CELLD_BINARY PORT
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
"$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
curl -s "http://127.0.0.1:$PORT/start" >/dev/null; sleep 0.5
curl -s "http://127.0.0.1:$PORT/release" >/dev/null; sleep 1
curl -s "http://127.0.0.1:$PORT/result"; echo
kill -INT $DEV; wait $DEV 2>/dev/null
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
