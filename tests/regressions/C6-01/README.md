# C6-01 — planet memory growth: export-pinned isolates stranded in `retiring`

Tunez Celld 6: planet-2 RSS 1.5 GB (16:57 AEST) → 20.7 GB (23:00), no
restart. Read-only `/state` of the running node at 00:29 AEST 11 Oct: 646
stateless isolates `retiring` with `requests=0, turns=0, cells=0`
(hb-workshop 257 holding 8.9 GB of V8 heap, hb-gadget-materializer 350 with
1.4 GB heap + 573 MB external, identity/gateway/publication/kernel 39);
2,085 "isolate retiring" vs 1,438 "isolate freed" log lines. The only
remaining condition that keeps a drained retiring isolate is
`export_pins > 0`: an actor (the Overseer) still held capabilities those
isolates exported. hb-workshop also hit "too many loaded workers (limit 255)"
at 17:01:26 — Worker Loader children owned by stranded heaps, whose
finalizers never run because a retiring heap runs no JS again.

Mechanism: the reaper retires the least-loaded *live* isolate, ignoring
exports. A pinned isolate marked retiring takes no new work and is never
freed while the holder lives (an actor context that never ends), and a fresh
isolate replaces it. Each idle reap therefore strands one more whole heap
(35 MB per hb-workshop heap) for every heap that exported a held capability.

workerd: an undisposed stub keeps the exporter's IoContext until the
holder's IoContext ends (api/worker-rpc.c++ ~JsRpcStub defers to the
context; GC is deliberately not observable), but the Worker's single isolate
keeps serving: no heap is ever stranded. Fix: `celld_logic::isolate::retire`
treats live exports like housed cells — never a candidate — and `may_free`
checks the same count; `/state` reports `exports` per pool.

Workload: 2 nodes; ingress requests make 200 cross-node actor calls each,
the actor calls a separate stateless service script, every request opens one
session the actor holds forever, and 20 cross-node leases are exported and
disposed (session churn). 20 s busy / 125 s idle cycles.
Before (`ported`): retiring 3 → 6, services heap 46 → 93 MB, owner RSS 172 →
244 MB after two cycles, growing linearly. After: retiring 0, heap ~50 MB.
