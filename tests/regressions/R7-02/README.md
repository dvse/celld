# R7-02 — logical RPC parameters survive safe routing retries

Workerd `api/worker-rpc.c++:359–429` owns arguments for the logical invocation;
PR #6780 `server/server.c++:2001–2068` resolves the promised target before use.
Celld now owns a logical packet until completion and forks independently retained
wire references for each dispatch attempt. Dropping or adopting one attempt never
consumes the logical packet or a different attempt. There is no replay on an
ambiguous execution result and no new remotely callable retention operation.

`case.json` runs three private nodes. A proxy gates the argument-bearing
request after A selected owner B. Celld's own ordinary eviction plus automatic
rebalance performs close, durability proof, release CAS and signed successor
handoff. Ownership counts/weights make the successor remote C.
Only after the actual successor is recorded does the proxy deliver the old
request to B. B's genuine stale-owner response triggers the retry. The callback,
readable stream, writable stream and mixed graph must work; the receiver ledger
must show exactly one execution and the callback must be disposed once. Artifacts
retain the handoff and NotOwner trace, gate events, outcome and ledgers.

`attempts.rs` is included by the native packet test module. It runs 1,000 schedules
with multiple independent attempts, first-attempt adoption, a dropped
pre-dispatch attempt, local retry and logical-call cancellation. The native
reference increment happens under the exporting isolate's validated turn; a
Rust guard owns each increment immediately, including cancellation during turn
completion. The fleet uses real callback/stream references; the packet unit's
empty route table isolates packet identity and state transitions.

Baseline qualification: `def239b` has no one-shot native packet layer and passes
this retry. The reviewed `93e39f0` fails with "RPC packet already transferred";
the corrected runtime passes. An honest regression for this newly introduced
bug cannot be made to fail on def239b. Local packet adoption after an abandoned
attempt is covered by `attempts.rs`, not claimed as a successful fleet handoff
to the calling node. That diagnostic is retained in remote evidence: the caller
with an outstanding route was not the selected successor; counting its failed
setup as a baseline defect would be incorrect. The prior R6-04 transport-failure
matrix separately checks request/tunnel failure and ambiguous delivered replies.
