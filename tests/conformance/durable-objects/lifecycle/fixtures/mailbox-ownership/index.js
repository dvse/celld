// An op a retired event of object A started, handed through the mailbox to a running event of A,
// is A's I/O and must survive that recipient's cancellation. Workerd keeps an actor's tasks in
// its one I/O context: "In Actors, we treat all tasks as wait-until tasks, because it's
// perfectly legit to start a task under one request and then expect some other request to
// handle it later" (io/io-context.c++:548-555).
//
// A parks a continuation on a promise that B resolves (one isolate). When it runs, A's original
// event has finished and the turn is B's, so the continuation's call to W is handed to A's
// running /hold event. The client of /hold then disconnects, which cancels /hold while the call
// to W is still in flight. Before the fix, the handed op was /hold's own and was dropped with its
// resolver: the continuation never resumed and /result answered "none".
import {DurableObject} from "cloudflare:workers";
let release;
const parked = new Promise((resolve) => { release = resolve; });
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
export class Worker2 extends DurableObject { async work() { await sleep(3000); return "worked"; } }
export class Obj extends DurableObject {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === "/park") {
      this.ctx.storage.kv.delete("result");
      void (async () => {
        await parked;
        const result = await this.env.W.getByName("w").work();
        this.ctx.storage.kv.put("result", result);
      })();
      return new Response("parked");
    }
    if (path === "/hold") { await sleep(6000); return new Response("held"); }
    if (path === "/release") { release(); return new Response("released"); }
    return new Response(String(this.ctx.storage.kv.get("result") ?? "none"));
  }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const object = env.OBJ.getByName(path === "/release" ? "b" : "a");
    return object.fetch(`http://x${path}`);
  },
};
