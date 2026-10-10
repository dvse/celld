// Checks patch 11: CELLD_PLACEMENT steers first claims of a class to its nodes.
import {DurableObject} from "cloudflare:workers";
export class Pinned extends DurableObject { where() { return "pinned"; } }
export class Free extends DurableObject { where() { return "free"; } }
export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const namespace = url.pathname === "/free" ? ctx.exports.Free : ctx.exports.Pinned;
    return new Response(await namespace.getByName(url.searchParams.get("n")).where());
  },
};
