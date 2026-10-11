// Standalone fixture or extension module; never edits the existing pilot fixture.
import { DurableObject, WorkerEntrypoint, restore } from 'cloudflare:workers';
import { loaderCases, makeScope, code, DATE } from './cases.js';
export { loaderCases, makeScope } from './cases.js';
const ISOLATE=crypto.randomUUID();
export class Audit extends WorkerEntrypoint {
  hold() {return this.env.ROOT.getByName(this.ctx.props.root).waitForRelease();}
  note(value) { return this.env.ROOT.getByName(this.ctx.props.root).recordAudit({root:this.ctx.props.root,label:this.ctx.props.label,value}); }
}
export class Root extends DurableObject {
  constructor(ctx,env) {super(ctx,env);this.events=[];this.savedKeys=new Set();this.restorePlans=new Map();this.activeFacets=new Set();this.used=false;this.holdActive=false;this.holdRelease=null;}
  waitForRelease() {
    if(this.holdActive)throw new Error('only one cancellation gate permitted');
    this.holdActive=true;return new Promise(resolve=>{const timer=setTimeout(()=>this.releaseHold(),1000);this.holdRelease=()=>{clearTimeout(timer);this.holdActive=false;this.holdRelease=null;resolve('released');};});
  }
  releaseHold() {this.holdRelease?.();}
  parentIdentity() {return 'fixture-supervisor';}
  recordAudit(value) {if(this.events.length>=16)throw new Error('audit bound exceeded');this.events.push(value);return value;}
  async save(key,value) {this.savedKeys.add(key);await this.ctx.storage.put(key,value);}
  [restore](params) {
    if(params?.kind!=='facet' || !this.restorePlans.has(params.name))throw new TypeError('unknown fixture restore plan');
    const plan=this.restorePlans.get(params.name);this.activeFacets.add(params.name);
    return this.ctx.facets.get(params.name,()=>({class:plan.worker.getDurableObjectClass(plan.className,{props:plan.props})}));
  }
  async runLoaderCase(id,tag) {
    let traceEntered=false,result;const scope=makeScope(this,tag);
    try {
      if(this.used)throw new Error('precondition: one fresh supervisor per case');this.used=true;
      if(!Object.hasOwn(loaderCases,id))throw new Error('unknown Loader case');
      if(!this.env.LOADER || this.env.AMBIENT_TEST!=='parent-only-fixture')throw new Error('precondition: missing standalone Loader profile');
      if(typeof this.ctx.facets?.get!=='function' || typeof this.ctx.restore!=='function')throw new Error('precondition: missing facets or restore support');
      // Actual Loader control, not a mock or a countable stress trace.
      const control=scope.ep(scope.load(code()));const proof=await control.verify();
      if(proof.entry!=='default')throw new Error('precondition: Loader positive control failed');
      traceEntered=true;
      const evidence=await loaderCases[id](scope);
      result={id,status:'PASS',phase:'complete',traceEntered,layer:'real-process-RPC',profile:'loader-props-2026-09-04',compatibilityDate:DATE,origin:{root:String(this.ctx.id),name:this.ctx.id.name,isolate:ISOLATE},evidence};
    } catch(error) {result={id,status:traceEntered && !error?.blocked?'FAIL':'BLOCKED',phase:traceEntered && !error?.blocked?'trace':'precondition',traceEntered:traceEntered && !error?.blocked,setupOperationsEntered:traceEntered && !!error?.blocked,error:String(error)};}
    result.requestTag=tag;
    try {result.cleanup={status:'ok',...await scope.cleanup()};}
    catch(error) {result.cleanup={status:'FAIL',error:String(error),details:error.cleanupReport};if(result.status==='PASS'){result.status='FAIL';result.phase='cleanup';}}
    return result;
  }
}
export default {
  async fetch(request,env) {
    const path=new URL(request.url).pathname;
    if(path==='/health')return Response.json({profile:'loader-props-2026-09-04',compatibilityDate:DATE,caseIds:Object.keys(loaderCases),hasLoader:!!env.LOADER});
    if(path!=='/run' || request.method!=='POST')return new Response('not found',{status:404});
    const input=await request.json();
    if(!Object.hasOwn(loaderCases,input.id) || typeof input.tag!=='string' || !/^L\d{3}:[a-f0-9-]{36}$/.test(input.tag) || !input.tag.startsWith(input.id+':'))return Response.json({error:'invalid case or owned root tag'},{status:400});
    return Response.json(await env.ROOT.getByName(input.tag).runLoaderCase(input.id,input.tag));
  }
};
