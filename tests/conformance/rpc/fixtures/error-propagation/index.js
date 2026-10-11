// workerd enhanced_error_serialization (jsg/ser.c++ WriteHostObject, jsg/util.c++): a thrown
// error crosses RPC with every own property except name/message/stack, enumerable or not,
// including `cause` and AggregateError `errors`; a DOMException keeps its class and name; one
// uncloneable property does not collapse the whole error.
import {WorkerEntrypoint} from "cloudflare:workers";
export class Thrower extends WorkerEntrypoint {
  hidden() {
    const e = new Error("hidden");
    Object.defineProperty(e, "code", {value: "E_HIDDEN", enumerable: false});
    e.visible = 1;
    throw e;
  }
  caused() { throw new Error("outer", {cause: new Error("inner")}); }
  aggregate() { throw new AggregateError([new Error("a"), new Error("b")], "many"); }
  dom() { throw new DOMException("bad clone", "DataCloneError"); }
  partial() { const e = new Error("partial"); e.ok = 2; e.fn = () => 1; throw e; }
}
const catchIt = async (fn) => {
  try { await fn(); return "no error"; } catch (e) {
    return {name: e.name, message: e.message, code: e.code, visible: e.visible,
      cause: e.cause?.message, errors: e.errors?.map((x) => x.message),
      isDom: e instanceof DOMException, ok: e.ok, remote: e.remote};
  }
};
export default {
  async fetch(request, env) {
    const t = env.THROWER;
    return Response.json({
      hidden: await catchIt(() => t.hidden()),
      caused: await catchIt(() => t.caused()),
      aggregate: await catchIt(() => t.aggregate()),
      dom: await catchIt(() => t.dom()),
      partial: await catchIt(() => t.partial()),
    });
  },
};
