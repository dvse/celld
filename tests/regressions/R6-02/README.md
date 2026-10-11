# R6-02 — loader props envelope

Dynamic Worker calls with absent, empty and ordinary props, repeated persistent-RPC props, HTTP controls and props forwarded through a service. Native capability_packet tests cover raw V8, loader-wrapped V8, packets and wrapped packets, malformed headers and queue cancellation while source buffers remain reachable.

Workerd worker-loader.c++:26–48 uses Frankenvalue. Contrary to the review's proposed positive test, transient RpcTargets/stubs and streams are rejected (worker-rpc.c++:783–790,1825–1830; streams/readable.c++:708–713). The test requires those rejections and uses a ctx.restore() channel for repeated positive calls. Reusable props snapshot channels without transferring a live incarnation. Storage-only opt-in checks remain on storage serialization.

The panic is a 52d3131 regression: def239b is a passing historical control for plain props, not a failing baseline for this newly introduced panic. Baseline still fails the expanded transient-props conformance case. The reviewed bd65da5 must fail; fixed runtime and workerd must pass. Do not manufacture a baseline failure by asserting new implementation symbols.

The runner uses a fresh MinIO bucket and explicit public/internal listeners on assigned offsets 0, 1, 6 and 7. Earlier diagnostic runs used celld dev, whose supervisor selects an ephemeral internal port; final conformance runs use this bounded launcher.
