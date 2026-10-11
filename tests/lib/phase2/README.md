# Phase 2 qualification

`CAMPAIGN.json` and `provenance/` pin the additional reviewed designs and
unchanged source files. Behaviour case headers remain the discovery mechanism.
The 671 primary designs and 115 characterization designs are counted once.

The owned fleet-host root is `~/celld-tests-20261010/phase2`. `provision.py` builds
celld from exact git archives with Rust 1.98.1 and esbuild 0.28.2 from source
with Go 1.25.3. QEMU, mke2fs and dependencies use the checkpoint's official
Debian package hashes, completed from the official Release/Packages index by
`complete-sysroot.py`. SeaweedFS 4.48 uses its official release archive hash.
`verify-workerd.py` verifies npm's SHA-512 integrity before extracting stock
workerd 1.20261010.1. Candidate002 is restricted to historical VM gates.

`matrix.py` creates fresh column directories, verifies every crate byte
against its build receipt, and runs full profiles serially. Native/Rust tests
therefore use the same revision as each column's celld binary. Run records
include exact harness, source and binary hashes. Each column independently
runs stock workerd as its oracle. An older run remains intact on any retry.

`fleet.py` launches five real celld processes with one official SeaweedFS
server and five independently controllable S3 proxies. Ingress 9820–9824,
internal 9830–9834, proxies 9840–9844, store 9800–9807. Single-runtime adapters
use 9810–9813, private HTTP/WebSocket peer 9870. All use loopback addresses.
Sources and staged changes are hashed separately. Native ownership witnesses
include PID/start ticks/boot ID/executable hash and bucket owner epochs.
Stopping an owner reaps its actual process; a cold start uses a new empty
local data directory. Driver clocks and authored Date.now receipts are kept.
Store controls cover blocked writes, acknowledged-but-hidden writes, 429,
and severed connections. Source-authored recovery/deployment schedules and
assertions run unchanged through concrete driver methods.

`relocate-vm.py` creates separate reviewed VM copies, regenerates INPUTS.json
and writes all original/new hashes and diffs into RELOCATION.json. The
checkpoint originals are never edited. Two KVM guests consume 1+2 GiB.
Every VM attempt, including failed preflight and store shutdown attempts,
retains its raw disks and process evidence. Source columns substitute their
new build qualification; the candidate002 column retains its exact historical
binary pin. No new run inherits a historical PASS receipt.

`topology.py` stages global random identity creation in the first constructor
because stock workerd prohibits startup randomness. It also relocates the
private streaming origin and preserves the accepted R027 replacement. All
assertion bodies, finite trace shapes and original expected values remain
unchanged. Staging records explain and hash each adaptation. Stock workerd
uses separate Worker services for caller and recipient; it does not implement
celld's bucket leases or dead-owner epochs. Such native recovery schedules
receive concrete workerd N/A rows instead of a simulated pass.

`examples.py` adds finite protocols, including companion deployments, native
cron/queue/workflow scheduling, client cancellation, websocket frames,
placement witnesses, clone/restart and deployment rejection. Adapters stop
on a violated assertion and retain the observation. Conformance suite delivery
does not imply every runtime satisfies every original source contract.

`campaign.py` reports source-authored assertion outcomes separately for each
runtime and retains paired assertion comparisons. It does not normalize error
messages or remove failed cleanup assertions. Older `http` cases retain their
exact paired-diff policy. Recovery schedules native to celld have no stock
bucket-lease equivalent. KV/D1/R2/queue/workflow bindings likewise need service
backends absent from the official standalone workerd binary.

All raw state stays on the fleet host. The review export excludes credentials, storage
payloads, binaries, guest disks and generated dependency trees; it retains
hashes and remote locations for the omitted raw files. No deletion, push,
paid-cloud action or access to another lane's remote directories is required.

Two supplied entry modules export scalar metadata (`WAVE` and `PROFILE`),
which both runtimes reject as named Worker handlers. Staging adds a wrapper
that re-exports the original default handler and classes, leaving metadata
and all source assertions intact inside the original module. The changed
Wrangler main and wrapper hashes are recorded. This affects only atomic
accounting and capability-order. Earlier startup failures remain raw evidence;
qualification replaces them only after rerunning those complete groups.

