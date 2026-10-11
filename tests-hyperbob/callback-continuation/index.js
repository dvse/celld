// The Workshop session shape (edge ApiSession → Planet Overseer on another node): Session gives
// Overseer a callback stub; Overseer calls it. The callback runs on Session's node as its own
// capability event, starts work that waits for a later Session request, and returns at once.
// When that later request resolves it, the work makes a call (I/O) whose owner is the finished
// callback event. workerd runs it in the I/O context current at that moment (or keeps the
// exporting context alive); celld dropped it with its resolver, so the work never finished.
import {DurableObject, RpcTarget} from "cloudflare:workers";
class Callback extends RpcTarget {
  constructor(session) { super(); this.session = session; }
  notify(text) {
    void (async () => {
      await new Promise((resolve) => { this.session.release = resolve; });
      const echoed = await this.session.env.OVERSEER.getByName("o").echo(text);
      this.session.ctx.storage.kv.put("result", echoed);
    })();
    return "notified";
  }
}
export class Overseer extends DurableObject {
  async subscribe(callback) { return await callback.notify("hello"); }
  echo(x) { return "echo:" + x; }
}
export class Session extends DurableObject {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === "/subscribe")
      return new Response(await this.env.OVERSEER.getByName("o").subscribe(new Callback(this)));
    if (path === "/release") { this.release?.(); await new Promise((r) => setTimeout(r, 1500)); return new Response("released"); }
    return new Response(String(this.ctx.storage.kv.get("result") ?? "none"));
  }
}
export default {
  async fetch(request, env) { return env.SESSION.getByName("s").fetch(request); },
};
