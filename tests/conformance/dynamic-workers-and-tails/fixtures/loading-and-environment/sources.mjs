// Small real Worker modules. These are code supplied to Worker Loader, never mocks.
export const PROBE = `
import { WorkerEntrypoint, DurableObject } from 'cloudflare:workers';
const token = crypto.randomUUID();
export default class Main extends WorkerEntrypoint {
  constructor(ctx,env) { super(ctx,env); this.turns=0; }
  verify() { return { entry:'default', token, turns:++this.turns }; }
  inspect() { return { entry:'default', props:this.ctx.props, keys:Object.keys(this.env).sort() }; }
  mutate() { const before=this.ctx.props.config.value; this.ctx.props.config.value='recipient-write'; return before; }
  async run(value) { return this.env.AUDIT.note(value); }
  async fetch(request) {
    const path=new URL(request.url).pathname;
    if (path==='/hold') { await this.env.AUDIT.note('entered'); await this.env.AUDIT.hold(); }
    if (this.env.AUDIT) await this.env.AUDIT.note('fetch:'+path);
    return Response.json({entry:'default',props:this.ctx.props,path});
  }
}
export class Named extends WorkerEntrypoint {
  verify() { return {entry:'named',token}; }
  inspect() { return {entry:'named',props:this.ctx.props,keys:Object.keys(this.env).sort()}; }
}
export class Broken extends WorkerEntrypoint {
  constructor(ctx,env) { super(ctx,env); throw new Error('constructor-failed'); }
  verify() { return 'unreachable'; }
}
export class Gadget extends DurableObject { verify() { return 'durable-only'; } }
`;
export const VERIFY_FAILURE = `
import { WorkerEntrypoint } from 'cloudflare:workers';
export default class extends WorkerEntrypoint {
  verify() { throw new Error('verification-failed'); }
  run() { return this.env.AUDIT.note('run-entered'); }
  healthy() { return 'still-callable'; }
}
`;
export const OBJECT_AND_NAMED = `
import { WorkerEntrypoint } from 'cloudflare:workers';
export default { fetch(request,env,ctx) { return Response.json({entry:'object',props:ctx.props}); } };
export class Named extends WorkerEntrypoint { verify() { return 'named-class'; } }
`;
export const IMPORTER = `
import { WorkerEntrypoint } from 'cloudflare:workers';
import { value } from './dependency.js';
export default class extends WorkerEntrypoint { verify() { return value; } }
`;
export const FACET = `
import { DurableObject, RpcTarget, restore } from 'cloudflare:workers';
const moduleLabel='VERSION';
class Callback extends RpcTarget {
  constructor(owner,params) { super(); this.owner=owner; this.params=params; }
  async ping(value) { return {value,params:this.params,owner:await this.owner.inspect()}; }
  async effectThenThrow() { await this.owner.bump(); throw new Error('callback-after-effect'); }
}
export class Gadget extends DurableObject {
  async inspect() { return {module:moduleLabel,id:String(this.ctx.id),props:this.ctx.props,count:(await this.ctx.storage.get('count'))??0}; }
  async bump() { const n=((await this.ctx.storage.get('count'))??0)+1; await this.ctx.storage.put('count',n); return n; }
  async clear() { await this.ctx.storage.delete('count'); }
  mint(params) { return this.ctx.restore(params); }
  mintThenMutate(params) { const result=this.ctx.restore(params); params.nested.label="mutated-inside-facet"; return result; }
  [restore](params) { if(params.kind!=='callback') throw new TypeError('unsupported-callback'); return new Callback(this,params); }
}
export class Other extends Gadget { async inspect() { return {...await super.inspect(),module:'other:'+moduleLabel}; } }
export class Broken extends DurableObject { constructor(ctx,env) { super(ctx,env); throw new Error('facet-constructor-failed'); } }
export class Root extends Gadget {}
`;
export function facetSource(version) { return FACET.replace("moduleLabel='VERSION'",'moduleLabel='+JSON.stringify(version)); }