`guard.py` independently samples Linux `/proc` every 50 ms and checks owned
PID/start ticks, resident memory, log size and outer deadlines. Limits are
1 GiB/16 MiB per runtime process, 768 MiB/32 MiB for SeaweedFS; 45 s for
historical superseded campaign cases, 90 s for topology cases, 240 s for durable recovery and 360 s for alarm/deployment cases,
and one hour per group. A breach kills only that owned process group and
invalidates every result sharing its group. Receipts record peak RSS/log
size, sampling gaps, violations and reap status. Topology/recovery/deployment use these polling limits. The final campaigns
use the stronger kernel domains and their exact source limits described below. The guard itself is checked with normal, RSS-breach
and deadline-breach child processes.

Interrupted full runs can resume only after matching the exact production
revision and each retained case contract. Every unaffected outcome, including failures,
is retained; explicit invalidation reruns cases or whole waves; new or changed cases execute. Resource supervision
was added after initial execution, so all runtime corpus waves were invalidated.
`configuration.json` and `resumption.json` retain the complete run lineage;
review exports include ancestor observations and source receipts. Older raw
results remain available and never inherit qualification from a later attempt.

Some unchanged fixture envelopes contain historical binary/profile labels.
Those literals are source provenance, not observations of the running build.
The column build receipt, immutable SOURCE-RECEIPT, runtime binary hash and
fleet `/proc/<pid>/exe` witnesses identify the actual source-built runtime.
Candidate002 is never selected by those fixture labels or by a primary runner.


Campaign qualification uses a delegated owned cgroup for all runtime/bundler/store
descendants, one CPU affinity plus CPU quota, kernel memory/swap/task bounds,
source-specific aggregate RSS/CPU/process/deadline checks, and an unprivileged
private tmpfs with the source's filesystem capacity. The controller runs as an
owned user service so it can attach children within the delegated subtree.
Before releasing the mount, every working file is retained and hash-verified;
this follows the operator's instruction to preserve state rather than the
source templates' deletion instructions. Process-count and RSS checks poll at
50ms; kernel task limits count threads separately (at least 128 tasks), while
source process ceilings are enforced over cgroup process membership. Generated
files, bundles, logs and private stores share the kernel filesystem quota.
Fresh-process git-codec cases each receive a separate domain and deployment.
The five-node fleet remains the transport/recovery/deployment implementation.

`build-pako.py` builds pako 3.0.2 at the official npm metadata's source commit
32be8f8e0ead1e6e8a74a1586a34f84734382d01 using our source-built esbuild. Published
package integrity, source-file hashes and built-module hashes are recorded;
no published precompiled pako distribution or external bundler is executed.


The stock oracle's Root/Cell fixtures bind `ROOT` back to the caller Worker
and `CELLS` to the recipient Worker in every service. This preserves the
coordinator state for recipient callbacks. Single-root resource fixtures also
keep their audit callback in that root's namespace. Other two-root fixtures
retain caller-to-owner routing. `oracle-routing.json` records every generated
binding and configuration hash; imported fixture bodies are unchanged.

Stock campaign configurations explicitly set `v8Flags = ["--max-heap-size=128"]`;
the official binary's successful startup and routing receipt retain that flag.
Celld uses `CELLD_V8_HEAP_LIMIT_MB=128`. External cgroup memory bounds also cover
native allocations, bundlers, store processes and their descendants.

Final publication is checked with `python3 tests/lib/verify-inventory.py --results`
and `python3 tests/lib/phase2/verify-results.py`. The latter verifies both complete
columns, source trees and binary receipts, case resource limits, retained working
file hashes, oracle binding/heap configuration, all exported raw-file hashes,
former N/A dispositions and the selected primary/historical VM receipts.
`PINS.json` keeps the qualified source trees separate from later branch observations.
The preferred branch for a future source refresh is `ported` when present.
