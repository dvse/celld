# C6-02 — capability ordering lane broken by an undelivered call

Tunez Celld 6 (2026-10-10), planet-2: 15,861 `capability ordering channel is
broken` errors in 24 s at 17:02 AEST, a sustained stream 20:09–20:22, each
burst opened by `predecessor did not arrive` exactly 60 s
(`ORDER_GAP_TIMEOUT`) after its lane stalled.

Mechanism: the caller assigns a lane sequence number in JS before the native
op runs. When the op is dropped before the request reaches the callee
(caller context ended or aborted, output gate failure, session/transfer setup
failure, transport error) or the callee rejects the request before ordered
admission, that slot is never resolved. Every later call on the lane waits
60 s, then the lane is marked broken forever; the page host's push loop
turned each instant failure into another push.

Reproduction: a long-lived local `RpcStub` owned by a Durable Object on node
`owner`; a stateless request on node `caller` fires three ordered calls and
returns without awaiting them (its ops are dropped with the request), then
the next request calls the same capability. Before: the call hangs (8 s probe
timeout; later 60 s break). After: every round completes in milliseconds.

workerd: one Cap'n Proto connection per peer gives e-order; a message cannot
be lost without the connection failing, which fails all of its calls
(capnp/rpc.c++). Fix: every slot is resolved exactly once — dispatch, callee
rejection before admission (`OrderSlot`), or a caller `Skip` notice on the
authenticated process session (`CallerOrderSlot`); a lost session fails its
lanes immediately.
