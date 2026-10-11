#!/bin/bash
# run.sh CELLD_BINARY PORT: serve this fixture with `celld dev` under a 5 s handler budget and
# print one JSON line. Expected (workerd):
#   statelessIo "io-done", doIo "io-done", doAwaitWhileObjectBusy "released", sessionWait "released",
#   statelessNothing an error (a request that awaits nothing is hung), waitUntilInContinuation
#   "accepted".
set -u
BIN=$1 PORT=$2 HERE=$(cd "$(dirname "$0")" && pwd)
STATE=$(mktemp -d); cp "$HERE/index.js" "$HERE/wrangler.json" "$STATE/"
CELLD_HANDLER_BUDGET_S=5 "$BIN" dev "$STATE" --port "$PORT" --no-watch > "$STATE/dev.log" 2>&1 &
DEV=$!
for i in $(seq 1 60); do curl -sf "http://127.0.0.1:$PORT/.well-known/celld/health" >/dev/null && break; sleep 1; done
U=http://127.0.0.1:$PORT
PIDS=()
curl -s --max-time 30 -o "$STATE/stateless-io" "$U/stateless-io?ms=8000" & PIDS+=($!)
curl -s --max-time 30 -o "$STATE/do-io" "$U/do-io?ms=8000" & PIDS+=($!)
curl -s --max-time 30 -o "$STATE/do-await" "$U/do-await" & PIDS+=($!)
# Keep another event of the object in flight past the budget, then release the waiter.
curl -s --max-time 30 -o "$STATE/do-busy" "$U/do-io?ms=9000" & PIDS+=($!)
curl -s --max-time 30 -o "$STATE/stateless-nothing" -w '%{http_code}' "$U/stateless-nothing" > "$STATE/stateless-nothing.status" & PIDS+=($!)
curl -s --max-time 30 -o "$STATE/session-wait" "$U/session-wait?ms=8000" & PIDS+=($!)
sleep 7
curl -s --max-time 10 "$U/do-release" > /dev/null
curl -s --max-time 10 "$U/start" > /dev/null
sleep 1
WAIT_UNTIL=$(curl -s --max-time 10 "$U/result")
wait "${PIDS[@]}"
body() { local v; v=$(cat "$STATE/$1" 2>/dev/null); [ -n "$v" ] && printf '%s' "$v" || printf null; }
printf '{"statelessIo":%s,"doIo":%s,"doAwaitWhileObjectBusy":%s,"sessionWait":%s,"statelessNothingStatus":%s,"waitUntilInContinuation":%s}\n' \
  "$(body stateless-io)" "$(body do-io)" "$(body do-await)" "$(body session-wait)" "$(cat "$STATE/stateless-nothing.status")" "${WAIT_UNTIL:-null}"
kill -INT $DEV; wait $DEV 2>/dev/null
pkill -INT -f -- "--listen 127.0.0.1:$PORT" 2>/dev/null
mv "$STATE" "$STATE.done"
