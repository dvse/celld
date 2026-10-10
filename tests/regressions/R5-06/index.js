import {DurableObject,RpcTarget,restore} from 'cloudflare:workers';
let saved,restores=0;
class Value extends RpcTarget {ping(){return 42;} get value(){return 42;}}
export class Actor extends DurableObject {
 [restore](){restores++;return new Value();}
 async seed(){const cap=await this.ctx.restore({id:'value'});await this.ctx.storage.put('cap',cap);cap[Symbol.dispose]();}
 async load(){saved=await this.ctx.storage.get('cap');}
 async foreign(){const rejected=[];const before=restores;
  for(const action of [()=>saved.ping(),()=>saved.value,()=>saved.dup(),()=>this.ctx.storage.put('bad',saved)]){
   try{await action();rejected.push(false);}catch(e){rejected.push(e.message.includes('Cannot perform I/O on behalf of a different'));}
  }
  return {rejected,restores:restores-before};
 }
 transferSaved(){return saved;}
 async own(){return await saved.ping();}
}
export default {async fetch(request,env){
 const a=env.ACTOR.getByName('a'),b=env.ACTOR.getByName('b');
 await a.seed();await a.load();const lazy=await b.foreign();
 let transferRejected=false;try{await b.transferSaved();}catch(e){transferRejected=e.message.includes('Cannot perform I/O on behalf of a different');}
 let own;try{own=await a.own();}catch(e){own=e.name;}const resolved=await b.foreign();
 let transferred;try{const explicit=await a.transferSaved();transferred=await explicit.ping();explicit[Symbol.dispose]();}catch(e){transferred=e.name;}
 return Response.json({lazy,transferRejected,own,resolved,transferred});
}};
