// workerd JsRpcStub::dup of a persistent stub shares the live capability (api/worker-rpc.c++):
// stub.dup().add(1) acts on the same restored counter as stub.add(1).
import {RpcTarget, WorkerEntrypoint, restore} from "cloudflare:workers";
class Counter extends RpcTarget {
  constructor(id) { super(); this.id = id; this.value = 0; }
  add(n) { this.value += n; return `counter:${this.id}:${this.value}`; }
}
export class Source extends WorkerEntrypoint {
  async dupShares() {
    const stub = await this.ctx.restore({id: "a"});
    const first = await stub.add(1);
    const copy = stub.dup();
    const second = await copy.add(1);
    const third = await stub.add(1);
    return [first, second, third];
  }
  [restore](params) { return new Counter(params.id); }
}
export default {
  async fetch(request, env, ctx) {
    try { return Response.json(await ctx.exports.Source.dupShares()); }
    catch (e) { return Response.json({error: e.message}); }
  },
};
