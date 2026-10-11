# Direct celld ordinary pipe cleanup semantics

Nine handwritten primary candidates, S201–S209, executed by individual GET
requests to `/case/<id>` in one active Worker.fetch. `fixture.js` imports
`cases.js`; `wrangler.json` supplies deployment metadata. There are no bindings,
remote stream capabilities, mocks, outgoing requests, persistent writes, runtime
monkey patches, compression transforms, or injected process/network faults.

## Status and execution boundary

Runtime status is **UNRUN / NOT_RUN for every case**. Source reading, Python
metadata generation/AST checks, JSON parsing, file hashes and Node `--check`
were the only authoring actions. Node never imported or ran a fixture, and no
celld/reference runtime was launched, built or downloaded.

S207–S209 are static EXPECTED_FAILURE_CANDIDATE designs. The correct intended
oracles are unchanged: zero stays zero; pre-aborted pipes join cleanup before
settling; a source-cancel rejection replaces the signal error. `streams.js`
568–573 and 617–621 predict discrepancies, which remain unobserved at runtime.
All errors are explicit ordinary source/sink application callback outcomes.

Static acceptance must come from a separate review receipt. The manifest keeps
reviewed credit at zero; a later independent receipt, not an edited author
assertion, supplies acceptance. Historical unguarded 8d27 runtime evidence does
not qualify these new tests. No current binary hash is claimed.

## Distinct mechanisms

- S201: EOF suppresses sink close and allows a new writer to finish
- S202: source error suppresses sink abort and preserves later writes
- S203: sink error suppresses source cancellation and permits a later drain
- S204: active signal shutdown waits for a write while preserving both resources
- S205: held write precedes independently held source and sink cleanup actions
- S206: pipe fulfillment and lock release wait for sink close acknowledgment
- S207: pre-aborted zero reason reaches rejection and cleanup with no writes
- S208: pre-aborted asynchronous cleanup is joined before ownership release
- S209: a rejecting cancellation action overrides the initiating signal reason

The overlap audit includes the preserved 575-design intent inventory, full
S001–S024, X001–X024 and H001–H026 manifests, actual S015/S016 and X013 bodies,
and searches throughout the stress corpus for prevention flags. X017 is absent
from the preserved X manifest. Existing default transfer, native-transform signal
fanout, remote writer close, HTTP abort, Blob/Body ownership and new facet/root
cases are not counted again. This is not a boolean/value matrix.

## Oracle and cleanup design

Use actual direct-celld ReadableStream, WritableStream and AbortController
globals. Each source initially has at most two small numeric chunks. Preserved
resources receive at most one extra chunk/write. Manual draining is capped at
four reads. Numeric chunks are valid ordinary non-byte streams.

Gates are explicit finite promises. A zero-delay event-loop checkpoint only
makes already-scheduled reactions observable while a gate is held; no wall-clock
latency threshold is a pass oracle. Callback instrumentation records returned
promises without implementing or replacing stream behavior. The harness adds an
unused AbortSignal to unsignaled traces solely for emergency failure cleanup.

The finally-equivalent cleanup path opens every gate, stops unfinished pipes,
joins original pipe and callback promises, releases manual owners, and checks
public reader/writer closed promises for terminal states. Still-open resources
are canceled/aborted and joined. Closed-promise rejection is valid evidence of an
errored terminal stream, not a swallowed new cleanup action failure. Unexpected
cleanup-action rejection is recorded as INCOMPLETE. Both stream locks and timer
count must reach zero. Cleanup does not erase a failed assertion.

If a broken implementation prevents a gate milestone or cleanup from finishing,
the request may remain pending. Only the independent supervisor may classify and
terminate that owned run; in-Worker timers are never the timeout authority.

## Mandatory future run contract

1. Verify the immutable guarded source archive and all pins. Supply a freshly
   identified direct-celld binary, complete build receipt, deployment receipt and
   an isolated disposable store. Follow the source archive's BUILD_AND_TEST.md
   and local adapter deployment protocol; do not substitute Node or workerd.
2. Deploy this Worker from wrangler.json. Before entering any trace, independently
   enforce schedule.json: 180-second outer suite deadline, 30-second preflight,
   90-second startup, five seconds per request and 20 seconds for cleanup. These
   are outer monotonic supervisor deadlines that include hung HTTP/read/cleanup.
   Limit the owned process group to 512 MiB, 128 PIDs and one CPU, V8 heap 128 MiB,
   response 64 KiB and owned filesystem 256 MiB. If unavailable, report BLOCKED.
3. Issue exactly one sequential GET per scheduled case. Record source/build and
   deployment identities, response bodies, all assertions, HTTP result, process
   state, entry evidence and deadline classification. No automatic retries.
4. PASS requires all declared assertions and complete local cleanup plus verified
   owned process-group exit and store removal. Timeout or residual work cannot
   be converted to PASS. Missing preconditions are NOT_RUN/BLOCKED; ambiguous
   entry/outcome is UNKNOWN. Terminate only owned resources on a breach.

The authored fixture and schedule are executable inputs for that existing direct
harness protocol, not a claim that the binary or external supervisor is currently
provisioned. No run or build is authorized by this package alone.

## OS relevance and limits

This is core OS supporting stream/cancellation coverage. The preserved
native-transform wave's source-pins.json records OS archive import, worksheet
export and pack/attachment digest stream usage. That provenance motivates
reliable shared stream ownership and cancellation. Its OS commit and file hashes
are copied as **historical context only**. The OS checkout is absent and was not
reread. Exact prevent* usage by OS callers is not asserted. This wave creates no
new product service and exercises no active DO lease/draining or G/N/P/J122
restricted path, authentication, forgery, replay or malformed-input mechanism.

## Static reproduction

`python3 author_manifest.py` regenerates metadata around handwritten case bodies.
`python3 validate_static.py` checks pins, manifests and syntax without executing
any trace. `SHA256SUMS` freezes package files; review receipts are kept separately.

Primary contract: [WHATWG ReadableStreamPipeTo](https://streams.spec.whatwg.org/#readable-stream-pipe-to),
retrieved 2026-10-09. Source line mappings and exact hashes are in source-pins.json
and the per-case manifest.
