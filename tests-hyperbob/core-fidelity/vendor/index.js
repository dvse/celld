// The vendor script of the core-fidelity fixture: a separate Worker, so the stub it returns
// crosses isolates through the live-capability transport, as Hyperbob's gatekeeper leases do.
import {RpcTarget, WorkerEntrypoint} from "cloudflare:workers";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
class Slow extends RpcTarget {
  async wait(ms) { await sleep(ms); return "waited:" + ms; }
  ping() { return "pong"; }
}
export class Vendor extends WorkerEntrypoint {
  mint() { return new Slow(); }
  async background() {
    this.ctx.waitUntil((async () => {
      await sleep(2000);
      await this.env.EVENTS.getByName("log").push("background-done");
    })());
    return "answered";
  }
}
export default { fetch() { return new Response("vendor"); } };
