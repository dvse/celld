// A stateless request (/start) parks a continuation on a promise that a later request (/release)
// resolves, then returns. When the continuation runs, its own request has finished and the turn
// belongs to /release; the call it makes then is that running request's I/O (in workerd the
// continuation runs under the request holding the isolate). celld dropped it with its resolver,
// so the continuation never finished.
import {DurableObject} from "cloudflare:workers";
let release;
let result = "pending";
export class Store extends DurableObject { echo(x) { return "echo:" + x; } }
export default {
  async fetch(request, env, ctx) {
    const path = new URL(request.url).pathname;
    if (path === "/start") {
      const parked = new Promise((resolve) => { release = resolve; });
      void (async () => {
        await parked;
        result = await env.STORE.getByName("s").echo("late");
      })();
      return new Response("started");
    }
    if (path === "/release") {
      release?.();
      await new Promise((r) => setTimeout(r, 1500));
      return new Response("released");
    }
    return new Response(result);
  },
};
