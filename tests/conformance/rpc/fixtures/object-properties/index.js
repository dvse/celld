// workerd: a Durable Object stub member is a JsRpcProperty (api/worker-rpc.c++, js-rpc-test.js
// property cases): `await stub.getter` reads the value, `stub.obj.method()` walks a path, and own
// instance state stays invisible.
import {DurableObject, RpcTarget} from "cloudflare:workers";
class Inner extends RpcTarget { hello(n) { return "inner " + n; } }
export class Obj extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.secret = "own"; }
  get answer() { return 42; }
  get inner() { return new Inner(); }
  get data() { return {nested: {value: "deep"}}; }
  method(x) { return "method " + x; }
}
const outcome = async (fn) => { try { return await fn(); } catch (e) { return "err:" + e.message; } };
export default {
  async fetch(request, env) {
    const stub = env.OBJ.getByName("o");
    return Response.json({
      getter: await outcome(async () => await stub.answer),
      pathCall: await outcome(() => stub.inner.hello(3)),
      plainPath: await outcome(async () => await stub.data.nested.value),
      method: await outcome(() => stub.method("x")),
      ownState: await outcome(async () => await stub.secret),
    });
  },
};
