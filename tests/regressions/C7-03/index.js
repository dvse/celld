// C7-03: stubs a stateless request creates or receives belong to that request. Another request,
// while the first is live or after it finished, is refused them with the cross-request error:
// a ctx.exports stub carrying props, a Durable Object stub it created, and one it received over
// RPC. Bindings of the isolate (env service bindings, ctx.exports entrypoints, namespaces) and a
// Durable Object's own stubs across its events stay usable. Passing such a stub on (an RPC
// argument or result, nested, a Durable Object's storage) is using it: the other request is
// refused at serialization. Another Durable Object in the same isolate is refused with the
// "different Durable Object" wording; a stub another script (Y) returned is bound to the request
// that received it, and so is a Durable Object class carrying props (ctx.exports.D({props}), or
// one Y returned alone or in {class}), which another request may not start as a facet; so are
// Worker Loader stubs and entrypoints (with props), and an actor's facet stubs; a stub made by code that resumed after its request ended
// is usable by nobody (workerd never runs that code).
import {WorkerEntrypoint, DurableObject} from 'cloudflare:workers';
export class Ent extends WorkerEntrypoint {
  fetch() { return new Response(null, {status: 204}); }
  who() { return 'props:' + JSON.stringify(this.ctx.props); }
  doStub() { return this.env.D.getByName('z'); }
  echo(x) { return x; }
}
export class D extends DurableObject {
  fetch() { return new Response(null, {status: 204}); }
  n() { return 'd-ok'; }
  who() { return 'd-props:' + JSON.stringify(this.ctx.props); }
  // Starts a facet of the class it is given (a DurableObjectClass, possibly carrying props).
  async facet(cls) { return await this.ctx.facets.get('f' + Math.random(), () => ({class: cls})).who(); }
  // A Durable Object keeps a stub it made in one event and uses it in later events.
  async keep() { this.peer ??= this.env.D.getByName('peer'); return await this.peer.n(); }
  echo(x) { return x; }
  stash(x) { this.s = x; return 'stashed'; }
  async callStash() { return await this.s.who(); }
  // A loader entrypoint and a facet stub this actor makes, kept in a module global.
  mkHandles() {
    shared.ep = loader(this.env).getEntrypoint('E', {props: {user: this.ctx.id.name}});
    shared.facet = this.ctx.facets.get('kept', () => ({class: this.ctx.exports.D({props: {user: 'facet-owner'}})}));
    return 'made';
  }
  async useHandles() {
    return await settle({ep: run(() => shared.ep.who()), facet: run(() => shared.facet.who())});
  }
  // Actors of one class can share an isolate: a module global carries a stub across them.
  grab() { shared.d = this.env.D.getByName('q'); return 'grabbed'; }
  async foreign() {
    return await settle({
      direct: run(() => shared.d.n()),
      storage: run(async () => { await this.ctx.storage.put('k', shared.d); return await (await this.ctx.storage.get('k')).n(); }),
      echo: run(async () => await (await this.env.D.getByName('r').echo(shared.d)).n()),
    });
  }
}
const shared = {};
// A dynamic Worker for the loader rows.
const CODE = `import {WorkerEntrypoint} from 'cloudflare:workers';
export class E extends WorkerEntrypoint { who() { return 'ld-props:' + JSON.stringify(this.ctx.props); } fetch() { return new Response('ld-fetch:' + JSON.stringify(this.ctx.props)); } }
export default { fetch() { return new Response('ld'); } };`;
const loader = env => env.LOADER.get('w1', () => ({compatibilityDate: '2026-08-14', mainModule: 'm.js', modules: {'m.js': CODE}}));
const held = {};
const run = async f => { try { return 'ok:' + await f(); } catch (e) { return 'refused:' + (e.message.includes('different request') ? 'cross-request' : e.message.includes('different Durable Object') ? 'cross-object' : e.message.slice(0, 90)); } };
const useAll = () => ({
  props: run(() => held.props.who()), propsFetch: run(async () => (await held.props.fetch('http://x/')).status),
  ys: run(() => held.ys.who()),
  ldStub: run(() => held.ldr.getEntrypoint('E').who()),
  ldEp: run(() => held.ep.who()), ldEpFetch: run(async () => await (await held.ep.fetch('http://x/')).text()), ysFetch: run(async () => (await held.ys.fetch('http://x/')).status),
  doStub: run(() => held.doStub.n()), doFetch: run(async () => (await held.doStub.fetch('http://x/')).status),
  rpcDo: run(() => held.rpcDo.n()),
  svc: run(() => held.svc.who()), exports: run(() => held.exports.who()), ns: run(() => held.ns.getByName('z').n()),
});
// Passing the held stubs on, from a request that may not own them.
const launder = (env, ctx, tag) => ({
  viaExports: run(async () => await (await ctx.exports.Ent.echo(held.props)).who()),
  viaSelf: run(async () => await (await env.SELF.echo(held.props)).who()),
  viaObject: run(async () => await (await env.D.getByName('x').echo(held.props)).who()),
  stashed: run(async () => { await env.D.getByName('stash-' + tag).stash(held.props); return await env.D.getByName('stash-' + tag).callStash(); }),
  nested: run(async () => await (await ctx.exports.Ent.echo({a: [held.props]})).a[0].who()),
  cls: run(() => env.D.getByName('fc-' + tag).facet(held.cls)),
  clsViaExports: run(async () => await env.D.getByName('fe-' + tag).facet(await ctx.exports.Ent.echo(held.cls))),
  yCls: run(() => env.D.getByName('fy-' + tag).facet(held.yCls)),
  yBag: run(() => env.D.getByName('fb-' + tag).facet(held.yBag.class)),
  yClsViaExports: run(async () => await env.D.getByName('fx-' + tag).facet(await ctx.exports.Ent.echo(held.yCls))),
  ldEpViaExports: run(async () => await (await ctx.exports.Ent.echo(held.ep)).who()),
  ysViaExports: run(async () => await (await ctx.exports.Ent.echo(held.ys)).who()),
  ysViaY: run(async () => await (await env.Y.echo(held.ys)).who()),
  doViaExports: run(async () => await (await ctx.exports.Ent.echo(held.doStub)).n()),
  doViaObject: run(async () => await (await env.D.getByName('x').echo(held.doStub)).n()),
  doInMap: run(async () => await (await ctx.exports.Ent.echo(new Map([['k', held.rpcDo]]))).get('k').n()),
});
const late = {};
const settle = async o => Object.fromEntries(await Promise.all(Object.entries(o).map(async ([k, v]) => [k, await v])));
export default {
  async fetch(req, env, ctx) {
    const p = new URL(req.url).pathname;
    if (p === '/hold') {
      held.props = ctx.exports.Ent({props: {user: 'alice'}});
      held.doStub = env.D.getByName('z');
      held.rpcDo = await ctx.exports.Ent.doStub();
      held.ys = await env.Y.mint('alice');
      held.cls = ctx.exports.D({props: {user: 'alice'}});
      held.ldr = loader(env); held.ep = held.ldr.getEntrypoint('E', {props: {user: 'alice'}});
      held.yCls = await env.Y.mintCls('alice'); held.yBag = await env.Y.mintBag('alice');
      held.svc = env.SELF; held.exports = ctx.exports.Ent; held.ns = env.D;
      // Passing a loader entrypoint on is refused by workerd even here (it is not
      // transferable); celld refuses it when the receiver calls it. Not compared.
      const ownLaunder = launder(env, ctx, 'own'); ownLaunder.ldEpViaExports.catch?.(() => {}); delete ownLaunder.ldEpViaExports;
      held.own = await settle({...useAll(), ...ownLaunder});
      await new Promise(r => { held.release = r; setTimeout(r, 8000); });
      return new Response('held');
    }
    if (p === '/held') return new Response(held.own ? 'yes' : 'no');
    if (p === '/own') return Response.json(held.own);
    if (p === '/use') { const out = await settle({...useAll(), ...launder(env, ctx, 'use')}); held.release?.(); return Response.json(out); }
    if (p === '/later') return Response.json(await settle({...useAll(), ...launder(env, ctx, 'later')}));
    if (p === '/actors') { await env.D.getByName('a').grab(); return Response.json(await env.D.getByName('b').foreign()); }
    // Loader entrypoint and facet stub made by actor 'h1': usable by it in later events, refused to 'h2'.
    if (p === '/handles') { await env.D.getByName('h1').mkHandles();
      return Response.json({same: await env.D.getByName('h1').useHandles(), other: await env.D.getByName('h2').useHandles()}); }
    // A continuation parked by /park resumes, after /park ended, when /wake releases it.
    if (p === '/park') {
      new Promise(r => { late.wake = r; }).then(() => {
        late.props = ctx.exports.Ent({props: {user: 'parked'}}); late.d = env.D.getByName('pk'); });
      return new Response('parked');
    }
    if (p === '/wake') { late.wake?.(); await new Promise(r => setTimeout(r, 100)); return new Response('woken'); }
    if (p === '/late') {
      // Never created (workerd cancels the continuation) or refused: either way unusable.
      const unusable = async f => { const r = await run(f); return r.startsWith('refused:cross-request') || r.includes('undefined') ? 'unusable' : r; };
      return Response.json(await settle({props: unusable(() => late.props.who()), d: unusable(() => late.d.n())}));
    }
    if (p === '/keep') { const s = env.D.getByName('keeper'); return new Response(await s.keep() + ',' + await s.keep()); }
    return new Response('c7-03');
  },
};
