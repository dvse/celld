# OR1-08 — structural invariants for changes 1 and 2 (Opus review 1, P2-8)

No runtime regression can distinguish `ported` from `ported-2` for structural
changes 1–2 on the paths fix-9 already repaired: both capture parameters at the
call site and both decode reusable props per receiver. The observable
differences the review found are covered by behavioural tests (OR1-05: client
held before serialization). This source test pins the structure itself so a
future per-path capture cannot return: fails on ported (`__admitRpcArgs`,
`preparedArgs`, raw-args dispatchers), passes on ported-2.
