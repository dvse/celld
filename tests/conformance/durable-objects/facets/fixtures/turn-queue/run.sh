#!/bin/bash
# run.sh CELLD_BINARY PORT [ROUNDS]: serve this fixture with `celld dev` and print one result
# line per round. Expected: {"race":"pong","hold":"held","probe":"alive"} every round.
set -u
BIN=$1 PORT=$2 ROUNDS=${3:-5} HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
"$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
# Warm the object and its facet so each round measures only the race.
curl -s --max-time 30 "http://127.0.0.1:$PORT/probe" >/dev/null
for round in $(seq 1 "$ROUNDS"); do
  curl -s --max-time 20 -o "$STATE/race.$round" "http://127.0.0.1:$PORT/race" &
  RACE=$!
  sleep 0.03
  HOLD=$(curl -s --max-time 20 "http://127.0.0.1:$PORT/hold?n=15000000")
  wait $RACE
  PROBE=$(curl -s --max-time 10 "http://127.0.0.1:$PORT/probe")
  printf '{"round":%s,"race":%s,"hold":%s,"probe":%s}\n' "$round" "$(cat "$STATE/race.$round" 2>/dev/null || true)" "${HOLD:-null}" "${PROBE:-null}" | sed 's/:,/:null,/g; s/:}/:null}/g'
done
kill -INT $DEV; wait $DEV 2>/dev/null
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
