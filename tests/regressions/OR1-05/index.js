import { DurableObject, RpcTarget, WorkerEntrypoint } from 'cloudflare:workers';
class T extends RpcTarget { echo(x) { return x.v; } }
export class D extends DurableObject { target() { return new T(); } }
export class E extends WorkerEntrypoint { target() { return new T(); } }
// A parameter getter disposes the stub while the call's arguments serialize.
// workerd acquires the one-call client before serializing parameters
// (api/worker-rpc.c++ callImpl / getClientForOneCall), so the call is delivered.
const disposingCall = async (stub) => {
  const arg = { get v() { stub[Symbol.dispose](); return 7; } };
  try { return { result: await stub.echo(arg) }; }
  catch (e) { return { error: String(e.message) }; }
};
// Arguments are captured when the call expression evaluates, on every path.
const capture = async (call) => {
  const arg = { n: 1 };
  const p = call(arg);
  arg.n = 2;
  try { return await p; } catch (e) { return String(e.message); }
};
export default { async fetch(req, env, ctx) {
  const actor = env.D.getByName('a');
  const svc = ctx.exports.E;
  return Response.json({
    actorTarget: await disposingCall(await actor.target()),
    serviceTarget: await disposingCall(await svc.target()),
    pipelinedTarget: await capture(a => actor.target().echo({ get v() { return a.n; } })),
    directDisposedFirst: await (async () => {
      const s = await actor.target(); s[Symbol.dispose]();
      try { await s.echo({ v: 1 }); return 'delivered'; } catch (e) { return 'rejected'; }
    })(),
  });
}};
