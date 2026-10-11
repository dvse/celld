// Workerd's event limits, checked with CELLD_HANDLER_BUDGET_S=5 so the old wall-clock cap shows
// in seconds rather than minutes.
//
// - An event that awaits I/O has no wall-clock limit: the limit enforcer workerd runs with
//   enforces none (server/server.c++:4779-4817). Only an alarm handler has one, 15 minutes
//   (getAlarmLimit, server/server.c++:4796-4798). celld failed both a stateless request and a
//   Durable Object call at the handler budget ("handler exceeded 300s budget", Celld 4).
// - A Durable Object request awaiting a promise that a later event of the same object resolves
//   is not hung while that object has other work: workerd keeps one IoContext per actor
//   (io/io-context.h:257-259). A stateless request awaiting nothing still is.
// - Imported waitUntil() inside a Durable Object is accepted from a continuation that runs after
//   its event answered: the actor's IoContext is current there (api/workers-module.c++:55-59,
//   io/io-context.c++:1593-1605). celld threw "Disallowed operation called within global scope."
// - A call on a live capability (an RpcTarget a session holds) that awaits something only a later
//   call of the same session settles is not hung: the session ends only when no capability
//   crosses it (api/worker-rpc.c++:3442-3449).
import {DurableObject, RpcTarget, waitUntil} from "cloudflare:workers";
class Gate extends RpcTarget {
  #release;
  #opened = new Promise((resolve) => { this.#release = resolve; });
  async wait() { await this.#opened; return "released"; }
  open() { this.#release(); return "opened"; }
}
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const outcome = async (call) => {
  try { return await call(); } catch (error) { return `error: ${error?.message ?? error}`; }
};
export class Obj extends DurableObject {
  #release;
  async slowIo(ms) { await sleep(ms); return "io-done"; }
  async awaitRelease() { await new Promise((resolve) => { this.#release = resolve; }); return "released"; }
  release() { this.#release?.(); return "ok"; }
  start() {
    this.ctx.storage.kv.delete("waitUntil");
    (async () => {
      await sleep(200);
      try {
        waitUntil(sleep(10));
        this.ctx.storage.kv.put("waitUntil", "accepted");
      } catch (error) {
        this.ctx.storage.kv.put("waitUntil", `error: ${error?.message ?? error}`);
      }
    })();
    return "started";
  }
  result() { return this.ctx.storage.kv.get("waitUntil") ?? "pending"; }
  gate() { return new Gate(); }
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const obj = env.OBJ.getByName("limits");
    const ms = Number(url.searchParams.get("ms") ?? 8000);
    switch (url.pathname) {
      case "/stateless-io": await sleep(ms); return Response.json("io-done");
      case "/do-io": return Response.json(await outcome(() => obj.slowIo(ms)));
      case "/do-await": return Response.json(await outcome(() => obj.awaitRelease()));
      case "/do-release": return Response.json(await obj.release());
      case "/stateless-nothing": await new Promise(() => {}); return Response.json("unreachable");
      case "/session-wait": {
        // Its own object, so no other event of the object is in flight.
        const gate = await env.OBJ.getByName("session").gate();
        const waiting = outcome(() => gate.wait());
        await sleep(ms);
        await gate.open();
        return Response.json(await waiting);
      }
      case "/start": return Response.json(await obj.start());
      case "/result": return Response.json(await obj.result());
    }
    return new Response("not found", {status: 404});
  },
};
