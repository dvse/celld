#!/bin/bash
# run.sh CELLD_BINARY PORT: serve this fixture with `celld dev` and print each check.
# /keep then /use 75 s later covers D2 (the idle stateless isolate is reaped in between);
# /slow?ms=65000 covers D1.
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
"$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
get() { echo "$1 $(curl -s --max-time 120 "http://127.0.0.1:$PORT$1")"; }
get /restore
get /waituntil
get /keep
get "/slow?ms=65000"
sleep 15
get /use
grep -c "isolate freed" "$STATE/dev.log" | sed 's/^/isolates freed during run: /'
kill -INT $DEV; wait $DEV 2>/dev/null
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
