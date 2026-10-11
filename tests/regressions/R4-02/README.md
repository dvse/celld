R4-02: actual harness state-machine unit test, with transport failure injected
at __stubOp. Workerd keeps a live client's identity after breakage
(worker-rpc.c++:683–738). Calls must not restore or replay, even with the
private, authenticated pre-dispatch rejection tag. Baseline restores 3 times
and dispatches 4 calls; fixed code restores once and dispatches twice.
`CELLD_SOURCE=/path/to/crates/celld/js/harness.js node run.mjs` selects the
source pin. No source transformation or alternate implementation is used.
This test does not claim a fleet restart or packet-loss integration test.

The full Worker case is a reference control: duplicating a stored token before
its first use restores independently in stock workerd, yielding [1,1,2]. That
behavior is preserved. It is distinct from duplicating an already resolved
live client, which must share identity. This control passes on the baseline;
the injected pre-dispatch failure above is the regression that fails there.
