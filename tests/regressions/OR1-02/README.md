# OR1-02 — export created while a retired heap drains (review 1, P1-2)

C6-01's first fix kept exporting heaps out of `retire`, but `retire` still
picks a heap with suspended requests, and those requests may export while it
drains. The heap then sat `retiring` and unfreeable for as long as the holder
lived — the C6-01 stranding at a lower rate (I/O-bound pools under steady load).

Fix: `Slot::pin_export` returns an ordinarily retired heap to service when a
draining request exports (generation retirement and condemnation close
capabilities first and are never reversed). workerd keeps an exporter's
IoContext until the holder's context ends while the Worker keeps serving
(api/worker-rpc.c++ ~JsRpcStub); celld now matches: a pinned heap serves,
collects its garbage (loaded workers, finalizers) and counts as live capacity.
Exports are released when their holder disposes them, its context ends, or its
capability session closes (`Session::close` → `release_local`).

Native test included in `crates/celld/pool.rs` `capability_drain_tests`:
`cargo test -p celld --lib or1_02`. Fails on ported-2 `d6cf644` (heap stays
retiring with live = 0), passes after.
