// A Durable Object keeps a dup() of a capability it received from a Durable Object on another
// node, disposes the original, and uses the dup in a later event. In workerd the dup is an
// independent reference owned by the actor (io/io-context.h: one IoContext per actor), so it
// keeps working after the event that made it ended.
import {DurableObject, RpcTarget, WorkerEntrypoint} from "cloudflare:workers";
class Lease extends RpcTarget {
  resolve(x) { return "resolved:" + x; }
}
export class Gate extends DurableObject {
  redeem() { return new Lease(); }
}
// A stateless entrypoint (the Hyperbob Publication Gatekeeper shape) that wraps the Durable
// Object's capability in its own RpcTarget and returns it inside a plain object.
class Wrapper extends RpcTarget {
  constructor(inner) { super(); this.inner = inner; }
  async resolve(x) { return "wrapped:" + await this.inner.resolve(x); }
}
// The lazy shape: the wrapper keeps a Durable Object stub made in the entrypoint call and calls
// it only when the caller uses the lease, after that call returned.
class LazyWrapper extends RpcTarget {
  constructor(stub) { super(); this.stub = stub; }
  async resolve(x) {
    using lease = await this.stub.redeem();
    return "lazy:" + await lease.resolve(x);
  }
}
export class Gateway extends WorkerEntrypoint {
  async openLease(kind) {
    if (kind === "lazy-env") return {lease: new LazyWrapper(this.env.GATE.getByName("g"))};
    if (kind === "lazy-exports") return {lease: new LazyWrapper(this.ctx.exports.Gate.getByName("g"))};
    const inner = await this.env.GATE.getByName("g").redeem();
    return {lease: new Wrapper(inner), note: "plain"};
  }
}
const timed = (promise) => Promise.race([promise,
  new Promise((resolve) => setTimeout(() => resolve("timeout"), 10000))]);
export class Planet extends DurableObject {
  async keep() {
    const lease = await this.env.GATE.getByName("g").redeem();
    this.kept = lease.dup();
    lease[Symbol.dispose]();
    return "kept";
  }
  async keepWrapped(kind) {
    const redeemed = await this.env.GATEWAY.openLease(kind);
    this.kept = redeemed.lease.dup();
    redeemed.lease[Symbol.dispose]();
    return "kept";
  }
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (request.headers.get("upgrade") === "websocket") return this.socket();
    return new Response(await (path === "/keep" ? this.keep() : this.keepWrapped(path.slice(1))));
  }
  // The Hyperbob published-socket shape: the lease is kept from the upgrade's fetch, and each
  // message runs a chain of awaits (a local RPC hop, a timer) before it calls the lease.
  async socket() {
    const redeemed = await this.env.GATEWAY.openLease("lazy-env");
    const lease = redeemed.lease.dup();
    redeemed.lease[Symbol.dispose]();
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    server.addEventListener("message", (event) => {
      void (async () => {
        try {
          await this.env.GATE.getByName("g").redeem();
          await new Promise((resolve) => setTimeout(resolve, 200));
          server.send(String(await timed(lease.resolve(String(event.data)))));
        } catch (error) { server.send("error: " + error.message); }
      })();
    });
    return new Response(null, {status: 101, webSocket: client});
  }
  async use() {
    if (this.kept === undefined) return "nothing kept";
    try { return await timed(this.kept.resolve("later")); }
    catch (error) { return "error: " + error.message; }
  }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    const planet = env.PLANET.getByName(path.split("/")[1]);
    if (path === "/fetch/keep") return planet.fetch("http://planet/keep");
    if (path === "/socket") return env.PLANET.getByName("socket").fetch(request);
    for (const kind of ["wrapped", "lazy-env", "lazy-exports"])
      if (path === "/" + kind + "/keep") return planet.fetch("http://planet/" + kind);
    if (path === "/rpc/keep") return new Response(await planet.keep());
    return new Response(await planet.use());
  },
};
