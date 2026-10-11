# R4-05 — OPEN: restored HTTP channel

A restored static service Fetcher crosses RPC and performs an HTTP POST,
retaining status, headers and body. Workerd restore.c++:74–89 preserves the
Fetcher channel kind. Current celld wraps it as a generic RpcStub and rejects
the reserved fetch member. This remains expected-fail: R4-05.

The case is a minimal positive reference control, not comprehensive coverage
of the remaining work: facets, Worker Loader channels, restored-self context,
streaming, WebSocket upgrades and storage/restart all require the typed HTTP
channel path too. No RPC-member visibility restriction should be loosened.
