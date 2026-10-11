# Ordinary facet/root workflows

Eighteen direct celld regression candidates: Z201–Z213 and Z215–Z219. All are
UNRUN. Z214 was retired before freeze because moving Z213's rollback schedule
from a root into a facet did not earn a new mechanism. No runtime, build, download,
mock execution, or full OS execution has occurred in this authoring task.

## What these add

The fixed traces cover named and string startup identity, durable receiver
continuity across fetch and RPC, ordinary plain loaded classes, the supported
four-level hierarchy, nested address components, separate SQLite schema catalogs,
mutable per-instance startup props, native constructor-time typed-graph decoding,
awaited asynchronous startup options, nested HTTP dispatch, independent app
transaction outcomes, local storage reset, selective deletion, recursive subtree
deletion, and module-local nested class resolution.

L001–L040 were read in full. The preserved facet example, foreign-class fixture,
distributed fixture and ACCEPTANCE.md were read before design. Each manifest row
identifies its nearest overlap and why the new asserted boundary is distinct.
The fixture calls real ctx.facets, Worker Loader, DurableObject storage and SQL.
The Sets/arrays in the supervisor only track owned cleanup names and worker
handles; they never implement a replacement object registry or oracle.

Z211's primary contract is successful Promise-valued facet startup options: the
constructor must receive the resolved persisted configuration. Lazy callback and
cached-instance checks are ancillary controls. Z210 reads only a summary captured
inside the constructor, so it targets native embedded startup decoding rather
than another generic RPC/storage graph round-trip. Z213 and Z215 use explicit
transaction-view rollback() as a normal application decision. Neither injects
failures or requests runtime recovery.

## OS relevance and evidence limit

The actual Cloudflare OS application checkout is absent from the recovered source
bundle. The mapping to OS-critical mechanisms is inferred from the preserved
celld-os-project/tests/ACCEPTANCE.md and its real distributed fixture. That
contract explicitly says fixtures are component evidence and actual OS
verify/run, positive execution-tail evidence, cross-process capabilities and
recovery require the real OS application. No actual OS source inspection is
claimed here. Every manifest entry names a concrete mechanism and this limit.

Likewise, identity/module tokens are relational fixture witnesses. They do not
prove process placement, ownership epoch, replicated storage durability, fleet
restart recovery, or full-OS acceptance. Source hashes are source identity only.

## Deferred direct-celld run contract

Use a separately authorized, independently reviewed supervisor against the exact
rebuilt guarded direct celld source. Follow the recovered BUILD_AND_TEST.md and
the supplied executable's actual CLI. Prepare a fresh owned deployment directory
with this entire wave and deploy wrangler.json. If a trusted bundler is needed,
record its version and resulting bundle hash. This archive includes no runtime
launcher and does not provision toolchains, binaries or dependencies.

Only Root is migrated as a SQLite DO. Facet, Leaf and CleanupProbe remain
unmigrated class exports. Loaded source is the exact static contents of facets.js
encoded in sources.js, with js_rpc explicitly enabled and only a fixture label in
its environment. The outer Worker keeps no capability after a request; each GET
creates one fresh random named root and makes one awaited root fetch. All facet
handles and loaded classes originate inside that durable root's active request.

Run the schedule serially. Require one fresh private store/fleet, one request at
a time, a 1-GiB RSS envelope, 12-second external HTTP deadline, 20-second per-case
owned-process deadline, and 420-second whole-wave deadline. Fixture budgets are
1 second for preconditions, 6 seconds for trace and 3 seconds for cleanup.
Application data is capped at 4 KiB, loaded module source at 16 KiB, and external
response capture at 64 KiB. JavaScript timers cannot interrupt native stalls: the external process deadline
must be enforceable. Any insufficient envelope or missing prerequisite is
BLOCKED for review; never silently raise bounds or substitute another runtime.

Record binary SHA256, source/build manifests, process IDs/start times/argv,
compatibility settings, exact deployed fixture hashes and fresh owned store.
Correlate rootName/objectId/activation with real runtime ownership. For an actual
PASS require HTTP200, ASSERTIONS_SATISFIED, traceSettled=true, every nonempty fixed
assertion true, matching expected/root IDs and names, cleanup.status=COMPLETE,
and independently verified final process/store teardown.

## Cleanup and stopping

All application calls settle before ordinary delete/reset steps. No stopped stub
is replayed. Z217 and Z218 await fresh same-name calls after public delete, which
returns void, to observe the public startup barrier. Common cleanup also deletes
each tracked top-level subtree and then awaits CleanupProbe.empty() through the
same name. It checks empty KV and absence of the only owned SQL table, releases
loaded worker handles, clears root storage and verifies root emptiness.

The replacement empty CleanupProbe facets remain resident until final teardown;
fixture cleanup is not a claim that runtime processes or storage files are gone.
External supervisor must terminate/reap only owned processes, remove the fresh
store, verify no survivors and record evidence. If a trace or cleanup times out,
there is no concurrent deleteAll attempt against unsettled work: return BLOCKED
and require external reap. Do not advance into a reused deployment after a
blocked cleanup. No user data or external service is accessed.

## Static verification

python3 validate_static.py checks case/manifest/schedule correspondence, fixed
assertion text, source pins, configuration, exact loaded-source mirroring and
JavaScript syntax. It never imports the fixture or executes a Worker. Source
metadata is regenerated by author_manifest.py; all metadata stays UNRUN after
static checks. Independent reviewer results and execution receipts remain
separate, independently versioned evidence.
