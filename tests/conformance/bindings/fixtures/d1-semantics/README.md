# Newly authored ordinary public D1 cases

E201–E220 are 20 assertion-bearing source-contract candidates for the exact
restored direct celld source. They are newly authored, unreviewed and not run.
Static integrity checks are not runtime passes or accepted distinct-case credit.

## Files

- `worker.js`: dependency-free Workers ES module, with 20 handcrafted case bodies.
- `wrangler.jsonc`: minimal module configuration with the six bindings needed to
  exercise three physical database identities and their explicit/name aliases.
- `manifest.json`: intent, application relevance, fixed trace, exact assertions,
  source ranges/hashes, distinctness, ownership, limits and cleanup for each case.
- `source-pins.json`: immutable source and inspected corpus hashes.
- `overlap-audit.json`: actual available-corpus search and nearest-case analysis.
- `author_manifest.py`: deterministic source-only metadata generation.
- `validate_static.py` / `static-validation.json`: syntax/metadata/pin checks only.
- `SHA256SUMS`: all artifact hashes except its own, which would be self-referential.

## Scope and source oracle

Only public D1 binding APIs are exercised. The implementation is in production
`harness.js` and `storage.rs`, reached through production deployment/bootstrap
binding construction. There is no services/d1.js. The fixture contains no custom
Durable Object, direct DO storage, SQL cursor, ingest, operator endpoint or private
hook. It does not import a substitute, extract/evaluate the source implementation,
or model D1 with Node/SQLite/Map.

All oracles are PINNED_DIRECT_CELLD_SOURCE_CONTRACT. In particular:

- Read-only `changes` and `last_row_id` reset to zero, even after prior writes.
- Service markers are `celld`, `local`, and primary=true.
- Session queries and batches advance bookmarks to the stable `celld:primary`.
- exec counts SQLite statements rather than source lines.
- database_id is the identity; absent IDs fall back to database_name.

These are not universal Cloudflare claims. No runtime comparison was performed.
Every row-order assertion uses ORDER BY; E216 accepts any valid first RETURNING
row and separately verifies all effects. E204 follows typed-array element-to-byte
conversion and only claims bind-time copying for ArrayBuffer/typed arrays. It
makes no snapshot claim for the plain byte-array input.

Successful batches prove their ordered dependencies, result association and
post-return commit completeness in these traces. They do not prove rollback,
concurrent-observer atomicity, durability across loss, replicas or any restart.
Explicit application transactions, malformed input, forced failures, auth/replay,
fault seams, retained capabilities and guarded G/N/P/J122 paths are excluded.

## Required future execution envelope

No runtime adapter or launch/build was executed in authoring. A separately
reviewed direct-celld adapter must provision and independently enforce all of
these conditions before any runtime case credit can be awarded:

1. Use a fresh, isolated, disposable test store with no user data. Keep fixture
   IDs confined to that store. Deploy the complete hashed Worker/config against
   the pinned direct source. Run serially with no other request or writer. The
   six configured bindings address three physical identities. E219 owns the same
   deterministic table name separately in two identities; E220 owns it only once
   despite three aliases. Do not mutate identity names without a recorded config
   adaptation and corresponding oracle review.
2. Record source/deployment/config and actual executable hashes, direct target
   provenance, owned process-group IDs/PIDs, invocation, origin and disposable
   state-directory identity. The Worker cannot attest to its own runtime. Missing
   bindings, deployment or resource/provenance witnesses mean BLOCKED. The Worker
   returns BLOCKED for absent bindings before claiming table ownership; genuine
   API exceptions and assertion mismatches remain FAIL.
3. Invoke exactly one GET `/case/E201` through `/case/E220` per case. No all-cases
   route, auto-retry, body-driven SQL, query parameters or generalized execution
   route exists. Each successful case performs 2–6 sequential main-phase binding
   dispatches, one preflight read per owned table, then two cleanup calls per
   table. The Worker enforces a separate 32-dispatch cap for each phase. Synchronous
   prepare/bind/session/bookmark operations are recorded in the finite trace but
   are not dispatched binding calls.
4. Before launching, enforce a strict 30-second total deadline per case request,
   including cleanup; a 700-second whole-wave deadline; 300 CPU seconds and 2 GiB
   aggregate RSS for the adapter-owned wave process group; 256 MiB maximum owned
   disposable-state disk use; and at most 1 MiB captured response per case. These
   are safety bounds, not performance goals. Unsupported enforcement means BLOCKED.
   Per-case data is tiny: at most four rows per table, two tables, five binds per
   statement, five batch statements, four exec statements, 1 KiB SQL per dispatch
   and 64-byte scalar/BLOB values. There is no open-ended polling or generation.
5. A runtime PASS requires HTTP 200, matching id, status PASS, the exact assertion
   labels/count and per-phase dispatch counts from manifest.json, cleanup.verified
   true, and valid external provenance and limit evidence. Non-PASS, a mismatch,
   truncation, malformed response or missing evidence cannot count as a pass.
   A 30-second stall is TIMEOUT, with cleanup unverified. No internal Promise.race
   pretends to cancel an in-flight SQL mutation.
6. Preflight checks exact sqlite_schema names and refuses pre-existing objects
   before claiming them. Finally attempts DROP TABLE IF EXISTS on each claimed
   name independently, then requires the exact schema lookup to return null. A
   failure still runs finally; a stall may prevent finally from completing. The
   adapter must stop only its owned request and, when request cancellation cannot
   be proved, its owned celld process group, preserve bounded evidence, then
   discard only its disposable store. Never kill unrelated processes or use a
   shared store. Never report successful logical cleanup after a timeout.
7. At wave end, stop the owned celld group and discard its isolated store even if
   every logical table-cleanup assertion passed. A subsequent independent run
   must start from a fresh store. This is ordinary owned-resource teardown, not a
   restart or crash-recovery test, and adds no authored-case credit.

Source-only packaging intentionally leaves these prerequisites explicit. A future
adapter must not launch a shared service or merely impose an HTTP client timeout
while letting an owned stalled SUT continue running.

## Overlap and static validation

The audit read actual preserved SQLite-concurrency case bodies. T011/T015/T018/T024
are direct DO cached cursor/transaction-view/schema behaviors; they are not public
D1 cases. T012/T013/T019/T020/T021 are also considered. A case is not new merely
because its old SQL was spelled using another API: each new candidate targets a
binding-specific codec, result shape, metadata, session, parser or configuration
identity contract. The available 319 text files in stress corpus and project tests
contain no D1/withSession/getBookmark text matches. Private or omitted tests may
exist. The current storage-sql-semantics wave was also read: D212/D213/D214 and
D216/D217/D219 are explicitly compared with the nearest E cases in the manifest
and overlap audit, including the close D213/E209 duplicate-column contract.
Different public APIs alone do not establish distinctness; independent review
must decide the additional implementation-path credit. The source guestbook example was read; it is not an assertion-bearing test.

Run `python3 validate_static.py` for module syntax, manifest/slice/source-pin and
finite-trace metadata checks. It never evaluates the Worker, executes SQL, launches
or builds a SUT, downloads dependencies or awards runtime credit. After a deliberate
artifact edit, regenerate metadata as needed, rerun static checks, and regenerate
SHA256SUMS before independent review. Source references remain pinned.
