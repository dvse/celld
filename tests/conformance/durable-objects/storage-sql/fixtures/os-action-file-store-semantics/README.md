# Actual pinned OS ActionFileStore candidates

F201–F206 are six individually authored source-only cases against the original
Cloudflare OS ActionFileStore. Every module call receives the actual migrated
DurableObjectState.storage from direct celld. Native storage.kv,
transactionSync and WebCrypto are used without mocks, proxies, monkeypatches or
reimplemented ActionFileStore code. All test wrappers and oracles are outside
vendor. Only owned synthetic bytes are used; no user file, external API or SMTP
connection is involved.

Authored: 6. Independent review: pending. Accepted primary credit: 0 until the
separate independent review receipt. Runtime executions and passes: 0. Every
case is UNRUN / NOT_RUN. Static syntax/hash checks do not qualify runtime behavior.
F207–F212 were reserved and remain unused; this wave does not fill an ID quota.

## Exact production source and license

Official source commit: 4358072f8cb1bc9ddfb6ee11122e194c76cd71e0 in
https://github.com/cloudflare/cloudflare-os . Byte-for-byte vendor copies:

- action-files.ts: 10,338 bytes; SHA256
  e735cdd41333be3297a6e8d7114553483772b33f310edfb0844296650c855da0
- positive-int.ts: 763 bytes; SHA256
  e9813ec2bd5121a0384dc6bd4af4467ea6aa27f169e11ddc27673a88879bded1
- kv.ts: 1,201 bytes; SHA256
  2dd68d8822cb4737d8563da0595e250894d0f7f0b2ed2dc4b1505336a1f4ef9d
- Apache-2.0 LICENSE: 10,174 bytes; SHA256
  0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594

The original module and license were copied from the sealed historical inventory;
that inventory was not changed. Newly fetched exact-commit helpers and package
AGENTS.md were saved only here through GitHub's ordinary Download raw file control
in a separate dot-cloud browser tab. No shell/network download, package-manager
operation or downloaded-code execution occurred. provenance.json records exact
URLs, original completed download paths, byte counts and hashes. The import graph
is closed: action-files.ts imports positive-int.ts at runtime and kv.ts as a type;
neither helper imports another file. Original source comments/notices are intact.
The inspected package-root GitHub tree had no NOTICE entry; the sealed inventory
already records the inspected repository-root license. No repo-wide claim about
other package notices is made.

Read source root/package AGENTS, the baseline README/BUILD_AND_TEST and relevant
existing fixtures before authoring. Upstream test/build instructions are context;
current authorization permits source/static work only, so none was run.

## Mechanisms, oracles and overlap

- F201: offset byte view is passed to capture and its backing bytes are changed
  synchronously before the first await. Reference digest, actual stored chunk
  and public read must all retain the original five-byte view, excluding backing
  prefix/suffix. This exercises the production dual digest/chunk snapshot, not
  just standalone storage serialization or crypto key import.
- F202: one 2 MiB+17-byte input crosses two real 1 MiB boundaries. The exact native
  keys and lengths are 0000/1048576, 0001/1048576 and 0002/17. Every native chunk
  byte and every reassembled byte is compared to a literal region oracle; a
  separately precomputed digest and literal accounting complete the check.
  It checks complete publication after capture resolves, not isolation under a
  competing observer or crash durability.
- F203: an empty file has a genuine manifest and allocation despite zero chunks
  and zero charge. Empty digest/read and deletion are checked. It is the zero-
  iteration path through capture/read/delete, not another payload-size grid row.
- F204: repeated valid deletion of a four-byte capture releases its allocation
  once, leaves the three-byte peer's rows/bytes intact and retains counter 3.
  No generic CRUD return-value or duplicated capacity-reuse credit is claimed.
- F205: a live reference protects an old capture; an unreferenced capture exactly
  at the cutoff is removed; a genuinely younger unreferenced capture survives.
  Release of the live reference and subsequent cutoff advancement then remove
  the two survivors in order, with literal totals 9→6→4→0. This invokes actual
  production allocation buffering and per-file deletion, not a new SQL GC model.
- F206: two captures charge 7 of cap 8. A valid five-byte third payload is refused
  with the exact ordinary aggregate-limit error. Every earlier native key/value
  and both public reads survive unchanged. Deleting the first four-byte capture
  permits that same five-byte payload to succeed, leaving exactly3+5=8 bytes.

SHA256 expectations are fixed literals independently checked with Python hashlib
against explicit synthetic vectors. The fixture never asks the production module
or WebCrypto to generate its own expected digest. Complete small bytes and large
constant-region byte checks are literal. Dynamic UUIDs are only genuine handles
returned by capture. Dynamic allocation timestamps are bracketed by actual clock
reads; they are witnesses, not invented expected payload/accounting data. Native
storage keys are pinned representation-specific checks, not a general platform
format promise. Storage observations are read-only; every application write or
removal goes through the original module.

overlap-audit.json identifies the exact closest D/T/X/C/I bodies and source hashes.
The six cases differ by production transition, not names, size permutations,
assertion count, wrapper copies, or scheduling variations. Shared substrate,
publication checks and cleanup earn no additional case credit.

## Schedule and finite witness handling

Each exact GET /case/F201 through /case/F206 creates one fresh random-named owned
DO and issues one same-deployment public DO.fetch. Every module operation remains
inside that single live request and is awaited in written order. F201's only
intentional overlap is caller mutation before awaiting the real capture promise.
No stream, callback, retained capability, restart, fault injection, corrupted
storage, forged reference, malformed input, authentication or replay path appears.
The ordinary valid aggregate refusal is F206's only expected exception.

