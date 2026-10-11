#!/bin/bash
# run.sh CELLD_BINARY PORT: prepare, stop the node, start again, and read back.
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
for path in /prepare /report; do
  "$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev$(echo $path | tr / -).log" 2>&1 &
  DEV=$!
  for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
  echo "$path $(curl -s --max-time 30 "http://127.0.0.1:$PORT$path")"
  kill -INT $DEV; wait $DEV 2>/dev/null; pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null; sleep 2
done
mv "$STATE" "$STATE.done"
