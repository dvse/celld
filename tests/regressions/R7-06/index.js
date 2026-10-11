import {WorkerEntrypoint,RpcTarget,DurableObject,restore} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Actor extends DurableObject {[restore](){return new Target();}make(){return this.ctx.restore({});}async save(binding){await this.ctx.storage.put('binding',binding);return await (await this.ctx.storage.get('binding')).read();}}
export class Receiver extends WorkerEntrypoint {
 async read(){const value=this.ctx.props.nested.value;this.ctx.props.nested.value=99;return {value,cap:this.ctx.props.cap?await this.ctx.props.cap.ping():null};}
 async fetch(){return Response.json(await this.read());}
}
export class Forward extends WorkerEntrypoint {roundtrip(binding){return binding;}}
export default {async fetch(req,env,ctx){const out={};
 for(const name of ['plain','persistent'])try{
  const cap=name==='persistent'?await env.ACTOR.getByName('source').make():undefined;
  const props={nested:{value:1},...(cap?{cap}:{})},binding=ctx.exports.Receiver({props});props.nested.value=2;cap?.[Symbol.dispose]();
  const values=[await binding.read(),await binding.read(),await (await binding.fetch('http://test/')).json()];
  const forwarded=await ctx.exports.Forward.roundtrip(binding);values.push(await forwarded.read());
  const loaded=env.LOADER.get(name,()=>({compatibilityDate:'2026-08-01',mainModule:'w.js',modules:{'w.js':`export default {async fetch(r,e){return Response.json(await e.BOUND.read());}}`},env:{BOUND:binding}}));
  values.push(await (await loaded.getEntrypoint().fetch('http://test/')).json());
  values.push(await env.ACTOR.getByName('storage').save(binding));out[name]=values;
 }catch(e){out[name]={error:e.message};}
 out.rejected=[];for(const cap of [new Target(),new ReadableStream(),new WritableStream()])try{ctx.exports.Receiver({props:{cap}});out.rejected.push(false);}catch(e){out.rejected.push(e.name==='DataCloneError');}
 return Response.json(out);
}};
