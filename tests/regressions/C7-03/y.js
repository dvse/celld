// C7-03's second script: mints stubs carrying props for its caller.
import {WorkerEntrypoint, DurableObject} from 'cloudflare:workers';
// A class the caller can start as a facet, carrying the props Y gives it.
export class YD extends DurableObject { who() { return 'yd-props:' + JSON.stringify(this.ctx.props); } }
export class Ent extends WorkerEntrypoint {
  fetch() { return new Response(null, {status: 204}); }
  who() { return 'y-props:' + JSON.stringify(this.ctx.props); }
  mint(u) { return this.ctx.exports.Ent({props: {user: u}}); }
  echo(x) { return x; }
  // The gatekeeper shape: a class with props, alone or in a bag.
  mintCls(u) { return this.ctx.exports.YD({props: {user: u}}); }
  mintBag(u) { return {class: this.ctx.exports.YD({props: {user: u}})}; }
}
export default { fetch() { return new Response('c7-03y'); } };
