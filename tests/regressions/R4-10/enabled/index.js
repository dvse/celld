import {DurableObject,RpcTarget,restore} from 'cloudflare:workers';
class Value extends RpcTarget {read(){return 42;}}
class Cap extends RpcTarget {ping(){return 42;}}
export class Actor extends DurableObject {
 [restore](){return new Value();}
 async check(){
  let live=false,stored=false,transientRejected=false;
  try{const a=await this.ctx.restore({value:42});live=(await a.read())===42;
   await this.ctx.storage.put('plain',a);stored=(await (await this.ctx.storage.get('plain')).read())===42;}catch{}
  try{await this.ctx.restore({cap:new Cap()});}catch{transientRejected=true;}
  return {live,stored,transientRejected};
 }
}
export default {async fetch(req,env){return Response.json(await env.ACTOR.getByName('test').check());}};
