#!/bin/bash
# run.sh CELLD_BINARY PORT: deploy owner.json then wrangler.json (caller) into one dev store and query.
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE"/*.js "$HERE"/*.json "$STATE/"
for config in owner.json wrangler.json; do
  "$BIN" dev "$STATE/$config" --port "$PORT" --no-watch > "$STATE/$config.log" 2>&1 &
  DEV=$!
  for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
  [ "$config" = wrangler.json ] && { curl -s --max-time 20 "http://127.0.0.1:$PORT/?n=$RANDOM"; echo; }
  kill -INT $DEV; wait $DEV 2>/dev/null; pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null; sleep 1
done
grep -h -i -E "error|refus" "$STATE"/*.log | head -5
mv "$STATE" "$STATE.done"
