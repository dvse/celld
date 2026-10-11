#!/bin/bash
# run.sh CELLD_BINARY PORT: serve this fixture with `celld dev` and print the result.
# Expected (workerd): "worked".
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
"$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
U=http://127.0.0.1:$PORT
curl -s --max-time 10 "$U/park" > /dev/null
# The client of /hold disconnects after 2 s, cancelling A's /hold event.
curl -s --max-time 2 "$U/hold" > /dev/null &
HOLD=$!
sleep 0.5
curl -s --max-time 10 "$U/release" > /dev/null
wait $HOLD
sleep 5
curl -s --max-time 10 "$U/result"; echo
kill -INT $DEV; wait $DEV 2>/dev/null
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
