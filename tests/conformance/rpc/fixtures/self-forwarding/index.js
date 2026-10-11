// The Hyperbob executeCode `self` chain: the kernel's Overseer mints
// ctx.exports.SelfLoop({props}) (a persistent loopback service), hands it to the code-mode runner
// (another script), whose code passes it to the Interplanetary Portal (a third script). The
// Portal gives it back to the Overseer's approval queue, which stores it durably and later calls
// it. workerd carries a ctx.exports stub through every hop as one service capability that keeps
// its origin, persistence and props (api/http.c++ Fetcher::serialize, channel-token.capnp).
import {DurableObject, WorkerEntrypoint} from "cloudflare:workers";
export class SelfLoop extends WorkerEntrypoint {
  async replied(text) {
    const overseer = this.ctx.exports.Overseer.getByName(this.ctx.props.overseer);
    return await overseer.record(`${this.ctx.props.chat}:${text}`);
  }
}
export class Overseer extends DurableObject {
  async run() {
    const self = this.ctx.exports.SelfLoop({props: {overseer: "o", chat: 7}});
    return await this.env.RUNNER.run({self, overseer: "o"});
  }
  // The Worker Loader executeCode engine: the code imports RpcTarget from cloudflare:workers and
  // gets `self` and the Portal binding from its loader env.
  async runLoaded() {
    const self = this.ctx.exports.SelfLoop({props: {overseer: "o", chat: 8}});
    const worker = this.env.LOADER.get("code-" + Date.now(), () => ({
      compatibilityDate: "2026-08-14",
      mainModule: "main.js",
      // The executeCode shape: the main module imports only WorkerEntrypoint, and the
      // authored module, a second module, imports RpcTarget itself.
      modules: {"main.js": `
        import {WorkerEntrypoint} from "cloudflare:workers";
        import authored from "./user.js";
        export default class extends WorkerEntrypoint {
          async run(self) { return await authored(self, this.env); }
        }`, "user.js": `
        import {RpcTarget} from "cloudflare:workers";
        class Probe extends RpcTarget {}
        export default async function (self, env) {
          const kind = typeof RpcTarget + ":" + (new Probe() instanceof RpcTarget);
          return kind + ":" + await env.PORTAL.messagePlanetBob({prompt: "hi"}, self, "o");
        }`},
      env: {PORTAL: this.env.PORTAL},
      globalOutbound: null,
    }));
    return await worker.getEntrypoint().run(self);
  }
  async bindHook(callback) {
    await this.ctx.storage.put("hook", callback);
    return "bound";
  }
  async fire(text) {
    const hook = await this.ctx.storage.get("hook");
    return await hook.replied(text);
  }
  record(line) { this.ctx.storage.kv.put("last", line); return "recorded " + line; }
}
export default {
  async fetch(request, env, ctx) {
    const overseer = ctx.exports.Overseer.getByName("o");
    const out = {};
    try {
      if (new URL(request.url).pathname === "/loaded") {
        out.run = await overseer.runLoaded();
        out.fire = await overseer.fire("loaded bob says hi");
      } else {
        out.run = await overseer.run();
        out.fire = await overseer.fire("planet bob says hi");
      }
    } catch (error) { out.error = String(error?.message ?? error); }
    return Response.json(out);
  },
};
