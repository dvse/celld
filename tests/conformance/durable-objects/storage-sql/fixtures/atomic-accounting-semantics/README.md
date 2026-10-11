# Atomic application-accounting compositions

T201–T215 are fifteen individually authored ordinary functional candidates. All
remain NOT_RUN, with zero runtime executions and zero runtime passes. No celld
binary, build, dependency download, SUT launch, VM or mock execution occurred.
The earlier target of 18–22 was deliberately reduced to avoid counting arithmetic
or domain-name variants as distinct mechanisms.

These are synthetic OS-relevant platform compositions. The OS checkout is absent.
Historical source-pins from both restored sqlite-concurrency and alarm-event-stress
waves retain the same SHA256 for typed-storage/index.ts (transactions and indexed
collections) and gatekeeper-kit/action-files.ts (atomic allocation/chunk/accounting).
Those files were not reread. Retained provenance motivates relevance; it is not
proof these fixtures execute OS callsites or reproduce current OS algorithms.

## Distinct candidate mechanisms

- T201: conditional UPDATE RETURNING controls quota admission plus document/index
- T202: UPSERT insert/conflict-update paths share payload bytes and count references
- T203: native triggers maintain both sides of folder moves and later deletion
- T204: foreign-key update and delete cascades maintain composite chunk ownership
- T205: valid deferred cyclic head/revision integrity through successful savepoints
- T206: partial unique index selects the active identity among archived same-slug rows
- T207: bounded KV prefix partitions transfer into SQL with disjoint byte conservation
- T208: bounded recursive ancestry materialization and subtree rollups
- T209: window-partitioned retention preserves pins and current revision pointers
- T210: overlapping byte writes span BLOB chunk boundaries without allocation growth
- T211: native LAG boundary query detects a sparse extent hole and its removal on fill
- T212: native range deletion and BLOB truncation followed by clipped-chunk append
- T213: contiguous chunk-set admission publishes a manifest and transfers its charge
- T214: generated UTF-8 byte lengths, virtual character lengths and index maintenance
- T215: FTS5 posting mutation reconciles with document/count/byte state

The full overlap audit names nearest cases. All T001–T032 and D201–D220 bodies were
read. The pre-entered two-request queue uses baseline T031 as scaffolding and earns
no new credit itself. Generic allocation, quota, transfer, tag and rollback variants
were consolidated or omitted. Candidate-specific SQL/storage compositions, fixed
state oracles and different native mechanisms are the uniqueness basis. Repeated
left/right operations, assertion counts, supporting controls and reruns add no IDs.

## Executable fixture and ordinary-request schedule

Deploy wrangler.jsonc with fixture.js and cases.js only on the exact rebuilt direct
celld runtime. Bundling, if required by the supported deployment path, must use an
approved trusted tool and record its output hash. Follow the recovered
BUILD_AND_TEST.md and the actual executable CLI help; this package neither launches
nor guesses a new runtime/deployment command. No substitute workerd/hybrid/Node
storage, mock database, standalone SQLite evaluation or test-script shortcut earns
credit. All case reads and mutations go to actual state.storage and native SQLite.
The helper wrapper only counts calls, drains real cursor rows and compares literals.

One external GET /case/T201 (or another exact manifest ID) creates a fresh randomly
named root. Setup is a separate completed DO.fetch. The frontend then issues two
real DO.fetch requests before awaiting either. Both enter a local Promise admission
barrier before the left transaction begins. The left case pauses at its explicit
mutation checkpoint. The already-entered right request issues its transaction,
records right-queued and releases the left wait. The right callback must enter
only after left-release and left body completion. No timer serves as evidence of
overlap; timers only bound missing gates. A separate finish request checks the
literal event order, fixed data oracles and cleanup after both handlers settle.

This intentionally requires two distinct incoming request contexts in one stable
DO activation. It neither claims nor needs multi-process placement, migration,
lease draining or faults. No internal runtime hook, hidden state control, retained
stateless capability or private storage mutation is used. No forced SQL errors,
malformed input, rejected constraint commit or application rollback is attempted.
T201 capacity exhaustion and T206 UPSERT are ordinary non-error outcomes. T205
explicitly witnesses foreign_keys=1, temporarily changes a deferred head inside a
valid transaction, then resolves it before successful commit.

## Fixed oracles and source identity

manifest.json links each literal oracle and case-body assertion count to inspected
JS/native source ranges. source-pins.json pins those exact recovered files and
retained OS evidence. Native SQL is forwarded through SQLite prepare/bind/step;
SQLite's official contracts support the relational features, not a special celld
implementation of these application algorithms. The referenced docs were checked
during authoring. Assertions are fixed in cases.js, never learned from the SUT or
computed by replaying a reference storage implementation. Helper reconstructions
read real rows and are compared with literal byte arrays, row sets and counters.
RETURNING order is never assumed for a multi-row result; every asserted RETURNING
receipt here has at most one row.

Generated arithmetic is not an oracle: each expected document set, membership,
revision, counter, byte sequence and intermediate receipt was derived by hand.
Cross-checks include explicit counts/sums and exact full state where meaningful.
The readChunks zero filling and overwrite chunk splitting in T210–T212 are
fixture-authored application algorithms, not native celld features. Their helper
assertions alone earn no coverage credit. Those candidates exercise actual BLOB
extent persistence/replacement/clipping with coherent KV accounting across
admitted transactions; T211’s distinctness is specifically sparse physical
extent allocation with a native LAG predecessor-end gap query returning exactly
[2,8] before fill and no gap after fill, plus logical-versus-stored byte accounting.
No performance, filesystem size, durability across restart, full-OS integration,
cluster recovery or production security guarantee is claimed.

## Required independent execution evidence and bounds

A later authorized supervisor must copy the fixture into a new owned staging
area, verify source and fixture pins and record direct executable SHA256/build
identity, PID/start identity, deployment binding/config hash, fresh private store,
loopback ingress, and actual DO owner/root correlation. Returned UUIDs are useful
correlation labels, not proof of direct execution or placement. Record all raw
responses and enforced limits without changing the oracle after observing output.

schedule.json is the exact placement, gate, acceptance and cleanup contract.
Run one external case at a time. There is one new root, four internal DO.fetch calls,
and at most two simultaneous operation handlers per case. Gate deadlines are
1.5 seconds; setup/cohort/finish limits are 2/6/3 seconds. Enforce an independent
12-second HTTP, 15-second owned-process per-case and 240-second whole-wave deadline,
plus 1 GiB RSS. A budget mismatch is BLOCKED for review, not permission to enlarge
limits. Native execution may wedge despite JS timers, so external limits are
mandatory. No public outbound requests or retries occur in case execution.

Both actor handlers and transaction promises must settle before data cleanup;
otherwise return EXTERNAL_REAP_REQUIRED. Cursors are immediately drained within64
rows and finally checked again. deleteAll touches only this fresh owned root;
verify KV and application SQL empty. The supervisor must reap its owned process
and store and verify teardown before assigning any runtime result. A failed
assertion, API error, missing schedule/identity witness, timeout, cleanup failure
or unverified environment cannot pass. This wave has not performed any of those
future runtime checks.

## Static-only validation

python3 validate_static.py verifies pinned source, retained-provenance shape,
case/manifest matching, schedule declarations, literal assertion counts, deployment
binding and JavaScript syntax. It never imports/runs cases, executes SQL, contacts a
runtime, builds or downloads anything. static-validation.json records that narrow
check only. Separate review receipts determine accepted case credit; the author's
metadata does not self-award independent review or runtime status.
