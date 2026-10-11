// A WebSocket session loop started in a Durable Object's fetch event keeps doing
// I/O after that event ended (the Cap'n Web server pattern). Before patch 08 the
// cell RPC behind KV.get never ran and the session hung.
import {DurableObject, WorkerEntrypoint} from "cloudflare:workers";
const within = (promise) => Promise.race([promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error("timeout")), 4000))]);
export class Session extends DurableObject {
  async fetch() {
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    let waiting = null;
    const queue = [];
    server.addEventListener("message", (event) => {
      if (waiting) { const resolve = waiting; waiting = null; resolve(event.data); } else queue.push(event.data);
    });
    const next = () => queue.length ? Promise.resolve(queue.shift()) : new Promise((resolve) => waiting = resolve);
    (async () => {
      for (;;) {
        const mode = String(await next());
        let value;
        try {
          value = mode === "svc" ? await within(this.env.SELF.hello())
            : mode === "sql" ? this.ctx.storage.sql.exec("select 1 as x").one().x
            : await within(this.env.KV.get("k"));
        } catch (error) { value = String(error); }
        server.send(JSON.stringify({mode, value}));
      }
    })();
    return new Response(null, {status: 101, webSocket: client});
  }
}
export class Hello extends WorkerEntrypoint { hello() { return "hi"; } }
export default {
  async fetch(request, env, ctx) {
    if (new URL(request.url).pathname === "/put") { await env.KV.put("k", "v1"); return new Response("ok"); }
    return ctx.exports.Session.get(ctx.exports.Session.newUniqueId()).fetch(request);
  },
};
