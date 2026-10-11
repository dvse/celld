// A stateless request (/start) parks a continuation on a promise that a later request (/release)
// resolves, then returns. When the continuation runs, its own request has finished. workerd
// cancels it ("A promise was resolved or rejected from a different request context … have been
// canceled"), so /result stays "pending". celld runs the reaction, but its I/O belongs to the
// finished request and is refused ("The execution context which hosts this callback is no longer
// running."), so the continuation does not complete either and /result stays "pending". celld logs
// no warning.
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
