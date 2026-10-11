#!/bin/bash
set -euo pipefail
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
case "$PORT" in 9[78][0-9][0-9]) ;; *) exit 2;; esac
STATE=$(mktemp -d)
cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
"$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
trap 'kill -INT "$DEV" 2>/dev/null || true; wait "$DEV" 2>/dev/null || true; pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null || true' EXIT
U=http://127.0.0.1:$PORT
for i in $(seq 1 60); do curl -sf "$U/.well-known/celld/health" >/dev/null && break; sleep 1; done
curl -fsS --max-time 10 "$U/park" >/dev/null
curl -fsS --max-time 10 "$U/release" >/dev/null
sleep 1
ACTOR=$(curl -fsS --max-time 10 "$U/result")
curl -fsS --max-time 10 "$U/dead-park" >/dev/null
DEAD=$(curl -fsS --max-time 10 "$U/dead-release")
NESTED=$(curl -fsS --max-time 10 "$U/dead-in-turn")
printf 'actor: %s\nstateless: %s\nended callee in live turn: %s\n' "$ACTOR" "$DEAD" "$NESTED"
test "$ACTOR" = origin-ok
test "$DEAD" = dead-rejected
test "$NESTED" = dead-rejected
