R9-05 / R8-05. Workerd api/basics.c++:789–890 uses typed RPC signal externals.
Live signals own a session-accounted capability to their source transition;
forwarding owns an alias. Receiver subscriptions are unreferenced native calls,
canceled at context end/GC/abort and renewed only in their owning actor context.
Subscriptions bypass application e-order because an unreferenced wait can retire
before sending. Implicit source/forwarder death delivers workerd's AbortError
(io/external-pusher.c++:166–181); explicit source release remains non-aborting.
A missing local source is an error; it cannot represent remote subscription.
The three-node fixture verifies actual owner placement, deferred direct/forwarded
abort, Request.signal, exact structured reasons/one notification, already-aborted,
never-aborting and retained-across-events controls. Workerd runs the same program.
Ports 9700–9799, private MinIO; no operator fleet state.

The disabled-flag fixture requires DataCloneError on both runtimes. Stock workerd
2026-08-09 also logs an internal IoContext error and fails deferred abort delivery
in the enabled fixture (already-aborted and never-aborting controls pass). Those
actual failures are preserved: the workerd run exits 1, not a fabricated oracle
pass. Celld's expected.json tests the typed-trigger contract described by
api/basics.c++:789–890. This known oracle limitation is reported separately.

The fleet also SIGKILLs the forwarding node and the source, then checks the
receiving signal's exact AbortError. Export/pin cleanup is polled to a bounded
five-second deadline before faults; a fixed 300 ms snapshot was too early.

Actor abort/eviction releases retained receivers and revokes its typed source
and forwarding bridges before native termination. Reference release uses the
existing authenticated transport independently of the dying application driver
and its output gate; it cannot keep an application event alive. The same fleet
requires zero final native exports/pins after actor aborts, before node faults.
