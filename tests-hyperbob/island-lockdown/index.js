// Runs Hyperbob's Island lockdown module (gadget-runtime-wrapper.ts GADGET_LOCKDOWN_MODULE,
// copied verbatim) in a celld Worker, then exercises the host surface it pins.
import * as host from "./lockdown.js";
export default {
  async fetch() {
    const out = {exports: Object.keys(host).sort()};
    const step = async (name, fn) => { try { out[name] = await fn(); } catch (e) { out[name] = "ERR " + String(e); } };
    await step("abort", () => { const c = new host.HostAbortController(); c.abort(); return c.signal.aborted; });
    await step("timeout", () => new Promise(r => host.HostSetTimeout(() => r("fired"), 5)));
    await step("clone", () => host.HostStructuredClone({a: [1, 2]}).a.length);
    await step("uuid", () => typeof host.HostCrypto.randomUUID());
    await step("encode", () => new host.HostTextEncoder().encode("hi").length);
    await step("response", async () => (await new Response("ok").text()));
    await step("errorName", () => { class E extends Error { constructor() { super("m"); this.name = "E"; } } return new E().name; });
    await step("frozenArray", () => Object.isFrozen(Array.prototype));
    return Response.json(out);
  },
};
