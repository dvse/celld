// Ports of workerd RPC member rules (api/worker-rpc.c++, api/tests/js-rpc-test.js):
//  D13 a plain-object entrypoint exposes only its own members, and the reserved names;
//  D14 arrays are not walkable pipeline intermediates;
//  D15 transient targets reserve `dup` and `constructor`;
//  D6  a top-level plain-object result's disposer runs exactly once, on dispose() or when
//      the caller's context ends;
//  D17 disposing an RPC promise is idempotent and the promise is unusable afterwards;
//  D21 pipelined property paths stop at depth 64.
import {RpcTarget, WorkerEntrypoint} from "cloudflare:workers";
let disposals = 0;
class Result extends RpcTarget { [Symbol.dispose]() { disposals++; } }
class Target extends RpcTarget {
  get list() { return [new Result()]; }
  dup() { return "own dup"; }
  make() { return {value: 1, [Symbol.dispose]() { disposals++; }}; }
}
export class Api extends WorkerEntrypoint {
  target() { return new Target(); }
}
const outcome = async (fn) => {
  try { return "ok:" + JSON.stringify(await fn()); } catch (e) { return "err:" + e.message; }
};
export default {
  hello(arg) { return "hello " + arg; },
  async fetch(request, env) {
    if (new URL(request.url).pathname === "/count") return Response.json({disposals});
    const out = {};
    out.objectOwn = await outcome(() => env.SELF.hello("x"));
    out.objectInherited = await outcome(() => env.SELF.getRpcMethodForTestOnly("toString")());
    out.objectReserved = await outcome(() => env.SELF.alarm());
    const target = await env.API.target();
    out.transientDup = await outcome(() => target.dup());
    out.transientConstructor = await outcome(() => target.constructor());
    out.arrayPath = await outcome(() => target.list[0].toString());
    let node = target.make;
    out.depth = await outcome(async () => { for (let i = 0; i < 70; i++) node = node.x; return "built"; });
    disposals = 0;
    const pending = target.make();
    await pending;
    pending[Symbol.dispose]();
    pending[Symbol.dispose]();
    await new Promise((r) => setTimeout(r, 50));
    out.afterDispose = await outcome(() => pending.value);
    out.disposals = disposals;
    // Never disposed: workerd runs the disposer when the caller's context ends.
    await target.make();
    return Response.json(out);
  },
};
