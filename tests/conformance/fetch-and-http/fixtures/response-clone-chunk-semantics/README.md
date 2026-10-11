# Direct celld Response clone raw-chunk regression

One authored ordinary case, Y301, with 11 fixed assertion call sites. Status:
NOT_RUN / UNRUN. Independent review is required before one primary static-design
credit can be recorded. No runtime pass, source fix, deployment, build or binary
qualification is claimed here. This package is append-only relative to the
original 57 URL/Headers/Body cases; none of those fixtures or oracles was edited.

## Distinct mechanism and oracle

Y301 creates one default ReadableStream, enqueues exactly one four-byte
Uint8Array [10,20,30,40], and closes synchronously. It invokes the real
Response.clone(), acquires each returned body's raw reader, and joins both first
reads before inspecting or changing data. After both fixed initial-byte checks,
it writes 99 to the original branch chunk's first byte. Its raw chunk must then
be [99,20,30,40], the sibling raw chunk must still be [10,20,30,40], and their
ArrayBuffer objects must differ. Both readers then return EOF with no value.
Every logged byte assertion is a fresh primitive-array snapshot, additionally
snapshotted by the assertion recorder before any later mutation.

Fetch body clone uses the specification-level stream tee operation, retaining
one output and assigning the other to the clone. That wrapper requests cloned
chunks in branch two. Default-stream tee enqueues each source chunk separately,
copying branch two when requested. Thus the deliberately single default-stream
chunk is an explicit input contract, rather than an assumption about arbitrary
network byte partitioning. Sources read on 2026-10-09:

- https://fetch.spec.whatwg.org/#concept-body-clone
- https://streams.spec.whatwg.org/#readablestream-tee
- https://streams.spec.whatwg.org/#readable-stream-default-tee

source-pins.json records the linked commit snapshots for reproducibility. The
living standards supply the contract; source inspection only explains how the
fixture reaches the implementation.

Y220 joins final arrayBuffer consumers, which each copy bytes, and cannot detect
raw tee-chunk aliasing. Y215 checks mutation of a buffered clone's returned
arrayBuffer and metadata. Neither tests this raw-chunk mutation. Existing
S017/H008 concern remote stream duplication and Request/host upload respectively;
their data transport/cleanup primitives earn no credit here. This is one case,
not a sweep of payloads, mutation positions or directions. EOF, types and exact
initial values are supporting assertions for that one isolation mechanism.

## Exact source identities

The old candidate001 Response.clone refuses streaming bodies. No attempt was
made to run Y301 on it. The frozen candidate002 r002 overlay changes the call to
existing body.tee(true); streams.js itself remains unchanged. Both source
identities, the virtual full-tree manifest, the v2 tee-true clarification and
prior fixture hashes are pinned separately in source-pins.json. Pinning this
candidate is not independent source approval and does not bind a future binary.
No presumed or missing post-ZIP provenance patch is reconstructed.

## Entry and bounded settlement

Deploy fixture.js with wrangler.json through the parent's separately reviewed
direct-celld workflow. Exactly one GET /case/Y301 enters exactly one trace. Do
not import the fixture into Node, execute extracted SUT JavaScript, substitute
web APIs, or use a reference runtime as the subject.

The finite operation budget is one source chunk/four source bytes, one clone,
three tracked streams, two explicit readers and at most two reads per reader
(four total). First reads and EOF reads each have an allSettled join. Cleanup
first joins every recorded read, then starts every held-reader and unlocked
stream cancellation before awaiting any, and finally releases all explicit
readers. This covers early assertions and exceptions after successful cloning.
If clone throws before tee, the unlocked source is cancelled. If a partial clone
leaves an inaccessible branch or unprovable source lock, cleanup is incomplete.

The existing tee may keep its source reader locked even after terminal input.
The fixture records that fact rather than treating explicit branch releases as
a source unlock. Every tracked stream needs terminal proof; the retained source
needs both tracked descendants' EOF/cancel-and-release evidence. The successful
r002 trace is expected to report four joined reads, two joined reader cancels,
two released readers, three terminal stream receipts, and one retained source
lock with both-local-clone-descendants-settled proof. This receipt describes only
local terminal settlement, not release of every runtime allocation.

No timer races a pending subject read. If read/cancel never settles, the external
five-second request deadline and independent suite/cleanup deadlines must stop
the entire proven-owned dev/bundler/runtime descendant tree across all PGIDs,
including owned temporary, log and store paths, and mark the semantic outcome UNKNOWN with
incomplete local cleanup, never PASS. An actual false assertion or API exception
is FAIL. Completion additionally requires verified descendant-tree emptiness, closed
listener and removal of all owned temporary, log, stage and store paths.
The process_group resource-limit field names in schedule.json are legacy labels
for that whole proven-owned descendant domain across PGIDs, not a limit on which
processes belong to cleanup. Strict enforcement remains unobserved. A separately
reviewed functional-only sampled envelope may report functional observations,
but cannot claim strict-profile success. Resource limits in schedule.json are
required strict-profile preconditions, not already-enforced observations.
The parent owns the separate one-case runtime envelope and authorization.

## Author checks and exclusions

validate_static.py parses JSON/Python, compares fixed assertion declarations,
checks case/schedule/config identity and SHA-256 pins, and invokes Node only in
--check parser mode. It never imports/evaluates JavaScript or launches celld,
a bundler, VM, network service or SQL. static-validation.json is static evidence
only; SHA256SUMS seals the package without changing another wave.

Scope is ordinary local four-byte Response body behavior. No generic security,
ownership, resource-ceiling, native HTTP, RPC, remote-handle, capability or
scheduler claim is made. G/N/P/J122 guarded-core/dependent work, authentication
forgery/replay/malformed/security probes, stateless returned-capability lifetime
reproduction, missing post-ZIP provenance reconstruction and alternate setup
routes remain excluded. No SUT changes or dependencies are needed by this test.
