// Before/after checks for four workerd behaviours:
//  D1  a live-capability call has no duration bound (workerd JS RPC has none);
//  D2  a stub returned by another script's stateless entrypoint keeps working after the pool
//      would have freed that isolate (workerd keeps a session's Worker while a
//      capability crosses it);
//  D3  static entrypoints and top-level Durable Objects start new restore chains
//      (ported from workerd api/tests/persistent-stubs-test.js
//      staticRestoreTargetStartsNewChain / topLevelDoRestoreTargetStartsNewChain;
//      restore events are logged in a Durable Object, because celld runs stateless
//      entrypoints and Durable Objects in different isolates);
//  W   an RPC call answers when its method returns; ctx.waitUntil work keeps
//      running afterwards (workerd js-rpc-test waitUntilWorks).
import {DurableObject, RpcTarget, WorkerEntrypoint, restore} from "cloudflare:workers";

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export class Events extends DurableObject {
  push(event) { const list = this.ctx.storage.kv.get("events") ?? []; list.push(event); this.ctx.storage.kv.put("events", list); }
  count(event) { return (this.ctx.storage.kv.get("events") ?? []).filter((e) => e === event).length; }
  reset() { this.ctx.storage.kv.delete("events"); }
}
const log = (ctx, event) => ctx.exports.Events.getByName("log").push(event);

export class Holder extends DurableObject {
  async keep() { this.kept = await this.env.VENDOR.mint(); return "kept"; }
  async use() { return this.kept === undefined ? "nothing kept" : await this.kept.ping(); }
  async slow(ms) { const stub = await this.env.VENDOR.mint(); return await stub.wait(ms); }
}

export class StaticTarget extends WorkerEntrypoint {
  ping(value) { return `${this.ctx.props.prefix}:${value}`; }
}
export class StaticRedirect extends WorkerEntrypoint {
  async makeInner(id) { return await this.ctx.restore({kind: "static-inner", id}); }
  async [restore](params) {
    await log(this.ctx, `static:${params.kind}:${params.id}`);
    return this.ctx.exports.StaticTarget({props: {prefix: `static:${params.id}`}});
  }
}
export class TopRedirectDo extends DurableObject {
  async makeInner(id) { return await this.ctx.restore({kind: "top-do-inner", id}); }
  async [restore](params) {
    await log(this.ctx, `top-do:${params.kind}:${params.id}`);
    return this.ctx.exports.StaticTarget({props: {prefix: `top-do:${params.id}`}});
  }
}
export class Store extends DurableObject {
  async get(name) { return await this.ctx.storage.get(name); }
  async put(name, value) { await this.ctx.storage.put(name, value); }
}
export class Source extends WorkerEntrypoint {
  async staticRedirectSecurityRoundTrip(id, value) {
    const store = this.ctx.exports.Store.getByName(`static-redirect-${id}`);
    const redirected = await this.ctx.restore({kind: "static-redirect", id, secret: "source-only"});
    const inner = await redirected.makeInner(id);
    await store.put("stub", inner);
    const loaded = await store.get("stub");
    return await loaded.ping(value);
  }
  async topLevelDoRedirectSecurityRoundTrip(id, value) {
    const store = this.ctx.exports.Store.getByName(`top-do-redirect-${id}`);
    const redirected = await this.ctx.restore({kind: "top-do-redirect", id, secret: "source-only"});
    const inner = await redirected.makeInner(id);
    await store.put("stub", inner);
    const loaded = await store.get("stub");
    return await loaded.ping(value);
  }
  async [restore](params) {
    await log(this.ctx, `${params.kind}:${params.id}`);
    if (params.kind === "static-redirect")
      return this.ctx.exports.StaticRedirect({props: {sourceId: params.id}});
    if (params.kind === "top-do-redirect")
      return this.ctx.exports.TopRedirectDo.get(this.ctx.exports.TopRedirectDo.idFromName(`redirect-${params.id}`));
    throw new Error("unknown kind");
  }
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const events = ctx.exports.Events.getByName("log");
    const holder = ctx.exports.Holder.getByName("holder");
    const out = {};
    try {
      switch (url.pathname) {
        case "/restore": {
          await events.reset();
          out.static = await ctx.exports.Source.staticRedirectSecurityRoundTrip("worker", "value");
          out.staticRedirectRestores = await events.count("static-redirect:worker");
          out.staticInnerRestores = await events.count("static:static-inner:worker");
          out.topDo = await ctx.exports.Source.topLevelDoRedirectSecurityRoundTrip("actor", "value");
          out.topDoRedirectRestores = await events.count("top-do-redirect:actor");
          out.topDoInnerRestores = await events.count("top-do:top-do-inner:actor");
          break;
        }
        case "/waituntil": {
          await events.reset();
          const started = Date.now();
          out.answer = await env.VENDOR.background();
          out.answeredFast = Date.now() - started < 1500;
          out.doneAtAnswer = await events.count("background-done");
          await sleep(3500);
          out.doneLater = await events.count("background-done");
          break;
        }
        case "/keep": out.keep = await holder.keep(); break;
        case "/use": out.use = await holder.use(); break;
        case "/slow": out.slow = await holder.slow(Number(url.searchParams.get("ms"))); break;
      }
    } catch (error) { out.error = String(error?.message ?? error); }
    return Response.json(out);
  },
};
