# R4-03 — ordering and failure retention (partial finding)

The extracted actual DurableObjectFacets class runs with controlled host ops.
Clone then delete must issue clone before delete. A failed clone must remain
in storage.sync()'s proof set after its promise settles. The baseline reverses
the two host operations and loses the rejection.

This does NOT verify an atomic snapshot at the synchronous clone() boundary.
The async, per-stream native copy still lacks that guarantee. R4-03 remains
P1/open for concurrent source continuations and subtree consistency, as well
as automatic root output-gate poisoning on a clone failure.
