# C7-03 — stubs made for one stateless request are refused to another

celld bound streams and RPC targets received over RPC to their request
(C7-02), but not the stubs a request makes: `ctx.exports.Name({props})`
stubs (their nodes carried no owner) and Durable Object stubs. Another
request could call them while the first was live and after it finished, so
a later request could act with an earlier request's `ctx.props`. workerd
binds both to the IoContext that made them (IoOwn, io/io-own.h; Fetcher
channels, api/http.h; `DurableObjectNamespace::get`, api/actor.c++) and
refuses them with the cross-request error (I/O type OutgoingFactory).

Fix (harness): a stub made with its own props, a service stub revived from
RPC or storage (a loopback stub of this script, or a stub or binding of
another script), a Durable Object stub, and a Durable Object class carrying
props (`ctx.exports.Name({props})`, a Worker Loader class, or one revived
from RPC or storage), a Worker Loader stub and its entrypoints, and a facet
stub record the context that made them
and check it before admitting a call, a property read, a fetch or (for a
class) a facet start in `ctx.facets.get`, and when
the stub is serialized (an RPC argument or result, nested in a value, a
storage write), as workerd's `Fetcher::serialize` reaches the channel
through its IoOwn (api/http.c++; Durable Object stubs serialize as Fetchers,
api/actor.h; classes: export-loopback.c++ LoopbackDurableObjectClass::call,
actor.c++ DurableObjectClass::serialize/deserialize). The un-specialized
`ctx.exports.D` stays shared. Use from another Durable Object in the same isolate gets
workerd's "different Durable Object" wording. Bindings of the isolate are
not bound, as in workerd: `env` service bindings, `ctx.exports`' own
entries, Durable Object namespaces. A Durable Object's own stubs keep
working across its events (one context per incarnation). A stub made where
no request ever ran (module scope) is not bound; one made by code that
resumed after its request ended belongs to that ended request, so no request
can use it (workerd never runs such code; that code itself gets "The
execution context which hosts this callback is no longer running.").

Case (single node, differential with stock workerd): `/hold` makes a props
stub, a Durable Object stub and receives one over RPC, uses and passes them
on, and waits; `/use` (another live request) and `/later` (after `/hold`
ended) are refused all three for calls, fetches and passing on (through
`ctx.exports.Ent.echo`, `env.SELF.echo`, a Durable Object's `echo`, a
Durable Object stashing it for later calls, a nested object, a `Map`), and
still use `env.SELF`, `ctx.exports.Ent` and `env.D`; the same holds for a
stub carrying props that a second script (`y.js`, deployed first into the
same dev store) returned over RPC: called, fetched, passed through
`ctx.exports.Ent.echo` and through `env.Y.echo`; and for Durable Object
classes carrying props: `ctx.exports.D({props})` made by `/hold`, and the
classes `y.js` returns alone (`mintCls`) or in `{class}` (`mintBag`, the
gatekeeper shape), given to a Durable Object that starts them as a facet,
directly and after a `ctx.exports.Ent.echo`;
a Worker Loader stub and an entrypoint with props held by `/hold` (called,
fetched, passed on; within its own request, workerd refuses passing the
entrypoint on at all while celld refuses the receiver's call, so that row is
not compared there); `/handles`: a
loader entrypoint and a facet stub an actor made, used by it in a later
event and refused to another actor ("different Durable Object"); `/keep` reuses a
Durable Object's stub across two events; `/actors` uses one actor's stub
from another actor directly, through storage and through RPC (refused,
"different Durable Object"); `/park` + `/wake` + `/late`: stubs made by a
continuation resumed after its request ended are unusable.
Before (C7-02 tree): `/use` and `/later` were allowed everything
(`props:{"user":"alice"}`). Before serialization was checked: every
passing-on shape, the storage and RPC shapes in `/actors`, and `/late` were
allowed. Before revived stubs of other scripts were bound: every `ys*` shape
was allowed (`y-props:{"user":"alice"}`). Before classes were bound: every
class row started its facet with alice's props. Before loader and facet
handles were bound: every loader row and `/handles` other-actor row was
allowed.
