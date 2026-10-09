# Live RPC capabilities

The RustV8 runtime can transfer a live `RpcTarget` or callable RPC target to a
different isolate or celld process. Calls return to the exact exporting heap;
they do not rely on the caller and target sharing a process, Worker pool, or
actor placement.

## Native contract

The internal harness uses these operations:

- `__capability_export(token, sourceScope)` returns an opaque route JSON string.
  `sourceScope` names the actor that owns the target; `null` means a stateless
  target. The host checks that actor storage belongs to the exporting heap.
- `__capability_call(route, pathJson, argsBytes)` asynchronously returns
  structured-clone reply bytes. Null argument bytes request a property read.
- `__capability_release(route)` asynchronously delivers one reference release
  to the exporting heap. The harness owns reference counts and disposal.
- `__capability_revoke(route)` synchronously removes an export on final local
  disposal or actor release. Only the exporting heap can revoke it.

The exporting harness implements `__dispatchCapability` and
`__releaseCapability`. These operations and route formats are private runtime
interfaces, not application APIs or a durable serialization format.

Direct engine embeddings without a host transport and without a Slot receive a
null route, preserving local-only references. Such a marker cannot be revived
as a foreign reference. Configured celld nodes do not use this fallback.

## Ownership and security

Each route contains the node address, a random process incarnation, heap
identity, an unguessable 256-bit bearer, and the originating actor's storage
scope, root scope, and activation epoch when applicable. A domain-separated
fleet HMAC seals the complete route. A receiving host verifies this seal before
using a foreign address, preventing application-created routes from turning the
peer transport into an arbitrary signed-request proxy.

Cross-process calls use `POST /peer/capability` with the existing fleet peer
request authentication and replay checks. A target validates the exact bearer
and route before consulting actor placement. Actor calls use the existing
owner/admission lifecycle and refuse a different owner. The exporting isolate
then rechecks its own heap and storage epoch immediately before dispatch.

The registry holds weak Slot references. It does not keep idle heaps alive or
prevent actor migration. Admission takes a temporary affiliation under the
heap lock, and retirement rechecks its counters under the same lock. A retired
heap, lost process, released actor, or changed epoch invalidates a live
reference rather than silently invoking a new instance.

Persisted/restorable capabilities are a separate layer: restoration resolves
the current actor owner and obtains a new live reference. Persisting this
opaque live route is not a substitute for restoration.

## Async execution and limits

Each call is driven by the existing asynchronous V8 event pump; no isolate lock
is held while waiting for another process. Actor capability calls install a
native cell event and its storage/output-gate context. The harness handles the
actor input gate, including captured critical-section reentry, so callbacks can
return to an actor while its outbound call is suspended. Reply bytes wait for
normal actor/facet output proofs.

Calls have a 60-second transport bound and are never automatically retried:
a timeout or disconnect does not prove that application code did not run.
Request and response wire bodies are bounded at 16 MiB. Reply bodies are read
incrementally, so a missing Content-Length cannot bypass the limit. The JS op
also limits argument bytes to 8 MiB and property paths to 128 components.

Debug events `capability_export` and `capability_peer_call` record node,
process, and heap identities for routing diagnostics. They never log bearer
tokens or complete routes.

## Restoration and stream adapters

The persistent-capability wrapper may restore once when the host proves the
attempt did not execute. This proof is a private Rust error type created only
before target dispatch (including a definitely failed TCP connection). Across
a peer hop, a dedicated response header carries that proof; an HTTP error
status or application-supplied error message does not. The JS wrapper retains
its prepared argument envelope for that one safe attempt. In-flight aborts,
completed handler failures, response loss, and timeouts never authorize replay.

The harness uses live target adapters for readable and writable RPC streams.
The real multi-process regression suite exercises readable/BYOB and binary
chunks, cancellation reasons, writable errors and abort, backpressure, cleanup,
and exporter death. Generic live AbortSignal propagation remains a separate,
process-local facility; it is not provided by this capability transport.

Worker WebSocket upgrades carried through service responses preserve the
native socket handoff rather than serializing only status 101. The pending
caller's native request context owns a parked handoff until it is returned or
accepted, so ignored responses and canceled calls release it. An intermediary
can forward the existing target unchanged or accept it through a local native
bidirectional pipe. This service-response handoff is process-local; it is
separate from the cross-node Durable Object WebSocket tunnel.

