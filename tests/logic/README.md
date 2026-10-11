# Decision-core behaviour

Native invariants are grouped by output gates, lease acquisition and continuity,
pressure, log recovery and wake recovery. Each case header specifies its exact
Rust filter and original trace/oracle. `simulation/` adds deterministic clock,
store and crash interleavings plus two compiled broken variants. `specification/`
records the missing upstream TLA models explicitly.
