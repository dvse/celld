# R5-03 — facet snapshot and mutation order

Two source/descendant operations are already suspended when the root calls clone. They resume immediately after clone returns. The copy must contain both pre-call values. Also checks clone/get/abort/get, self-clone during an earlier clone, clone/delete, delete/clone, immediate chained clones and facet reload. Workerd `server.c++:752–793,941–985` snapshots the complete subtree synchronously.

Native SQLite access across loaded-facet isolates must participate in the snapshot cut. Root output proofs cover persistence separately from capture.

Run: `python3 run.py` with the shared regression environment. The HTTP matrix
uses both static facets and a loaded Worker's facet/descendant in another
isolate. The fault case removes write permission from its own destination
folder after initialization, then calls a clone whose handler immediately
returns: the reply must fail instead of acknowledging the failed mutation.
The permission fault is celld-only; the normal snapshot matrix is differential.

Three native tests exercise exclusion against a separate native writer, failed
proof retention/ordered predecessor failure, and abandoned-owner settlement.
Run with `cargo test -p celld --lib facet_snapshot::regression_tests`.
No filesystem fault is injected into workerd and no cross-node migration or
object-store failure is claimed by this case.
