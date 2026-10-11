# Direct celld stream backpressure and admission candidates

Six handwritten ordinary API cases, S301–S306, with 84 fixed assertions. Each is
entered once by GET /case/<id> on the actual deployed Worker. The fixture uses
real ReadableStream, WritableStream, TransformStream and ByteLengthQueuingStrategy
globals; no copied implementation, reference runtime or mock is substituted.

## Status and distinctness

All cases are UNRUN / NOT_RUN. Runtime executions: zero. No build, dependency
installation, download, SUT launch or JavaScript import/execution was performed.
Node --check provides syntax evidence only. The manifest grants zero reviewed
credit; only a separate independent review receipt can accept these candidates.

- S301: weighted ready-promise identity and distinct pressure epochs, including
  readiness with the second callback still held
- S302: successful asynchronous sink initialization independently gates callback
  admission even though initial writer readiness has fulfilled
- S303: queued close resolves an existing pressure-ready epoch before the held
  write completes, without prematurely completing close or closed
- S304: readable HWM0 demand gates each ordinary transform/write after start
- S305: successful asynchronous flush owns a fixed final tail and terminal EOF
- S306: weighted readable queue capacity controls source pull/refill admission

S304 and S306 are EXPECTED_FAILURE_CANDIDATE from source inspection only. Their
normal intended API contracts remain the pass oracles. The source currently
appears to omit transform read-demand coupling, and to calculate ordinary pull
admission from queue length rather than weighted size. No runtime failure has
been observed. A future changed implementation must still satisfy the same
oracles; this package does not bless the current behavior.

The audit covers 126 baseline and accepted stream-related entries, plus the
original distributed-stream fixture's coarse pressure and prefetch checks.
Per-case overlap deltas are in manifest.json and overlap-audit.json. S020's FIFO
write-before-close, S024/X012 writer handoff, S206's held pipe close, and X015's
delayed native output consumption receive no new credit. Terminal bytes, stable
EOF and cleanup support these six mechanisms; they are not extra cases. This
is not an HWM, payload-length or chunk-shape parameter expansion.

## Oracles, gates and cleanup