F205 reads genuine production-created allocation timestamps. Old captures may
share a millisecond; that is fine. It uses the old orphan's actual createdAt as
an inclusive cutoff, requires the protected capture's time to be no later, and
waits at most 32 times at 5 ms until Date.now exceeds the cutoff. After capturing
the young file it independently requires young.createdAt > cutoff. Missing
separation is BLOCKED_WITNESS, never a PASS or permission to change stored times,
replace Date.now, extend the wait budget or fabricate data. Allocation times are
also required to fall inside their genuine capture intervals. Timer delivery is
not a liveness/performance assertion; the external deadline is authoritative.

## Future trusted bundle and direct-celld deployment

The following is a deferred contract, not permission to execute. A separately
authorized trusted esbuild installation may bundle fixture.js as worker ESM with
TypeScript syntax erasure, using these immutable source/helper files. No runtime
package dependencies are needed. Do not run downloaded scripts, install packages,
rewrite vendor code or substitute a hand-port. Write only to new reviewed staging;
copy wrangler.jsonc there and adapt only main to the generated bundle filename.
Pin trusted bundler identity/version, every input, staged config and output bundle.
A missing trusted prerequisite is BLOCKED. This source delivery contains no bundle.

Run the exact rebuilt guarded direct-celld source from the immutable baseline,
using its documented configuration/deployment path and verified binary CLI help.
The config registers one SQLite-backed ActionFileCase class under CASE, with an
actual new_sqlite_classes migration. Workerd, Node execution, mock/in-memory KV,
internal runtime test modes and private control/fault APIs are not substitutes.

The future supervisor must independently establish binary SHA256, guarded source
and build manifests, boot/PID/start identity, exact OS module/helper/bundle/config
identities, private fresh store, loopback ingress, and actual object ownership.
Fixture-reported source hash, objectId, rootName, expectedObjectId and activation
are consistency labels only, never independent process identity or full-OS proof.

Run one case request at a time. The envelope is 1 GiB aggregate RSS, 32 owned processes,
128 MiB total writable owned artifacts, 10 seconds per outer HTTP request, 15 seconds
per owned-case process deadline and 120 seconds for the six-case wave. Enforce
limits over the entire proven-owned dev, trusted-bundler and runtime descendant
tree across process groups, preferably one cgroup and ownership domain. A parent
PID or single PGID does not establish celld dev cleanup. Include generated bundles,
staging config, logs, temporary files and private store in that same writable quota.
Existing read-only binaries/source inputs are not copied into that domain.

Per case: one created root, one external case request, one internal DO.fetch,
zero external-service calls, at most 16 native entries (actual maximum 10), at most
2,097,169 retained payload bytes, a 16 MiB visible-JS byte-view estimate, 64 rows
per fully consumed list, 64 native list calls, 256 native KV point operations,
16 native transactions, 12 public module calls, 8 WebCrypto digest calls and 32 small
clock waits. There are no streams. The large F202 bytes never enter JSON receipts.
Both wrapper layers cap the serialized receipt to 32 KiB. The source trace timer is
5 s, fresh-storage precondition 1 s and cleanup 2 s; these timers cannot preempt a native
synchronous operation, hence the required independently enforceable deadline.
The byte-view estimate covers four simultaneously explicit full payload views
(input, observed chunks, public read output, and a temporary full native list
result), totaling 8,388,676 bytes for F202, with headroom for internal read
assembly/list views. It is not an enforced total-memory cap or a claim about
native serialization/WebCrypto snapshots, hidden runtime copies, GC timing or
allocator retention; only the independent 1 GiB aggregate RSS ceiling bounds
the complete runtime domain. Missing or insufficient controls are BLOCKED,
never an unreviewed budget increase.

## Settled cleanup and qualification

All capture/read promises, including their real WebCrypto digest promises, are
awaited in the trace. The wrapper marks traceSettled only when the original trace
promise settles. An unsettled trace cannot race in-object cleanup; only the
supervisor may terminate the complete owned domain and remove its owned store.

After settlement, open and fully exhaust one fresh native sync-KV list to close
any abandoned previous scope cursor (pinned storage.rs:3853–3862); never call next
again after done. Then deleteAll only the new owned DO and verify an empty native
KV view. Cleanup failure or timeout is BLOCKED_CLEANUP. No unrelated storage,
source, build cache or process may be removed. Regardless of fixture outcome,
independently verify all proven-owned descendants terminate and all owned writable
artifacts/store are removed before assigning an eventual runtime classification.

An eventual runtime pass additionally requires HTTP 200, ASSERTIONS_SATISFIED,
nonempty all-true assertion receipts, traceSettled true, matching object identity,
cleanup COMPLETE, and all independent supervisor witnesses. HTTP 200 or a clean
syntax check alone cannot establish PASS. This component wave establishes no
full OS run, production readiness, security, restart durability or performance.

## Static validation only

python3 validate_static.py

This performs read-only JSON/schema/census/import/line-range/hash/bounds/independent
vector checks, parses authored Python and calls Node --check on only cases.js and
fixture.js. It never imports, runs or transforms any JS/TS, executes a case,
compiles a dependency, builds celld, opens a service or downloads over the shell.
static-report.json records those limited results. SHA256SUMS pins every delivered
file except itself. author_manifest.py regenerates metadata only before review;
accepted files must not be changed or regenerated without renewed review.