## Static DurableObjectClass references

A specialized class exported by a deployed script carries a host-sealed
reference to the source script, class name, immutable deployment version, and
canonical deployment-graph identity. The source's persistent-storage opt-in is
also authenticated. Importing a reference creates a local facet heap from that
exact source WorkerConfig, preserving its bindings and compatibility settings;
it does not redirect facet storage to the source script's ordinary actor
namespace. Storage and lifecycle remain parent-owned.

The host validates the seal before selecting code, and restricts the resulting
loader to the authorized class. Dynamic, caller-supplied Worker classes do not
receive static deployment references. If the referenced graph is no longer
available on a node, import fails explicitly instead of selecting the latest
version. In particular, a persisted class reference does not make old deployed
code available after a cold restart into a different deployment graph.

## Same-named Durable Object classes

Multiple deployed Workers may each export a class such as `UserAccount`.
The generation retains their separate configs and verifies the namespace
signature already embedded in celld's named and randomly generated Durable
Object IDs to select the source Worker. Exactly one source must match. This
changes neither `Class:ID` scope strings, storage keys, owner records, nor pins,
and introduces no node-affinity requirement.

Canonical 64-hex user object IDs are checked even when only one source remains,
so removing one Worker cannot reinterpret its existing state as another
Worker's class. Previously unchecked arbitrary 64-hex operator IDs now fail
instead of selecting unrelated code. Non-64-hex legacy scopes remain accepted
for a unique class, but fail when source selection is ambiguous. Shared runtime
namespaces such as D1 retain their existing fleet-wide semantics.

## Ordered capability dispatch

Calls and releases issued through aliases of one capability share a sender
lane. The receiver admits sequence numbers in order and advances the lane when
the target method has entered, rather than when its returned promise settles.
A later method can therefore resolve an earlier pending method, and callbacks
can re-enter a suspended caller. Local serialization and exact JSON wire-size
validation happen before enqueue; synchronous rejection rolls back the unused
sequence. Transport gaps are bounded at 60 seconds, then break that lane instead
of repeatedly hanging later calls. Already-dispatched sequence outcomes remain
ambiguous and never authorize automatic mutation replay.

Active sender state is bounded, with at most 4096 idle lane counters retained
for reacquiring previously released references. Each exporting capability also
has a finite 4096-sender-lane admission limit; exhaustion fails explicitly.
These bounds limit bookkeeping, not actor placement. They are not a substitute
for hostile-tenant isolation or a full resource-accounting audit.

## Source-worker Durable Object namespaces

Multiple cohosted workers may export the same user class name. Celld IDs already
encode a namespace HMAC derived from the source worker and class name. Activation
uses that existing namespace component to select exactly one source config.
The namespace key is deterministic, so this is source discrimination, not
caller authorization or tenant isolation. The stored `Class:ID` scope, ID
generation format, ownership protocol, and replication keys do not change. Named and random IDs therefore retain existing
state when another source exports the same class.

Canonical 64-hex user IDs must match a loaded source namespace even when only
one candidate remains; removing a source must not reinterpret its state as a
different worker. Noncanonical legacy raw IDs retain prior behavior only when
the class has one unambiguous source. Previously unchecked arbitrary 64-hex
operator IDs now fail closed. Ambiguous, mismatched, and unsigned colliding
references are rejected rather than routed to the first worker. Shared engine
reserved namespaces retain their existing fleet-wide behavior.

## Parameter and stored-value ownership

`rpc_params_dup_stubs` is enabled by default from 2026-01-20, with explicit
`rpc_params_transfer_stubs` opt-out. Modern arguments duplicate native stubs and
honor the workerd custom `dup()` contract for RpcTarget/function parameters;
return values transfer. This distinction preserves pure-JS Cap'n Web observer
ownership when a Worker forwards arguments into native RPC.

Opted-in durable service references retain their original source script,
entrypoint, props and originating persistence permission across RPC/storage.
Ordinary data in a lifted envelope cannot claim native capability marker keys;
validation checks each copied key, and revival only recognizes own marker
properties. Ordinary configured bindings do not gain durable authority merely
because their shape resembles a service token.