The primary [WHATWG commit snapshot](https://streams.spec.whatwg.org/commit-snapshots/b9ba9f49d95b4280be0dc2372377a006c3a91c18/)
was read independently of celld source. normative-verification.json identifies
checked algorithms; manifest.json provides per-case locators and source ranges.
The source audit's original spec locators alone were not treated as verification.

All callbacks and returned API promises are observed immediately. Gates prevent
completion; zero-delay task fences let already-enabled promise jobs settle and
are never latency measurements or substitutes for entry/settlement evidence.
S304 joins the actual start result before its no-demand experiment. S305 issues
the prefix read before its write is awaited, allowing a correct HWM0 transform
to progress. S306 joins the exact promise returned by the first pull, then uses
a task fence before observing no refill; a still-active pull cannot fake success.
The second pull is held independently and the producer emits at most two chunks.

On every returned trace, cleanup opens all gates, initiates cancellation of each
live readable and abortion of each live writable before joining, joins every
original API, ready/closed and callback promise (including observations added
during settlement), and only then releases any remaining owners. Readable
cancellation unblocks a missing HWM0 read. Post-release promise getters are also
observed. Successful traces have already closed normally, so cleanup does not
invoke cancellation callbacks on those closed streams. Deep assertions preserve
undefined-valued EOF fields and ignore object key ordering.

A runtime defect can strand an API or cleanup promise. No in-isolate timeout
converts that into success: the independent external five-second request deadline
must record failure and terminate the owned descendant domain if needed. COMPLETE local
cleanup means local settlement, not independently verified process teardown.
The response records zero locks, pending observations and timers, plus each
terminal promise and gate. Final acceptance also requires external teardown.

## OS relevance and provenance

The immutable baseline contains no OS checkout. A separately recovered historical
raw blueprint-archive.ts was reread and its SHA-256 verified against the preserved
pin: 3169045728d1eb6a9de86afa08b1eddf8c14766affda28e8e95f1d01a2a846c1.
At lines 145–162, buildBlueprintArchiveStream constructs an ordinary
TransformStream, pipes a prefix with preventClose, then pipes archive content.
source-pins.json pins that exact raw file under campaign_evidence, without
pinning the still-growing recovery inventory. This is supporting source
relevance. It does not assert that this caller uses custom queue weights or a
user flush callback, and it creates no extra pipe or handoff cases. Other listed
historical OS records remain metadata-only. The full checkout/dependencies and
any actual OS workflow, runtime result or distributed placement are not claimed.

## Future direct-celld execution contract

This is a future-run specification, not an executed launcher or permission to run.

1. Supply a separately reviewed direct-celld binary built from the complete guarded
   source pin and a trusted installed esbuild. Historical unguarded binaries are
   not qualification evidence. Verify source-pins.json and SHA256SUMS first.
2. Copy cases.js, fixture.js and wrangler.json to a fresh supervisor-owned run
   directory. Never run from the immutable baseline or author folder. No dotenv,
   bindings, shared store, credentials, outgoing host or production data is needed.
3. Record complete guarded-source, binary/build and esbuild digests; deployed
   fixture/config digests; fresh store; actual listener; supervisor/child PIDs and
   a proven-owned whole-descendant execution domain, such as an already
   provisioned cgroup. It must cover dev, every bundler and the runtime node,
   including descendants that create separate process groups. All temporary
   bundles, logs and stores must remain within the same owned filesystem quota
   and cleanup domain. In the future reviewed Linux environment, set TMPDIR to
   an existing fresh RUN_DIR/tmp inside that quota before deployment and direct
   logs there; deploy.rs:2882 uses a temporary directory for bundler output.
   Verify effective paths rather than assuming containment from the working
   directory alone. No privileged provisioning is performed by this package.
4. The pinned source's documented command is:

       CELLD dev RUN_DIR/wrangler.json --host 127.0.0.1 --port PORT --no-watch

   Substitute only the reviewed binary, fresh run directory and reserved loopback
   port. The command performs a real deployment and starts a real celld node with
   its own store. Observe startup directly within 90 seconds. A case is not a
   health probe, and missing prerequisites are BLOCKED before trace entry.
5. Send schedule.json's six GET requests serially, once each, without request body,
   query, authentication header or retry. Enforce five seconds and 64 KiB maximum
   response per request. Requests are to the recorded local listener only.
6. Accept a case only with HTTP 200, exact profile/id, traceEntered true, its exact
   assertion count with all passed, null error, COMPLETE cleanup with no residual
   resources, and all independent provenance/runtime witnesses. Assertion or
   unexpected exceptions are FAIL; a witnessed entered-case timeout is FAIL.
   Uncertain entry/outcome is UNKNOWN. Syntax cannot establish runtime success.
7. Terminate only the recorded proven-owned whole-descendant execution domain
   and independently verify domain emptiness within 20 seconds, including dev,
   bundlers and node. Pinned dev.rs:742-746 deliberately places the node in a
   separate process group; killing only dev's group is insufficient. No
   best-effort single-PGID fallback is allowed. Preserve bounded redacted evidence,
   then remove only the domain's disposable bundles, logs and stores. Incomplete
   descendant or filesystem teardown blocks acceptance.

Overall deadline: 180 seconds, with preflight 30, startup 90, six requests at five
seconds each, and cleanup 20. Whole-descendant-domain supervisor limits: one CPU,
512 MiB memory, 128 processes, 128 MiB V8 heap, 256 MiB owned filesystem including
temporary bundles, logs and stores. Fixture limits:
two owners, 192 observations, 16 callback entries, 16 gates and 12 task fences per
request; normal traces use at most 22 logical payload bytes and four reads. Record
BLOCKED if provisioning cannot fit these limits; do not raise them silently.

## Static validation

    python3 validate_static.py --source-root /absolute/path/to/restored-cut
    sha256sum -c SHA256SUMS

The validator parses Python/JSON, compares case bodies and assertion declarations,
checks source/artifact hashes and baseline manifest correspondence, source ranges,
finite trace budgets, serial schedule and scope/cleanup structure, and invokes
Node only with --input-type=module --check on stdin. It never imports or executes
fixtures. author_manifest.py emits metadata around handwritten bodies; it does
not generate cases. static-validation.json is STATIC_ONLY / UNRUN. Files remain
editable until final independent receipt; freeze is a subsequent coordination step.

Excluded: auth/forgery/replay/malformed input, returned-capability lifetime
reproduction, denied G/N/P/J122 guarded-core work, fault injection, stress,
compression corruption, OS execution and distributed placement claims.
