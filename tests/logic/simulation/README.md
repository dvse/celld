# Deterministic coordination simulation

`simulation.rs` is compiled against the production `celld-logic` crate and the
preserved lease fixture helpers. Each seed drives CAS success with lost reply,
a racing CAS, stale/failed/missing readback, independently advanced wall and
monotonic clocks, timer/completion ordering, and a crash followed by late old
process completions. The run checks State structural invariants, no authority
after either prior expiry, no authority resurrection after crash, and eventual
fencing after quiescence. Quick uses 64 seeds; full uses 10,000, replayable by
setting `CELLD_SIM_SEEDS` on the emitted Rust test binary.

The broken-variant cases compile copies of real production logic. One removes
the prior-expiry guard; the other removes only its monotonic component. Both
must fail the same seeded safety assertion with a counterexample seed. Build
logs, mutated sources and exact diffs are retained. A failed compile, timeout,
unrelated panic or surviving mutation fails the checker test.

This is a bounded lease simulation, not the unpublished upstream complete
multi-cell simulator. Alarm liveness and full storage recovery are covered only
by the separately inventoried component/fleet cases, not by these seeds.
