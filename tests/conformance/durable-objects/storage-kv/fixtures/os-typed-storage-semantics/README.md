# Actual pinned OS typed-storage component candidates

C201–C207 are seven source-only candidates. They import the real historical
Cloudflare OS typed-storage production module, byte-for-byte, and pass it the
actual DurableObjectState.storage object from the direct-celld runtime. No
production storage/index implementation is reproduced in these fixtures. No
mock, in-memory database or intercepted storage layer substitutes for the native
DO storage. Each case uses neutral, disposable application records.

Authored: 7. Independent body review: pending. Accepted primary credit: 0 until
review. Runtime executions: 0. Runtime passes: 0. Status: NOT_RUN. Syntax and
source-integrity results do not qualify runtime behavior.

## Production provenance and license

The module at vendor/cloudflare-os/packages/typed-storage/src/index.ts is the
exact 29,223-byte, 819-line original from cloudflare/cloudflare-os commit
4358072f8cb1bc9ddfb6ee11122e194c76cd71e0, SHA256
561111a1a0787d5158ddfa9df5c1910285b156906d874f5f58719a901e004c12.

Official source:
https://github.com/cloudflare/cloudflare-os/blob/4358072f8cb1bc9ddfb6ee11122e194c76cd71e0/packages/typed-storage/src/index.ts

The original Apache-2.0 license is preserved without modification in
vendor/cloudflare-os/LICENSE, SHA256
0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594.
The inspected pinned repository root has no NOTICE entry; this is not a
repo-wide claim about possible per-package notices. Original source comments
and notices are preserved. The original module has no runtime imports.

Source bytes and license were copied locally from the finalized source inventory;
this author made no new download. provenance.json records official URLs,
local provenance, unmodified status and missing future build inputs.
source-pins.json pins the OS module, application call-site evidence, license,
source-inventory records, guarded direct-celld storage source and overlap bodies.

The fixture and metadata files outside vendor are separately authored test
harness material, not modifications to Cloudflare OS. Future bundling must keep
vendor source immutable and write output only into a fresh reviewed staging
area, recording a new generated-bundle identity.

## Distinct mechanisms and independent oracles

- C201: the production nonunique index must buffer its outer native KV list before
  opening child lists. One combined case checks documented outer index-key
  limits, full-group results, first-encounter dedupe, reverse ordering and
  primary-key pagination within one group. Option permutations add no credit.
- C202: valid application uniqueness conflicts in the second unique index must
  roll back earlier index changes, preserve the full main/index/counter state,
  and permit a later successful replacement. Fixed literal native-keyspace
  oracles establish absence of partial writes and exact subsequent success.
- C203: scalar, array and null membership transitions must preserve intersections,
  delete obsolete memberships and last-member groups, restore nullable aliases,
  and allocate fresh nonunique group IDs. This matches actual OS mixed-return
  index declarations, rather than fabricated low-level SQL.
- C204: real unique/nonunique rebuild methods backfill records that predate index
  declaration, nest with a version stamp, sweep obsolete child entries on a
  second rebuild, preserve the persistent allocation counter, and support a
  coherent later edit. No writes occur through the obsolete schema.
- C205: real nonunique group deletion snapshots original primary keys before its
  built-in index subscribers and an ordinary read-and-audit callback open more
  native KV lists. Exact deletion counts, full survivor/audit records and all
  remaining secondary postings are checked. Callback timing is not an oracle.
- C206: documented deleteRecord semantics derive a computed primary key while
  ignoring stale non-key caller fields. Actual stored fields govern removal of
  unique/nonunique postings; a sibling revision remains intact.
- C207: sequential neutral schema-property renames use explicit storageName and
  storageKey while retaining original main/index/singleton locations. No old
  schema handle is used after the rename; concurrent alias semantics are not
  assumed.

The complete expected records, native index rows, monotonic allocation counters
and operation receipts are written as fixed literals in cases.js. No expected
result is calculated by importing the production module into a second model or
by rerunning an equivalent index implementation. Raw storage assertions are
specific to this pinned module representation; they do not claim a universal
Cloudflare storage format. Public method result oracles also check reconstructed
application records.

The overlap audit read T001–T032, D201–D220, T201–T215, accepted facet Z cases and
K201–K220. New candidates are actual production-module mechanisms over native
storage, not copies or renamed SQL workflows. closest_existing_cases and
per-case distinctness in manifest.json identify the nearest prior assertions.
C208 was proposed then retired before body authoring because undocumented
observer ordering would be a nonpromoting characterization. C209–C219 remain
unused. No quota was filled with extra CRUD cases or assertion permutations.

