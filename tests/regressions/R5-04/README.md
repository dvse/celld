# R5-04 — restored HTTP channels

Workerd restore.c++:74–89 preserves HTTP independently from RPC. Service, DO, facet and dynamic Worker Fetchers are used directly, passed over RPC, stored/reloaded, and called through streaming POSTs and WebSocket upgrades. HTTP handlers call ctx.restore to check the restored-self context; an ordinary RpcTarget.fetch method remains an RPC control.

Run the ordinary case through `case.json`. For the peer path, run `fleet.py` with
`CELLD_BIN`, `CELLD_TEST_ARTIFACTS` (a fresh directory) and
`CELLD_TEST_PORT_BASE=9740` on the fleet host; it uses the lane's local MinIO and three nodes.
All artifacts and state remain in that directory after its own processes stop.

Evidence on the fleet host, 2026-10-10 19:06 AEST:
- `evidence/verify-20261010T090641`: def239b fails; patched and stock workerd pass.
- `evidence/R5-04-fleet-fixed-0858`: 3/3 exact matrices pass, 20 peer HTTP calls.
- `evidence/native-round5-04.log`: 37/37 library tests pass.

The matrix checks streamed body content and upgrades; it does not establish
all AbortSignal or HTTP disconnect/cancellation lifetime semantics. Restored
HTTP is a separate authenticated subrequest channel, not permission to invoke
an entrypoint's reserved `fetch` member through RPC. A failed peer HTTP request
is not automatically replayed.
