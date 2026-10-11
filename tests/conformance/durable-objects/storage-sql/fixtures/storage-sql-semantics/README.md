# Newly authored ordinary DO storage and SQL workflows

D201–D220 are twenty new handcrafted executable regression candidates. All are
NOT_RUN and pending independent review. Source/static checks establish only
packaging and source identity. No runtime has been launched or attributed here.

The single-case frontend creates a random fresh Durable Object root and calls its
ordinary fetch once. Tests use real state.storage, state.storage.kv and
state.storage.sql. A delegating wrapper records native SQL cursor handles for
finite cleanup; it does not substitute storage behavior or expected values.

## Uniqueness audit

The restored T001–T032 wave concentrates on transaction queue ownership,
concurrent cached/native cursors, error rollback and pending writes. This wave
adds successful structured-clone ownership, rich storage values, async/sync
coherence, sparse get-many, list-bound intersections and reverse continuation,
materialized Map ownership, deletion counts, complete deleteAll/reinitialize,
SQL value conversion, duplicate-column raw projection, RETURNING receipts,
prepare coercion, and five public sql.ingest boundaries. No restored stress case
uses sql.ingest. Shared generic SQL/KV operations do not earn duplicate credit:
each manifest entry names the newly asserted mechanism and nearest baseline.

K201–K220 in the sibling wave address an env KV namespace (bytes/text/metadata,
null-hole bulk reads and cursor strings). These use an individual DO's arbitrary
structured-clone storage, sparse Map reads, range/reverse controls and SQLite.
No public KV namespace test has been copied here. RPC codec tests exercise a
transport boundary, rather than stored clone ownership or the native SQL seam.

D220 is an ordinary callback-chosen transaction rollback using valid complete SQL
and a local Error. It does not inject runtime faults, tamper with storage, use a
private control hook, or enter any previously excluded guarded-core path. D217 and
D218 contain fully valid quoted SQL and complete trigger definitions, never
partial or malformed statements. Source expectations are explained individually.

## Deferred execution contract

No celld binary/toolchain/dependencies/VM image is available in this environment.
These files do not launch, download or compile anything. A runtime result needs a
separately authorized and reviewed deployment supervisor.

That supervisor must copy this wave into a new owned staging directory and deploy
wrangler.jsonc with the exact rebuilt direct celld source. If bundling imports is
needed, use the approved trusted bundler and record its output hash. Follow the
recovered BUILD_AND_TEST.md and exact binary CLI help. Do not substitute workerd,
hybrid, Node execution, a mocked DO, or a test-script shortcut lacking real state.

Record executable SHA256, build/source manifest, boot/PID/start identity, fixture
hashes, compatibility date, fresh private store and loopback ingress. Correlate the
returned rootName, expectedObjectId/objectId and activation with actual runtime
ownership. These fixture labels are consistency checks, not a process witness.
All external calls are GET /case/<exact manifest ID>; each opens only one same-
deployment DO.fetch. No user or external service is contacted.

Bound to one external case request at a time, one owned runtime process/fleet
setup, 1 GiB RSS, a 10-second HTTP deadline, 15-second per-case owned-process
deadline and 360-second whole-wave deadline. The fixture has a 1-second precondition,
5-second trace and 2-second cleanup budget; its timers cannot interrupt wedged
native code. Require an external enforceable process deadline. An unsuitable
budget is BLOCKED for review, never silently lifted.

A valid observation needs HTTP 200, ASSERTIONS_SATISFIED, traceSettled true,
nonempty all-true assertion records, matching returned object identities and
cleanup.status COMPLETE. Failures are never reduced to PASS. An unsettled trace
must not race deleteAll: the fixture instead requests external owned teardown.
Cleanup exhausts each recorded cursor within 64 remaining rows, deletes only this
fresh test object's state, checks KV empty, and leaves final process/store reaping
to the supervisor. That supervisor must verify teardown before classifying any
real runtime execution. These are local direct-DO API tests, with no crash/restart,
fleet durability, performance, security, full-OS or cross-process guarantee.

## Static checks

Run `python3 validate_static.py`. It checks source hashes, all 20 manifest/function
pairs, finite declarations and JavaScript syntax only. It never executes the SUT.
A read-only aggregate checkpoint verifier will also verify accepted wave hashes.

Normative oracle corrections: D207 never combines start with startAfter in one
call, as required by the [storage list contract](https://developers.cloudflare.com/durable-objects/api/sqlite-storage-api/#list).
D214 treats RETURNING as an unordered result set, per [SQLite documentation](https://www.sqlite.org/lang_returning.html#limitations_and_caveats).
These are corrections within existing IDs, adding no test credit.
