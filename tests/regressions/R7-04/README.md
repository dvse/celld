# R7-04 — persistent live/promised client transfer

Workerd worker-rpc.c++:782–886 distinguishes RPC clients from stored/Frankenvalue
channels. The duplicate/legacy-transfer matrix checks live, lazy and pending
clients, shared restore counts/incarnation, failed restoration, encoding rollback,
returned wrappers and delayed nested-result wrapper disposal. Storage decode is
an intentional new lazy client; RPC transfer must carry its single admitted
client. The full series uses the shared bounded-port MinIO/workerd launcher.

The real workerd oracle establishes two boundaries: `dup()` of a never-used
stored wrapper leaves two lazy clients (two restores); an RPC send forces one
client before it crosses the wire. A plain returned graph releases the source
wrapper on resolution; a graph with a top-level disposer retains it until the
result is disposed. Both boundaries are tested. Celld preserves its existing
atomic rollback of an uncloneable transfer graph, as the review requires;
workerd consumes the already-serialized wrapper in legacy transfer mode even
on that error. Only that recorded assertion has a separate workerd expectation
(`expected-workerd.json`); duplicate mode has identical rollback semantics.

HTTP channel control: the R5-04 three-node matrix exercises restored service,
DO, facet and dynamic Fetchers, request/response streaming and WebSocket upgrade.
A pending client forwards the native request body exactly once from its call
driver or resource owner. It must still reject a stream owned by neither; it
never steals a source from the global stream registry.
