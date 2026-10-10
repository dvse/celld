// An op that needs its own isolate (opening a facet of the script's own class takes a turn on
// the root's isolate) must not be granted that turn while the event that owns it waits for
// its own turn without polling it. Workerd runs each continuation on its own and each takes
// the isolate lock for its own turn, so the facet call below simply completes there.
//
// Sequence: /race starts a facet call and a 150 ms timer, then holds the isolate for ~100 ms.
// /hold arrives during that turn and holds the isolate for ~300 ms more, so the facet open
// queues for the isolate behind it. The timer fires while /hold runs, so the /race event's
// driver queues for its next turn behind its own facet open. Before the fix, /hold's release
// granted the turn to the unpolled facet open, and the isolate admitted no turn again:
// /race, and every later event of the object, waited forever (Tunez Celld 4, planet-2).
// The clock does not advance inside a turn, as in workerd, so the isolate is held by a fixed
// amount of work rather than by watching Date.now().
import {DurableObject} from "cloudflare:workers";
// About 20 ns per iteration on the test host: 5e6 is ~100 ms.
const burn = (n) => { let x = 0; for (let i = 0; i < n; i++) x = (x + i * 2654435761) % 1000003; return x; };
export class Child extends DurableObject {
  ping() { return "pong"; }
}
export class Root extends DurableObject {
  child() { return this.ctx.facets.get("child", () => ({class: this.ctx.exports.Child})); }
  async race() {
    const call = this.child().ping();
    const timer = new Promise((resolve) => setTimeout(resolve, 150));
    burn(5e6);
    await timer;
    return await call;
  }
  hold(n) { burn(n); return "held"; }
  probe() { return "alive"; }
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const root = env.ROOT.getByName("root");
    if (url.pathname === "/race") return Response.json(await root.race());
    if (url.pathname === "/hold") return Response.json(await root.hold(Number(url.searchParams.get("n") ?? 1.5e7)));
    if (url.pathname === "/probe") return Response.json(await root.probe());
    return new Response("not found", {status: 404});
  },
};
