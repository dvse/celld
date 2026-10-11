# Local fleet fault qualification

Full profile runs five scenarios on the fleet host with two separately supervised celld
processes, four cells, and three initial acknowledged writes per cell. Each
fault is followed by two more writes per cell and a complete ordered ledger
sweep through both nodes. Listener ports are 9800–9807.

The store is the checked-in, loopback-only S3 subset in `../lib/s3_store.py`, with
linearizable conditional writes, ranged reads, delimiter/paginated listing and
append-only tombstones. the `unit/store/` contract validates its contract. celld
also executes its own conditional-write and range probes before serving. No
production credentials are read or logged. This qualifies recovery against a
local S3-compatible test store; it does not qualify MinIO or real S3 latency.

- SIGKILL during a held chunked request, after its first 4096-byte write is
  witnessed. The killed owner's local DB directory is moved aside; the survivor
  restores from the bucket. Every previously acknowledged entry must return.
- SIGSTOP owner beyond lease expiry; survivor takes ownership and writes. On
  SIGCONT the stale process must fence and exit before its fresh replacement
  joins and passes the sweep.
- Return store-unavailable responses only to the owner; an expired owner must
  not acknowledge a fresh write, and the survivor must restore all prior acks.
- Return 429 on every store endpoint, attempt a write, require no unproven ack,
  and bound retries to 200 requests in the four-second two-node window. Restore
  the store and recover; this is a finite retry bound, not a throughput claim.
- Stop one owned node with SIGTERM; survivor and restarted process must preserve
  the ledger. Provider-level whole-host shutdown is explicitly not-applicable.

Each case retains configuration, expected/observed ledgers, fault events,
process logs, all store request metadata (without Authorization), and immutable
store versions. Failed runs are retained. Local DB removal is implemented by
moving it out of the process's data path, preserving evidence.

Browse process failure in `process-failure/`, stale-owner fencing in
`lease-fencing/`, and unavailable/throttled storage in `store-outages/`. Headers
select scenarios in the shared `../lib/fleet.py`; the ledger fixture has one
physical home under `process-failure/fixtures/ledger/`.
