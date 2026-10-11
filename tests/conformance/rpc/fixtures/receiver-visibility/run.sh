#!/bin/bash
# run.sh CELLD_BINARY PORT: serve this fixture with `celld dev` and print the check result.
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
"$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
curl -s --max-time 30 "http://127.0.0.1:$PORT/?v=$RANDOM"; echo
sleep 2; curl -s --max-time 30 "http://127.0.0.1:$PORT/count"; echo
kill -INT $DEV; wait $DEV 2>/dev/null
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
