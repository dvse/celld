// Checks patch 12: RPC promises and object results are disposable, as in workerd, so
// `using pending = stub.method()` and `using result = await stub.method()` work.
import {DurableObject, RpcTarget, WorkerEntrypoint} from "cloudflare:workers";
class Session extends RpcTarget { hello(name) { return "hello " + name; } }
export class Box extends DurableObject { plain() { return {a: 1}; } session() { return new Session(); } }
export class Svc extends WorkerEntrypoint { plain() { return {b: 2}; } }
export default {
  async fetch(request, env, ctx) {
    const out = {};
    const box = ctx.exports.Box.getByName("x");
    try { using pending = box.plain(); out.doPromise = (await pending).a; } catch (e) { out.doPromise = String(e); }
    try { using result = await box.plain(); out.doResult = result.a; } catch (e) { out.doResult = String(e); }
    try { using pending = env.SVC.plain(); out.svcPromise = (await pending).b; } catch (e) { out.svcPromise = String(e); }
    try { using result = await env.SVC.plain(); out.svcResult = result.b; } catch (e) { out.svcResult = String(e); }
    // Pipelining through a Durable Object method result, as GatekeeperLoopback does.
    try { out.doPipeline = await box.session().hello("x"); } catch (e) { out.doPipeline = String(e); }
    try { const session = box.session(); const proxy = new Proxy(session, {}); out.doProxyPipeline = await proxy.hello("y"); } catch (e) { out.doProxyPipeline = String(e); }
    return Response.json(out);
  },
};
