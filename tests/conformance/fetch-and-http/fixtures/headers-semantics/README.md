# New direct celld Headers and Cache API cases

18 newly authored, manually reasoned designs (17 primary candidates and one
implementation characterization earning zero primary credit): V201–V213 cover thirteen distinct
Headers conversion/mutation/iteration mechanisms; V214–V218 cover five finite Cache
consumer workflows. They are **NOT_RUN**, unreviewed source candidates. No historical
runtime evidence is attributed to this wave. This is new work, not reconstructed
post-checkpoint work. Static syntax validation is not direct celld execution.

`manifest.json` contains each fixed trace, oracle, source lines, relevance,
distinctness, schedule, limits and cleanup. `cases.js` contains the actual
assertion-bearing functions. Metadata generation never generates case bodies or
parameter combinations. `fixture.js` exposes one case per request. The selected
source is immutable; source identities are in `source-pins.json`.

## Coverage audit and relevance

The 575 restored designs are concentrated on RPC/capability ordering, codec,
streams, lease/output/input gates, deployment/durability, alarms and bounded load.
There is no dedicated local Headers or Cache public API wave. Existing RPC-codec
C015 checks merged ordinary fields, revived cookies and detached source snapshots
across RPC. This wave does not count an equivalent cookie/merge-only test: it
instead examines constructor observable effects, memo invalidation, iterator
position/value updates, callback identity, and both input/output tuple aliasing.
The cases are relevant to middleware header construction, ordinary response
rewriting and best-effort cache consumers; they do not execute a full OS workflow.

Both implementations are included by direct runtime bootstrap (`bootstrap.rs`,
HEADERS_SOURCE/CACHE_SOURCE). Expected values are explicit literals. V209 follows
this source's live numeric-cursor semantics. V216 specifically characterizes celld's current always-miss layer; source comments
allow caching to be added later. It is intentionally not a required functional
invariant and earns zero toward the 2,000-case target.

## Static verification only

Run `python3 validate.py`. This hashes source pins, verifies manifest/function
bijection and status fields, and invokes Node only as a JavaScript syntax checker.
It never evaluates fixtures or runs a Headers/Cache polyfill. The source identity
and syntax checks do not establish a passing SUT assertion.

## Deferred direct-runtime deployment contract

Runtime setup is currently unavailable: there is no celld binary, toolchain,
dependency cache, reviewed deployment supervisor or VM image here. No runtime
launch, build or download was performed or authorized by this wave authoring step.

When separately authorized and provisioned, a reviewed adapter must:

1. Copy this folder to a fresh owned staging directory, preserving hashes. Bundle
   local imports with a trusted configured bundler if the selected `celld dev`
   route requires it. Deploy `wrangler.jsonc` as an actual direct celld Worker.
   Read the recovered `BUILD_AND_TEST.md` and CLI help for that exact build; do not
   substitute workerd, hybrid, Node, mocked globals, or CELLD_TEST_SCRIPT_PATH.
2. Record executable SHA256, the source build manifest, PID/process-start identity,
   owned state directory, worker/fixture hashes, command and compatibility date.
   An arbitrary HTTP response that names this wave is not an identity witness.
3. Isolate ingress to loopback. Use an outer supervisor with a 1 GiB process RSS
   limit, at most one case request in flight, a 5-second HTTP deadline, a 10-second
   per-case owned-process deadline and a 180-second entire-wave deadline. If these
   cannot be enforced or leave insufficient runtime headroom, report BLOCKED and
   obtain a reviewed envelope rather than silently removing limits.
4. Read GET /manifest and compare the exact ID set, then make one GET /case/V201,
   and so on for each exact manifest ID. Never batch case IDs into one invocation.
   Cache URLs are valid synthetic keys; the fixtures never fetch them. Preserve
   complete response JSON and HTTP status. A 200 response is only an assertion
   observation, never independent proof of the SUT or successful teardown.
5. Require fixtureStatus ASSERTIONS_SATISFIED, traceSettled true, a nonempty set
   of all-true assertion records and successful cleanup. A timeout, HTTP error,
   missing API, unexpected failure or unjoined trace is FAIL/BLOCKED, never PASS.
   Inspect error and assertion records to distinguish semantic failure from
   missing prerequisites. The fixture never emits a final PASS classification.
6. Stop/reap only owned processes and confirm no request/case work survives. Write
   a separately reviewed runtime result joining source/build/process/fixture
   identity with assertions and cleanup. A leftover locked reader on an explicitly
   closed finite stream is recorded as runtime-owned, not falsely reported as a
   released lock. No resource-leak or cross-process claim is made by that record.

All keys and values are valid, tiny and synthetic. There is no authorization,
forgery, replay, malformed-input, network-fault, retained-capability or guarded-core
work here. Each case's substantive operations are fixed and finite; elapsed-time
checks supplement an external deadline and cannot terminate a wedged isolate.
