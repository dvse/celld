// workerd keeps one I/O context per Durable Object (io/io-context.h). Object A parks a
// continuation on a promise that object B resolves (two objects of one class share an isolate).
// When it runs, A's original event has finished and the turn is B's; the continuation then calls
// another object. That call is A's I/O and must complete; celld used to drop it with its resolver.
import {DurableObject} from "cloudflare:workers";
let release;
const parked = new Promise((resolve) => { release = resolve; });
export class Worker2 extends DurableObject { work() { return "worked"; } }
export class Obj extends DurableObject {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === "/park") {
      void (async () => {
        await parked;
        const result = await this.env.W.getByName("w").work();
        this.ctx.storage.kv.put("result", result);
      })();
      return new Response("parked");
    }
    if (path === "/hold") { await new Promise((r) => setTimeout(r, 4000)); return new Response("held"); }
    if (path === "/release") { release(); return new Response("released"); }
    return new Response(String(this.ctx.storage.kv.get("result") ?? "none"));
  }
}
export default {
  async fetch(request, env) {
    const a = env.OBJ.getByName("a"), b = env.OBJ.getByName("b");
    await a.fetch("http://x/park");
    await new Promise((r) => setTimeout(r, 300));
    const hold = a.fetch("http://x/hold");
    await new Promise((r) => setTimeout(r, 300));
    await b.fetch("http://x/release");
    await hold;
    await new Promise((r) => setTimeout(r, 500));
    return new Response(await (await a.fetch("http://x/result")).text());
  },
};
