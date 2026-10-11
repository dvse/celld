# R7-03 — canceled JS continuations own late results

Workerd `api/worker-rpc.c++:1168–1200,1229–1231` retains a continuing
JS handler's call context, parameter group and result builder after cancellation.
The result stays in the canceled call's capability graph.

`case.json` starts two private nodes, MinIO and per-node TCP proxies. An unrelated
anchor retains a stateless source session throughout twelve single-call
cancellations. The source handler waits on a **local JS promise**: cancellation
cannot merely cancel a nested host operation and prevent the late continuation.
After the caller rejects, another call on the healthy anchor resolves the gate.
Late results cover a new child, readable/writable streams, a plain object's
root disposer, a rejection, and partial serialization failure. Disposal ledgers
must count each owned result once; legitimate `waitUntil` must run. Result-first
controls exercise ordinary delivery. The final native exports and pins must be
zero without killing either node. Baseline lacks one native diagnostic, which is
reported as unavailable rather than made into an artificial failing assertion.

The fixture uses ports base through base+9, all in 9700–9799, stores all artifacts,
and closes only its own processes. `python3 fleet.py` is the direct entry point.

The continuation must not retain the canceled target's export reference forever:
workerd's warning at :1184–1186 says the target (`this`) may already be destroyed.
Its continuation instead owns the call/result context and parameter disposal
group. `settlement.mjs` exercises 1,000 cancellation-first and 1,000 result-first
schedules. The existing R5-02 holder-death/70-second-call fixture also passes:
last-holder death releases a one-hour pending call's target and heap pin promptly.
An independent anchor or waitUntil keeps a healthy source context available for
late JS; dropping that context does not grant an abandoned continuation new I/O.
