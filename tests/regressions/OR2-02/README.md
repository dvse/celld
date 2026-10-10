# OR2-02 — closed heaps are never pinned or un-retired (Opus review 2, N-3/N-4)

N-3: `capability::export` pinned a heap even after its capabilities were
closed, so an export minted by a request still draining a generation-retired
or condemned heap kept the old generation from draining. N-4: `pin_export`
read `capabilities_closed` and cleared `retiring` in two steps; `retire_all`
could close in between and the heap ended closed but not retiring.

Fix (`pool.rs`): one per-slot `lifecycle` lock serializes `close_capabilities`
(used by `retire_all` and `condemn`) with `pin_export`; `pin_export` returns
`None` once closed; `export` also drops a pin if closing raced its insertion.
Native test: `cargo test -p celld --lib or2_02`.
