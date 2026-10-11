import {DurableObject,WorkerEntrypoint,RpcTarget,restore} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Inner extends WorkerEntrypoint {ping(){return 42;}}
export class Carrier extends WorkerEntrypoint {ping(){return this.ctx.props.inner.ping();}}
export class Forward extends WorkerEntrypoint {echo(value){return value;}}
export class Actor extends DurableObject {
 [restore](params){return new Target();}
 async test(inner){
  const out=[];
  for(let layers=0;layers<3;layers++){
   let value=inner;for(let i=0;i<layers;i++)value=this.ctx.exports.Carrier({props:{inner:value}});
   value=await this.ctx.exports.Forward.echo(value);
   try{await this.ctx.storage.put('v'+layers,value);out.push(await (await this.ctx.storage.get('v'+layers)).ping());}catch(e){out.push(e.name);}
   try{const restored=await this.ctx.restore({value});try{await this.ctx.storage.put('restore'+layers,restored);out.push('stored');}finally{restored[Symbol.dispose]();}}catch(e){out.push(e.name);}
  }
  return out;
 }
}
export default {async fetch(r,e,c){const out={};for(const [name,inner] of [['denied',await e.UNSAFE.get()],['allowed',c.exports.Inner({})]])try{out[name]=await e.ACTOR.getByName(name).test(inner);}catch(e){out[name]={error:e.message};}return Response.json(out);}};
