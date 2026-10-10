# OR1-01 — same-process ordered call ends before the callee guard (Opus review 1, P1-1)

`call_ordered`/`fetch_ordered` disarmed the caller's skip guard for every
same-process route before dispatch. The node's dispatch (`dispatch_capability`)
can then end the call in preflight, actor routing (`app.request`) or actor
admission (`local_request().run()`) before `invoke_local` builds its
`OrderSlot`. The slot stayed unresolved; the next call on the lane waited the
60 s gap timeout and broke the lane — the C6-02 shape on a path C6-02 does not
exercise.

Fix: a same-process call keeps its `CallerOrderSlot` armed until the call
ends; `skip_order` is a no-op for a slot the callee dispatched or skipped.

Native tests (included from `crates/celld/capability.rs`): a call dropped while
dispatch waits and a call refused by dispatch (`native.rs`, RPC feature), and a
fetch refused before `invoke_local_fetch` (`native_http.rs`, included by the
Fetcher HTTP feature that defines `fetch_ordered`, so every patch builds).
Each asserts the next sequence admits within 2 s.
Run: `cargo test -p celld --lib same_process`.
Against ported-2 `d6cf644` (with the test hook applied) all three fail: the next
call waits for the 60 s gap.
