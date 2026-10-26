# H26-02 — `name in stub` is false on celld RPC proxies

Found 2026-10-26 running Hyperbob main on a five-node celld fleet (lane
CELLD-EVOL). A published guest route (`/p/tunez`) rendered "Connection
interrupted": the page's socket opened, and its first `ready()` call was
rejected with "RPC stub used after being disposed."

Hyperbob's Publication Gatekeeper lease hands every resolution its own copy of
the identity it retains (`packages/publication-gatekeeper/src/contracts.ts`,
`ActivePublicationLease.resolveForAction`):

    const identity = this.identity !== null && "dup" in this.identity
      ? this.identity.dup() : this.identity;

celld's RPC stubs are Proxies with no `has` trap, so `"dup" in stub` is false.
The lease handed out its own identity stub, the socket opener disposed that
first resolution, and the next resolution used the disposed stub.

workerd exposes RPC members through a JSG wildcard property: a non-masking,
strings-only V8 named interceptor whose query callback reports a name present
whenever the wildcard getter answers it (`src/workerd/jsg/resource.h:1219-1259`).
`JsRpcStub::getRpcMethod` and `Fetcher::getRpcMethodInternal` answer every name
but `then` (`src/workerd/api/worker-rpc.c++:1817-1824`, `src/workerd/api/http.c++:2411-2419`);
`JsRpcPromise`/`JsRpcProperty` answer every name and also define `then`
(`src/workerd/api/worker-rpc.h:441-447`, `558-569`). `Symbol.dispose` comes from
`JSG_DISPOSE`, which `JsRpcStub` and `JsRpcPromise` declare and `Fetcher` (a
Durable Object stub or service binding) does not.

The fixture records `in` for each probed name on a Durable Object stub, a
`ctx.exports` entrypoint, an RPC promise and property, a received stub and its
dup, then replays the lease pattern. `expected.json` is stock workerd
1.20261010.1's observation. Before the fix celld answered false for every RPC
name and the second resolution failed with "RPC stub used after being
disposed."; after it, celld matches workerd exactly.

Run `python3 run.py` with CELLD_BIN, WORKERD_BIN, CELLD_ESBUILD,
CELLD_TEST_RUNTIME and a fresh CELLD_TEST_ARTIFACTS.
