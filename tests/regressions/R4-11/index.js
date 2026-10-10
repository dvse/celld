import {DurableObject,WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Echo extends WorkerEntrypoint {accept(v){return true;}}
export class Child extends DurableObject {}
export class Actor extends DurableObject {
 facet(){return this.ctx.facets.get('x',()=>({class:this.ctx.exports.Child}));}
 bad(){return this.facet();}
 async param(){try{await this.ctx.exports.Echo.accept(this.facet());return false;}catch(e){return e.name==='DataCloneError';}}
 good(){return new Target();}
}
export default {async fetch(req,env){
 const actor=env.ACTOR.getByName('test');let rejected;
 try{await actor.bad();rejected=false;}catch(e){rejected=e.name==='DataCloneError';}
 const parameter=await actor.param();const good=await actor.good();
 return Response.json({rejected,parameter,control:await good.ping()});
}};
