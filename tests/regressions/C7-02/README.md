# C7-02 — RPC objects of a stateless request, single node

Follow-up to C7-01, runnable without a fleet (`celld dev`, differential with
stock workerd). C7-01's fix installed the stateless fetch handler's
IoContext, but the first turn after the handler returned (`turn_begin`'s
first `finish_turn`, which settles a synchronously finished handler and
starts its response-body pump) still ran without it, while a Durable Object
event's first turn runs in its context. RPC objects the handler received
(owned by the request) were then read from that turn, so the owner check
refused them: a same-script loopback RPC stream returned as the body gave an
empty reply, and an RpcTarget used from a body `pull()` failed after its
first chunk (`/sync-*`, `/async-target`). Before C7-01 both sides had no id,
so these passed by accident, while `/wait-target` (the same after a timer)
already failed. A held stream read by another request failed as a premature
disconnect instead of workerd's cross-request error.

Cases (each a separate HTTP request whose body the runtime pumps):
synchronous and asynchronous bodies reading `ctx.exports` RPC results
directly, through `pull()`, through a pipelined promise; a loopback RPC
stream returned as the body; bodies an entrypoint returns from its own first
turn (`/ep-*`: a stream reading a target the callee received, and an RPC
stream it received); a stateless WebSocket whose `message` listener calls a
received RpcTarget (`/ws-sync`, `/ws-async`, via `ws.mjs`, Node's WebSocket);
and `/hold` + `/use`: a second live request is refused both the stream and
the target with the cross-request error.

Results: c793514c fails `/wait-target` and `/use` (the target and stream are
usable from another request); the C7-01-only tree fails the synchronous and
target cases, `/async-rpc-stream` and `/ep-*` (empty replies), `/ws-*`
(every message refused) and the stream refusal message; the fix and stock
workerd pass every case.

Known divergences, not asserted here:
- (Closed by C7-03.) Stubs from `ctx.exports` carrying props and Durable
  Object stubs used from another request are refused as in workerd.
- A continuation of a finished stateless request that another request
  resumes runs, but its I/O is refused ("The execution context which hosts
  this callback is no longer running."); workerd cancels it and logs a
  warning (tests-hyperbob/stateless-continuation).
- A same-script service-binding `fetch` (`ctx.exports.default.fetch`) takes a
  fast path that hands the callee's Response object to the caller, so a body
  that reads the callee's RPC objects is refused in the caller; workerd
  streams the body across.
