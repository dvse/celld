# Finding regressions by behaviour

| Behaviour | Finding | Invariant |
|---|---|---|
| rpc/restored-http-channels | [R4-05](R4-05/README.md) | Restored static Fetcher crossing RPC retains HTTP status, header and body; open finding |
| durable-objects/facet-mutation-order | [R4-03](R4-03/README.md) | Clone precedes delete and failed clone proof is retained; partial finding |
| durable-objects/persistent-stub-permissions | [R4-10](R4-10/README.md) | Reference control: restore is flag-gated and transient token parameters are rejected |
| rpc/session-completion | [R4-01](R4-01/README.md) | Final-export release ends a stateless session; failed encoding reclaims provisional exports; partial finding |
| durable-objects/alarm-timeout | [R4-04](R4-04/README.md) | Expired alarm revokes the incarnation and drops already-ready I/O |
| web-platform/abort-attributes | [R4-08](R4-08/README.md) | Abort attributes are branded and readonly in both compatibility modes |
| rpc/facet-serialization | [R4-11](R4-11/README.md) | Direct facet capabilities reject RPC serialization; ordinary targets remain usable |
| rpc/persistent-capability-failure | [R4-02](R4-02/README.md) | Authenticated pre-dispatch failure preserves resolved identity; stored-token lazy copies restore independently |
| rpc/capability-identity | [R4-06](R4-06/README.md) | Repeated wire references preserve identity and one disposal owner |
| rpc/disposal-context | [R4-07](R4-07/README.md) | Final release enters the source resource context and refuses dead re-entry |
| rpc/disposed-pipelines | [R4-09](R4-09/README.md) | Saved pipeline methods reject after disposal; underlying root promise remains awaitable |
| rpc/receiver-lifetime | [R4-12](R4-12/README.md) | Each props binding operation constructs a new stateless receiver |
| rpc/session-ownership | [R4-13](R4-13/README.md) | Live handles reject cross-session calls and duplication before side effects |
| rpc/pipelining-and-cloning | [R4-14](R4-14/README.md) | Pipeline results clone values and own independent capability references |
| rpc/property-observation | [R4-15](R4-15/README.md) | Each RpcProperty then/catch/finally starts a fresh GET while root promises remain cached |
| rpc/data-shape | [R4-16](R4-16/README.md) | Capability envelopes preserve own data keys and sparse array shape |
| dynamic-workers/admission | [H26-01](H26-01/README.md) | Unnamed Dynamic Worker loads dropped without dispose() are never refused by a live-count cap |
| rpc/stub-property-query | [H26-02](H26-02/README.md) | `name in` RPC stubs, promises, properties and Fetchers answers as workerd's wildcard property query |

Imported files are unchanged; IMPORT.json pins the fixes commit and hashes.
These assertions run against this branch's celld build; fixes present only on
the sibling branch can therefore expose real failures here. Failures are not
suppressed. CONTRACT.md describes the bounded HTTP adapter. The importer reads
every tree, blob and mode from the resolved commit, so concurrent fixes commits
cannot mix source versions in one import.
