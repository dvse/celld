# R5-02 — holder-death capability ownership

Workerd's completion/revocation membrane (`api/worker-rpc.c++:2133–2163,2189–2222`)
and PR #6780's VatNetwork lifetime (`server/cluster-registry.c++:314–350,408–429`)
own remote references until release or connection loss. A heap pin alone cannot
identify a dead holder.

`case.json` runs `fleet.py` on the fleet host with `CELLD_BIN`, `CELLD_TEST_ARTIFACTS` (fresh),
and `CELLD_TEST_PORT_BASE=9760`. It requires the lane's local `bin/minio`, `bin/mc`
and npm esbuild; all state stays beneath the supplied artifact directory.
Only ports 9700–9799 are permitted by this lane's operator brief. The test stops
only its own processes and retains their databases and logs. No cloud is used.

The three-node fixture tests direct exports, forwarding, duplicated aliases,
an independent local holder, SIGKILL without disposal, cancellation of an active
call, exactly-once source disposal and a healthy 70-second call. Final native
export and heap-pin counts must reach zero. Baseline binaries lack count
instrumentation; that diagnostic is reported unavailable, not treated as proof.

Evidence (fleet host, 2026-10-10 AEST):
- `evidence/R5-02-fleet-baseline`: def239b, 11 pass / 6 fail. All six failures are
  missing holder-death disposal; the healthy call and surviving aliases work.
- `evidence/R5-02-fleet-counts`: patched, 18/18, including zero exports/pins.
  The final protocol-6 rerun is `evidence/R5-02-protocol6-final`.
- `evidence/native-round5-02-final.log`: 41/41 native tests, including packet
  delivery cancellation independent of source-buffer GC, adoption ownership,
  per-session reference accounting and authenticated peer separation.

The implementation authenticates incoming session establishment with the fleet
HMAC and records both process identities; the existing private-network boundary
still applies. A process session is never reconnected;
its EOF revokes only its own references. Imported handles keep the exact session
and never reconnect to a replacement. Forwarding creates an owned intermediary
export. Per-call ownership is canceled through a private native control path;
normal application calls have no fixed duration limit. Packets retain provisional
references across native queues and output gates. Their metadata is private to
the native serializer. Ambiguous RPC transport failures are not replayed.

Peer/tunnel protocol is now 6; mixed old/new peers are rejected. Deployment must
use a consistent protocol version. Persistent storage token encoding is unchanged.
The session transport is separate from per-call HTTP, not a full Cap'n Proto
VatNetwork port. A canceled send after its packet has been bound to a still-live
session can retain that packet's exports until the session ends; this test does
not claim prompt per-message cancellation in that window. Network partitions,
all decoder failures and HTTP AbortSignal permutations remain review targets.
