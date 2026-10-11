# Direct celld body and form semantics candidates

20 handwritten ordinary API cases, Y201–Y220. Every trace is entered by one GET
to /case/<id> on the actual deployed Worker. Local Blob, File, FormData, Request,
Response and ReadableStream operations run inside celld. Constructed upload URLs
are inert strings: these cases never send an outgoing fetch or upload to a host.

## Status

All runtime outcomes are UNRUN / NOT_RUN. No celld, reference runtime, build,
download or dependency installation was performed during authoring. Node --check
is syntax evidence only. Authored designs are unreviewed until a separate review
receipt accepts them; this source manifest awards no reviewed census credit.

Y212, Y214, and Y217–Y220 are EXPECTED_FAILURE_CANDIDATE from static source
inspection. The intended API contracts remain their pass oracles. Suspected
source gaps are separately described and are not observed runtime failures.

The immutable source cut includes the prior-lease guard, but historical unguarded
8d27 runtime results do not qualify these newly authored API cases. This package
does not include or claim a binary hash. A future run needs a fresh exact build
identity and complete guarded-source provenance.

## Coverage and overlap audit

- Y201–Y204: immutable Blob input/output ownership, byte slicing, independently
  opened stream lifecycle
- Y205–Y206: Blob/File form-entry conversion and mixed duplicate replacement
- Y207: one-shot binary Body to reusable typed Blob conversion
- Y208–Y213: multipart extraction, binary file preservation, legal delimiter
  lookalikes and parameter order, newline normalization, and typed form dispatch
- Y214–Y220: Request body transfer, Response clone metadata/byte ownership,
  Response.json snapshots, absent-body state, direct-reader disturbance,
  string media-type inference, and unused streaming Response cloning

Baseline S001–S024, H001–H026, X001–X024, other preserved case declarations, and
new U201–U220/V201–V218 were audited. Per-case distinctness notes identify nearby
coverage. There is no new credit for a repeated old subcheck. In particular Y215
adds clone metadata/header independence and consumer-buffer ownership; V215's
Cache.put clone-consumption subcheck is not counted again. Y220 exercises the
unsupported Response.clone stream path; H008 is Request.clone plus committed
host uploads. Y204 uses two independent Blob streams rather than a tee.

The form examples are complete valid multipart messages. Arbitrary bytes in a
File part are valid content; they are not malformed text input. The boundary
lookalike in Y210 occurs mid-line and cannot be a delimiter. No malformed-input,
auth, forgery, replay, retained capability, native guarded G/N/P/J122 path,
transport fault injection, compression corruption, or host-stream stress is used.

## Fixed oracles and safe local resources

cases.js contains all handwritten traces and literal expected values.
author_manifest.py emits metadata around those bodies; it never generates cases
from a parameter matrix and never executes JavaScript. Source ranges, suspected
gaps, intended contracts, exact assertion declarations, finite traces, cleanup
requirements, and primary normative links are recorded for each case.

Generated multipart boundaries are intentionally not fixed random output. The
fixture extracts the advertised boundary, then uses a small independent text-only
framing oracle. It compares fixed field names and exact values while accepting
standard header casing and optional final CRLF. The oracle never calls the SUT's
FormData parser. The hand-framed parser tests have independently fixed boundaries
and literal payloads, including exact binary byte arrays.

Forwarding helpers record the real runtime clone/Request-construction calls and
awaited Body consumers; they do not replace builtins or emulate behavior. A
buffered body producer can be lazy. Explicit JS stream producers here enqueue
bounded data and close synchronously. Every explicit reader is cancelled and
released on exit. All unlocked stream cancellations start before any are joined,
so one tee branch cannot block cleanup from cancelling its sibling. Streaming
clone consumers are joined using allSettled, even if one rejects.

Cleanup receipts distinguish released explicit readers, cancelled unlocked
streams, and runtime-retained locks. A retained lock must have a recorded
fulfilled full-body consumer or all clone/proxy descendants settled. Any other
locked stream is unverified and makes cleanup INCOMPLETE. COMPLETE means local
resource settlement only, not that runtime-owned locks were forcibly released.
External owned-process teardown is always required for suite acceptance. A
timeout in any API or cleanup is bounded by the external supervisor, never hidden
by an in-isolate timer or converted into a pass.

## Future direct-celld execution contract

This is a specification for a separately authorized run, not an executed launcher.

1. Provision an independently reviewed exact direct-celld binary built from the
   full source pin and trusted esbuild already installed. No substitute runtime,
   mock, copied polyfill, OS wrapper, build or download is part of this package.
2. Verify source-pins.json and SHA256SUMS. Copy only cases.js, fixture.js and
   wrangler.json into a fresh supervisor-owned directory. Do not use this author
   directory or the immutable baseline as a runtime work directory. No dotenv,
   bindings, shared bucket, production credentials or previous store is needed.
3. Record the complete source manifest, binary/build receipt, esbuild digest,
   deployed source/config digests, actual supervisor and child PIDs, owned
   resource envelope, fresh .celld/dev store and actual loopback listener.
4. Under a reviewed external bounded supervisor, the pinned source documents:

   CELLD dev RUN_DIR/wrangler.json --host 127.0.0.1 --port PORT --no-watch

   CELLD, RUN_DIR and PORT are the reviewed binary, fresh owned directory and
   reserved local port. dev performs a real deployment and starts a real celld
   node with a local store. Observe startup directly within 120 seconds; do not
   use a case as a health probe and do not add case repetitions.
5. Send the twenty schedule.json GET requests serially, one per case, with no
   request body/query/auth header or retry. Enforce five seconds and 64 KiB
   response maximum per request. For example, after provisioning, the client
   would request http://127.0.0.1:PORT/case/Y201 with a five-second HTTP deadline.
6. A case can pass only with HTTP 200, exact profile/id, traceEntered true, exactly
   its manifest assertion count, every assertion passed, null error, COMPLETE
   local cleanup with no unverified locks, and external direct-runtime witnesses.
   Assertions or unexpected exceptions are FAIL. Unavailable prerequisites before
   entry are BLOCKED. A witnessed case timeout is a timeout failure; ambiguous
   execution/outcome evidence is UNKNOWN. Never infer runtime success from syntax.
7. Terminate only the recorded owned process group and verify all children exit
   within the cleanup budget. Delete only the fresh deployment/store directory
   after preserving bounded redacted receipts and provenance. Incomplete external
   teardown prevents acceptance regardless of Worker assertion status.

The overall external deadline is 300 seconds: preflight at most 30, startup 120,
twenty requests at five seconds each, and cleanup 20. Runtime process-group limits
are one CPU, 1 GiB memory, 256 MiB owned filesystem, and 128 MiB isolate heap.
Fixtures use at most 16 KiB logical bytes, eight form entries, and sixteen explicit
reader reads. If provisioning cannot fit these reviewed limits, record BLOCKED
rather than raising them silently.

## Static validation

    python3 validate_static.py --source-root /absolute/path/to/restored-cut

This parses Python/JSON, checks exact source/artifact pins, source ranges, IDs,
routes, schedules, assertion declarations and Node syntax. It never imports or
runs the fixture. static-validation.json is explicitly STATIC_ONLY and UNRUN.

Primary contracts are the [Fetch Standard](https://fetch.spec.whatwg.org/),
[File API](https://w3c.github.io/FileAPI/),
[FormData](https://xhr.spec.whatwg.org/#interface-formdata), and
[HTML multipart encoding](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#multipart-form-data).
