# R5-05 — admitted call lifetime

A call admitted before disposal retains its target through asynchronous execution and result transfer. Covers immediate disposal, an already-running timer, a returned capability/pipelined call, failure and final parameter cleanup. Workerd `worker-rpc.c++:359–374,1168–1189,2155–2163` is the oracle.

The early-teardown defect was introduced after def239b (commit 2b45571). The round-4 head must fail on call execution. Def239b lacks final session cleanup and therefore fails the additional `disposed: 4` assertion; that is the inherited leak, not evidence that baseline had the new early-teardown defect.

Run via case.json and the regression contract environment. Fresh artifacts are retained.
