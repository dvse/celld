// The script that owns class Box, plus an entrypoint that echoes its static props.
import {DurableObject, WorkerEntrypoint} from "cloudflare:workers";
export class Box extends DurableObject {
  put(value) { this.ctx.storage.kv.put("v", value); return this.ctx.id.toString(); }
  get() { return this.ctx.storage.kv.get("v") ?? null; }
}
export class Echo extends WorkerEntrypoint {
  props() { return this.ctx.props; }
  // Reads the same named Box through the owner's own namespace.
  ownerView(name) { return this.ctx.exports.Box.getByName(name).get(); }
}
export default { fetch() { return new Response("owner"); } };
