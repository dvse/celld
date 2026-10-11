// C7-02: what a stateless fetch handler receives over RPC belongs to its request, including the
// turn that settles it and the response body the runtime pumps after it returns; another live
// request may not use it.
import {WorkerEntrypoint, RpcTarget} from 'cloudflare:workers';
const enc = new TextEncoder();
class T extends RpcTarget { n(i) { return 't' + i + ';'; } }
export class Ent extends WorkerEntrypoint {
  n(i) { return 'e' + i + ';'; }
  target() { return new T(); }
  stream() { let i = 0; return new ReadableStream({pull(c) { c.enqueue(enc.encode('s' + i + ';')); if (++i == 3) c.close(); }}); }
  // The callee's own first turn returns a stream that reads an RPC object the callee received.
  viaSync() { const tp = this.ctx.exports.Ent.target(); return body(async i => (await tp).n(i)); }
  async viaAsync() { const t = await this.ctx.exports.Ent.target(); return body(i => t.n(i)); }
  async viaRpcStream() { return await this.ctx.exports.Ent.stream(); }
}
const kind = e => e.message.includes('different request') ? 'cross-request' : 'other: ' + e.message;
// A body whose pull() calls through an RPC object the handler received.
const body = call => { let i = 0; return new ReadableStream({async pull(c) {
  try { c.enqueue(enc.encode(await call(i))); }
  catch (e) { c.enqueue(enc.encode('ERR:' + kind(e))); c.close(); return; }
  if (++i == 3) c.close(); }}); };
const socket = target => {
  const [client, server] = Object.values(new WebSocketPair());
  server.accept();
  server.addEventListener('message', async e => {
    try { server.send(await (await target).n(e.data)); } catch (err) { server.send('ERR:' + kind(err)); }
  });
  return new Response(null, {status: 101, webSocket: client});
};
const held = {};
export default {
  fetch(req, env, ctx) {
    const p = new URL(req.url).pathname;
    const stub = ctx.exports.Ent;
    // Returned synchronously: the body is pumped from the turn that settles the request.
    if (p === '/sync-exports') return new Response(body(i => stub.n(i)));
    if (p === '/sync-target-promise') { const tp = stub.target(); return new Response(body(async i => (await tp).n(i))); }
    if (p === '/sync-pipelined') { const tp = stub.target(); return new Response(body(i => tp.n(i))); }
    // A stateless WebSocket whose message listener calls an RpcTarget the handler received.
    if (p === '/ws-sync') return socket(stub.target());
    if (p === '/sync-rpc-stream') { const sp = stub.stream(); return new Response(new ReadableStream({async start(c) { const r = (await sp).getReader(); for (;;) { const {done, value} = await r.read(); if (done) break; c.enqueue(value); } c.close(); }})); }
    return (async () => {
      // Returned asynchronously.
      if (p === '/async-target') { const t = await stub.target(); return new Response(body(i => t.n(i))); }
      if (p === '/wait-target') { const t = await stub.target(); const b = body(i => t.n(i)); await new Promise(r => setTimeout(r, 50)); return new Response(b); }
      if (p === '/inline-target') { const t = await stub.target(); return new Response(await new Response(body(i => t.n(i))).text()); }
      if (p === '/ws-async') return socket(await stub.target());
      // Bodies an entrypoint returned from its own first turn.
      if (p === '/ep-sync') return new Response(await stub.viaSync());
      if (p === '/ep-async') return new Response(await stub.viaAsync());
      if (p === '/ep-rpcstream') return new Response(await stub.viaRpcStream());
      // The published-route shape over a same-script loopback: the RPC stream is the response body.
      if (p === '/async-rpc-stream') return new Response(await stub.stream());
      if (p === '/buffered-rpc-stream') return new Response(await new Response(await stub.stream()).text());
      // Cross-request: /hold keeps what it received alive while /use, another request, tries it.
      if (p === '/hold') {
        held.s = await stub.stream(); held.t = await stub.target();
        await new Promise(r => { held.release = r; setTimeout(r, 8000); });
        return new Response('held');
      }
      if (p === '/held') return new Response(held.t ? 'yes' : 'no');
      if (p === '/use') {
        const out = {};
        try { out.target = 'ok:' + await held.t.n(1); } catch (e) { out.target = 'refused:' + kind(e); }
        try { out.stream = 'ok:' + await new Response(held.s).text(); } catch (e) { out.stream = 'refused:' + kind(e); }
        held.release?.();
        return Response.json(out);
      }
      return new Response('c7-02');
    })();
  },
};
