import {DurableObject,RpcTarget,restore} from 'cloudflare:workers';
class Counter extends RpcTarget {value=0;next(){return ++this.value;}}
export class Actor extends DurableObject {
 [restore](){return new Counter();}
 async check(){
  const original=await this.ctx.restore({id:'counter'});
  await this.ctx.storage.put('counter',original);
  original[Symbol.dispose]();
  const lazy=await this.ctx.storage.get('counter');
  const copy=lazy.dup();
  return [await lazy.next(),await copy.next(),await lazy.next()];
 }
}
export default {async fetch(req,env){return Response.json(await env.ACTOR.getByName('test').check());}};
