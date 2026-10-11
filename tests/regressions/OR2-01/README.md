# OR2-01 — per-session lane index leaked one entry per export (review 2, N-1)

Fix round 1 indexed lanes by caller session so a closed session removes its
lanes without a full scan, but the index was pruned only on session close.
Peer sessions live for days, so every export ever called over one leaked an
index entry. `revoke` and `retain_live_exports` now call
`forget_session_lanes` for the departing export (`capability.rs`).

Native tests (included from `crates/celld/capability.rs`): 1,000 export →
ordered call → prune / revoke cycles over one long-lived session; the index
must end empty. `pruned_exports_leave_the_session_index` fails at 40c5664
(1,000 entries) and passes after. The revoke variant uses the new helper.
Run: `cargo test -p celld --lib session_lane_index_regressions`.
