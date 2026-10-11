# C7-01 — a Response received over RPC cannot be returned by a stateless fetch handler

Celld 7 fleet (2026-10-11), edge: every Hyperbob `/p/` request (`/p/nosuch`
404, unauthenticated git 401, `git clone` over `/p/~planets/<id>.git`)
answered with an empty reply; the edge logged `HTTP connections failed …
surface="public" … error=error from user's Body stream` once per request.
The origin router answers `/p/` with the Response its Publication service
binding's `route()` RPC returned, and the Publication gatekeeper re-wraps
every body (`new Response(result.body, result)`), so the response body is a
ReadableStream the router received over RPC.

Mechanism: a received RPC stream or stub records its owning IoContext
(`owner: __io_context_id()`) and refuses I/O from any other context
(workerd's cross-request I/O error). Durable Object events install their
IoContext in the continuation data for the handler and for the first turn
that settles it; the stateless `fetch` handler ran with no context id
(`""`), so the stream it received was owned by `""`. The node then pumps the
returned body from a turn that runs with the request's real context id
installed; the first pull failed the owner check, the stream errored before
its first chunk, and hyper dropped the connection without a status line.
Reading the body inside the handler worked (same `""` on both sides), which
is why only returned bodies failed.

Reproduction: two nodes; `c7-01-router` (service binding to
`c7-01-gatekeeper`, whose default `WorkerEntrypoint.route()` re-wraps a
string body, a local streamed body, or the streamed answer of a Durable
Object placed on the other node) and the same through a Durable Object RPC
method. Before: every `/p/` and `/do/` path on both ingresses is an empty
reply (`RemoteDisconnected`), while `/read` (body consumed in the handler)
passes. After: 404/401/200 with complete bodies.

workerd: one IoContext per request (io/io-context.h); the response body is
streamed within that request's context. Fix: the stateless fetch handler
installs its own tracked IoContext, and the first turn after the handler
returns (stateless fetch, entrypoint RPC, queue) runs in it, as a Durable
Object event's does, so the handler and the pump that settles it share one
owner. C7-02 covers the single-node shapes (same-script loopback RPC streams,
RpcTargets used from a body pull, cross-request refusal). Session loss on an unfinished
body still errors (R9-07 is unchanged).
