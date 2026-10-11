// Checks ctx.facets.clone() against workerd's cloneFacet: the copy carries the source's whole
// subtree (nested facets included), replaces the destination's subtree, aborts only the
// destination ("Facet was cloned-over."), leaves the source serving, and a clone onto itself
// only aborts. run.sh restarts the node between /prepare and /report, so the copies must be
// durable.
import {DurableObject} from "cloudflare:workers";
export class App extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.storage.sql.exec("create table if not exists t (k text primary key, v text)");
  }
  set(k, v) { this.ctx.storage.sql.exec("insert or replace into t values (?, ?)", k, v); }
  rows() { return this.ctx.storage.sql.exec("select k, v from t order by k").toArray(); }
  child(name) { return this.ctx.facets.get(name, () => ({class: this.ctx.exports.App})); }
  childSet(name, k, v) { return this.child(name).set(k, v); }
  childRows(name) { return this.child(name).rows(); }
}
const failure = async (call) => {
  try { await call(); return "no error"; } catch (error) { return String(error?.message ?? error); }
};
export class Root extends DurableObject {
  facet(name) { return this.ctx.facets.get(name, () => ({class: this.ctx.exports.App})); }
  async prepare() {
    await this.facet("a").set("one", "a1");
    await this.facet("a").childSet("c", "nested", "c1");
    await this.facet("b").set("stale", "x");
    await this.facet("b").childSet("d", "stale-child", "d1");
    const heldSource = this.facet("a");
    const heldDestination = this.facet("b");
    this.ctx.facets.clone("a", "b");
    // The source is not aborted: its running stub keeps serving. A write made after clone()
    // returned is not in the copy, as with workerd's synchronous copy.
    await heldSource.set("late", "after-clone-call");
    const sourceDuring = await heldSource.rows();
    const destinationAborted = await failure(() => heldDestination.rows());
    await this.ctx.storage.sync();
    await heldSource.set("two", "a2-after-clone");
    const sourceAfter = await heldSource.rows();
    await this.facet("b").set("three", "b3");
    // Self-clone: aborts the running facet and keeps its data.
    const heldSelf = this.facet("a");
    this.ctx.facets.clone("a", "a");
    const selfAborted = await failure(() => heldSelf.rows());
    const selfAfter = await this.facet("a").rows();
    return {sourceDuring, destinationAborted, sourceAfter, selfAborted, selfAfter, ...await this.report()};
  }
  // On a node that has not run "a" since the restart, "a"'s nested facet is only in the
  // bucket: the clone must still carry it.
  async reclone() {
    this.ctx.facets.clone("a", "e");
    await this.ctx.storage.sync();
    return {e: await this.facet("e").rows(), eChild: await this.facet("e").childRows("c")};
  }
  async report() {
    return {
      a: await this.facet("a").rows(),
      aChild: await this.facet("a").childRows("c"),
      b: await this.facet("b").rows(),
      bChildCopied: await this.facet("b").childRows("c"),
      bChildReplaced: await this.facet("b").childRows("d"),
    };
  }
}
export default {
  async fetch(request, env, ctx) {
    const root = ctx.exports.Root.getByName("root");
    const path = new URL(request.url).pathname;
    return Response.json(path === "/prepare" ? await root.prepare() : path === "/reclone" ? await root.reclone() : await root.report());
  },
};
