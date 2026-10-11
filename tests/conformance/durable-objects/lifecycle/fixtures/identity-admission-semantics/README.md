# Valid public DO identity and successful admission

Five handwritten direct-celld candidates, A201–A205. All remain UNRUN with zero
runtime executions or passes. They are independent public API component tests.
They do not resume, rename or reproduce the excluded native routing N001–N036
wave or G/N/P/J122 guarded-core work. Five cases were selected rather than padding
the wave with parameter permutations or already-covered namespace changes.

- A201: named get/idFromName/getByName/valid idFromString state equivalence
- A202: newUniqueId serialization/reopen with two independent nameless states
- A203: one compound 1024-byte UTF-8 name metadata and full-name routing contract
- A204: successful constructor initialization admits first and queued fetches
- A205: successful request block admits its reader while a same-class peer progresses

No invalid, foreign or forged ID is ever submitted. There is no cryptographic,
authentication, replay, malformed-input, takeover, lease, draining, retained
capability, fault-injection, nested-gate or contended-gate test. There are no
native state hooks, runtime replacements, local Maps that simulate roots,
transaction-failure tests or blockConcurrencyWhile failure/timeout tests.

## Genuine schedules and fixed oracles

The Worker receives one GET /case/A20x and keeps its ordinary namespace stubs
only for that request. Every subject operation invokes a real migrated celld DO
via stub.fetch. Identity oracles use known strings and exact relational IDs from
public minting APIs, with actual recipient IDs checked on every response. They
never compute an expected identifier by copying native HMAC code.

A204 and A205 have a separately addressed Control DO with one finite promise
wait. The target calls Control from inside its successful block. The supervisor
observes that real hold before sending a new target request and awaiting a peer
operation. Before releasing, it requires Control to still be held, zero target
handler entries, and both target promises unsettled. After release, all actual
handler entries must carry the exact target ID, readiness and after-release
witness; returned storage values must be terminal. First/second order in A204 is
intentionally unspecified. A205 uses a second root of the SAME EventTarget class.

Control is only a schedule witness; it does not implement DO addressing, storage
or input admission. Root identity does not prove node/process placement. A single
live deployment may execute this component contract. There is no distributed,
restart, replication, epoch or full-OS claim.

The 2500 ms Control fuse resolves normally, never rejects the block. If it fires,
the desired successful explicit-release schedule is BLOCKED, not a positive
result. The test never waits for celld's 30-second block timeout. Assertion,
request and native failures are not induced by the written schedules; an observed
failure remains a failed/blocked candidate, not authorization to explore recovery.

## OS relevance and overlap limits

The actual Cloudflare OS application checkout is absent. Relevance is inferred
only from preserved ACCEPTANCE.md, duplicate-names, foreign-class and distributed
component fixtures. They establish that ordinary namespaces, roots and isolation
matter to the intended OS acceptance program; they do not establish that the OS
calls idFromString/newUniqueId, uses 1025-byte names, or initializes a particular
class with blockConcurrencyWhile. Each case labels this evidence limit.

The overlap audit read the public docs and harness, preserved fixture source,
T/L/R manifests, U014/U015/U017 bodies, M008's body and graph, and Z201/Z202.
M008 concerns ECMAScript module namespace identity, not DO ID helper identity.
Class/script/binding rename and facet display identity are already covered and
receive no new credit. T001/T031 and the new atomic-accounting schedule are
storage transaction admission; this wave has no storage transaction at all.
The distributed fixture's normal reentry case passes transient RPC callbacks;
this wave uses no RPC callbacks or returned capability. No gate permutations were
added. See overlap-audit.json for the exact per-case distinction and source pins.

## Deferred execution contract

No SUT launch, build, dependency download, fixture execution or OS execution was
performed. This folder supplies executable fixture/configuration and a static
schedule, not a runtime launcher. A future authorized reviewer must follow the
recovered BUILD_AND_TEST.md and the rebuilt executable's actual CLI, deploy all
four migrated classes from wrangler.jsonc in a fresh private owned store, and
record source/build/binary hashes and exact fixture hashes. If bundling is
required, record the trusted bundler identity and output hash.

Run the five listed GETs serially with a one-GiB process RSS envelope. Enforce a
12-second external HTTP deadline, 20-second per-case process deadline and
120-second whole-wave deadline. JavaScript timers cannot interrupt a native
stall, so the external process limit must be independently enforceable. Fixture
limits: three activated roots, 100 supervisor DO fetches plus at most 3 target
control calls, 60 status polls, two logged target entries, one small key per
object, 1025 UTF-8 bytes per name and 64 KiB external response capture. The
metadata's 110 total-fetch cap includes conservative headroom. Trace timeout is
6 seconds; owned cleanup timeout is 3.5 seconds.

A runtime pass requires HTTP 200, ASSERTIONS_SATISFIED, traceSettled=true,
nonempty all-true fixed assertions, exact recipient IDs, no Control fallback,
COMPLETE empty storage cleanup and independent verification of final process and
store teardown. A missing prerequisite is BLOCKED; do not silently raise limits,
substitute Node/workerd/mocks, or turn unexecuted checks into passing checks.

## Owned cleanup

Cleanup normally releases Control, joins every outstanding target request, then
calls deleteAll and verifies empty storage on only the registered fixture roots.
Control is last and must have zero waiters and timers. Registration deduplicates
alias handles only for cleanup and never acts as a target registry. An unsettled
trace cannot race deleteAll: it returns an external-reap requirement instead.
Cleanup timeout also blocks further cases in a reused deployment.

After fixture cleanup, an external supervisor must terminate/reap only its
verified owned process groups, remove the fresh owned store and verify absence
of survivors. Empty databases/actors may remain resident before that external
teardown; fixture cleanup makes no claim that processes or files disappeared.
No real user data or external service is used.

## Static checks and review

python3 validate_static.py checks handwritten case/manifest/schedule agreement,
nonempty literal assertions, source hashes/ranges, immutable-baseline hashes,
finite bounds, public configuration and JavaScript syntax only. It does not
import or execute fixtures. author_manifest.py regenerates metadata from fixed
case descriptions, never from observed runtime output.

## Oracle correction identified during review

The official [ID documentation](https://developers.cloudflare.com/durable-objects/api/id/)
separates client ID metadata from the server name passed to an object. A201 does
not assert incidental server-name retention after a valid parsed-ID access.

A203 deliberately retains the intended full client stub name from the official
[Stub contract](https://developers.cloudflare.com/durable-objects/api/stub/#name).
The recovered source instead sets client stub.name from its server dispatchName,
which drops long names. This is a SOURCE_PREDICTED_COMPATIBILITY_FAILURE, not an
executed failure. The server ctx.id.name cutoff and full-name state-routing
oracles remain intact, and run before the client-name assertion. No expected
value was weakened to match source behavior. Both official pages were checked
on 2026-10-09; source assessment stays separate from UNRUN runtime status.

Independent review is required before freeze or count credit. Author metadata
intentionally awards zero independent review credit. Runtime status stays UNRUN
after successful static validation. Reviewer results remain separate evidence.
