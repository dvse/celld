import {DurableObject,WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
class Callback extends RpcTarget {constructor(done){super();this.done=done;}ping(){return 42;}[Symbol.dispose](){this.done();}}
export class Factory extends WorkerEntrypoint {callback(){return new Callback(()=>{});}}
export class Leaf extends DurableObject {async echo(value,cb){return [value.nested.value,await cb.ping()];}}
const code=`import {WorkerEntrypoint} from 'cloudflare:workers';export default class extends WorkerEntrypoint {async echo(value,cb){return [value.nested.value,await cb.ping()];}}`;
export class Actor extends DurableObject {
 async invoke(stub){const cb=await this.ctx.exports.Factory.callback(),value={nested:{value:1}},call=stub.echo(value,cb);value.nested.value=2;cb[Symbol.dispose]();return await call;}
 async test(){const out={};
  const worker=this.env.LOADER.get('loaded',async()=>{await new Promise(r=>setTimeout(r,20));return {compatibilityDate:'2026-08-01',mainModule:'w.js',modules:{'w.js':code}};});
  const entry=worker.getEntrypoint();
  for(const label of ['loaderCold','loaderWarm'])try{out[label]=await this.invoke(entry);}catch(e){out[label]={error:e.message};}
  const facet=this.ctx.facets.get('facet',async()=>{await new Promise(r=>setTimeout(r,20));return {class:this.ctx.exports.Leaf};});
  for(const label of ['facetCold','facetWarm'])try{out[label]=await this.invoke(facet);}catch(e){out[label]={error:e.message};}
  this.ctx.facets.clone('facet','clone');try{out.cloneBarrier=await this.invoke(facet);}catch(e){out.cloneBarrier={error:e.message};}
  const bad=this.ctx.facets.get('bad',()=>{throw new Error('startup failed');});try{await this.invoke(bad);out.failedStartup=false;}catch(e){out.failedStartup=e.message.includes('startup failed');}
  return out;
 }
}
export default {async fetch(r,e){try{return Response.json(await e.ACTOR.getByName('test').test());}catch(e){return Response.json({error:e.message});}}};