## Future trusted bundling and real-runtime deployment

Nothing in this delivery has imported, executed or compiled the downloaded
module, run a JS case, installed a dependency, built celld, or launched the SUT.
The current source-only authorization does not authorize those steps. The
following describes a future separately authorized workflow, not an instruction
to execute it now.

Use a reviewed, already trusted esbuild installation to bundle fixture.js as ESM
for a neutral worker platform with TypeScript syntax erasure. The entry imports
cases.js, which imports the immutable vendor TypeScript module. There are no
runtime dependency packages to fetch. Do not execute downloaded package scripts,
run a package manager, substitute a hand-ported module, or modify the vendor
source to obtain a build. Write the generated worker into fresh owned staging;
copy wrangler.jsonc there, adapting only main to the generated bundle filename.
Record the staging config, complete input hashes, bundler identity/version and
output bundle hash. Missing trusted build prerequisites remain BLOCKED.

Deploy with the exact rebuilt guarded direct-celld source from the immutable
baseline. Use its documented public configuration/deployment path and verified
binary CLI help. Do not substitute workerd, hybrid, Node execution, mocked DO
storage, internal harness test scripts or private fault/control APIs. The config
registers one SQLite-backed TypedStorageCase class under binding CASE.

An approved supervisor must independently record binary SHA256, guarded source
and build manifests, boot/PID/start identity, exact OS module/bundle/config
hashes, fresh private store, loopback ingress and actual runtime object ownership.
The fixture's objectId, expectedObjectId, random rootName and activation are
consistency labels, never independent process or full-OS witnesses.

For each exact GET /case/C201 through /case/C207, the frontend creates one random
new root and issues one same-deployment DO.fetch. Each root accepts one case per
activation. Cases execute finite synchronous operations in written dependency
order within that live request, with no external service calls, inter-request
schedule, crash/restart, fault injection or retained capability work.

Run at most one external case request at a time. The proposed envelope is one
owned runtime/fleet setup, 1 GiB aggregate RSS, at most 32 owned processes,
128 MiB of owned writable artifacts, and 10 seconds per external HTTP request,
15 seconds per case owned-process deadline and 120 seconds for this seven-case
wave. Supervise the entire proven-owned dev, trusted-bundler and runtime
descendant tree across process groups, preferably through one enforceable cgroup
and ownership domain. A single PGID or parent PID is insufficient for celld dev.
Generated bundles, staging configuration, logs, temporary files and the private
store must all live inside the owned quota domain; existing read-only binaries
and source inputs are not copied there. A future supervisor must prove complete
descendant termination and remove only these owned files on success, failure,
timeout or cancellation. Each case creates at most 32 physical native storage entries and fully
consumes at most 64 rows per read. Native operations cannot be interrupted by
JavaScript timers; the external process deadline must be enforceable. Missing
resource/process controls or inadequate bounds require review and BLOCKED,
never unannounced budget increases.

The wrapper checks fresh storage within one second, runs the trace with a
five-second timer, and allows two seconds for cleanup. It passes native storage
directly to the imported module. A completed result requires HTTP 200,
ASSERTIONS_SATISFIED, nonempty all-true assertion records, traceSettled true,
matching object identities and cleanup.status COMPLETE. All other outcomes
remain failures or typed blockers, never PASS.

Cleanup starts only after the trace settles. It opens one fresh public sync-KV
iterator and fully drains it, thereby replacing any abandoned native sync-list
cursor for that scope; storage.rs:3853–3862 explicitly closes earlier cursors.
It never calls next again after done. Then it calls deleteAll on only the new
owned DO and verifies native KV is empty. C205 unsubscribes in finally before
cleanup. If the trace did not settle or cleanup fails, only the supervisor's
owned-process/store teardown is appropriate. Independently verify whole-domain descendant and writable-artifact teardown
before accepting any eventual runtime classification.

These are actual OS-module component candidates. They establish no full OS
verification/run result, distributed behavior, fleet durability, restart,
security, performance or production-readiness claim. Earlier denied guarded-core
work, authentication, forgery, replay, malformed input, corruption, capability
lifetime and fault work are outside this fixture.

## Static checks only

python3 validate_static.py

The validator reads JSON and exact hashes, checks IDs/assertion sites/bounds/
imports/source references, parses authored Python, and runs only Node --check
on the two authored JavaScript files. Node does not resolve or execute imports
in that mode. The downloaded TypeScript is not imported, run, compiled or
syntax-transformed. static-report.json records these limited checks; SHA256SUMS
covers the delivered files. author_manifest.py regenerates only metadata inside
this wave and should not be used after the independent freeze without review.
