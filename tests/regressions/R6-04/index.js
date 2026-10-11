import {DurableObject,WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
class Target extends RpcTarget {
 constructor(report,label){super();this.report=report;this.label=label;}
 ping(){return 42;}
 [Symbol.dispose](){return this.report.record(this.label);}
}
export class Factory extends WorkerEntrypoint {make(kind,label){return new Target(this.env[kind].getByName(kind.toLowerCase()),label);}}
class Sink extends RpcTarget {
 constructor(actor){super();this.actor=actor;this.keep=new Map();}
 ping(){return 42;}
 accept(label,cap,retain){if(retain)this.keep.set(label,cap.dup());return 42;}
 async held(label){return await this.keep.get(label).ping();}
 release(label){this.keep.get(label)[Symbol.dispose]();this.keep.delete(label);return true;}
 makeReply(label){return this.actor.ctx.exports.Factory.make('RECEIVER',label);}
}
class Ledger extends DurableObject {
 init(){return true;}
 async record(label){await this.ctx.storage.put(label,(await this.ctx.storage.get(label)||0)+1);}
 async ledger(){return Object.fromEntries(await this.ctx.storage.list());}
}
export class Receiver extends Ledger {
 sink(){return new Sink(this);}
 accept(_label,_cap){return 42;}
}
export class Sender extends Ledger {
 async setup(){this.anchor=await this.env.RECEIVER.getByName('receiver').sink();return await this.anchor.ping();}
 alive(){return this.anchor.ping();}
 async send(kind,label){
  let cap,sink;
  try{
   if(kind==='reply'){sink=await this.env.RECEIVER.getByName('receiver').sink();const result=await sink.makeReply(label);result[Symbol.dispose]();return 'delivered';}
   cap=await this.ctx.exports.Factory.make('SENDER',label);
   if(kind==='tunnel'){await this.env.RECEIVER.getByName('receiver').accept(label,cap);return 'delivered';}
   sink=await this.env.RECEIVER.getByName('receiver').sink();
   if(kind==='ambiguous')this.retained=sink.dup();
   await sink.accept(label,cap,kind==='ambiguous');return 'delivered';
  }catch(e){return 'failed';}
  finally{cap?.[Symbol.dispose]();sink?.[Symbol.dispose]();}
 }
 async retainedAlive(label){return await this.retained.held(label);}
 async releaseRetained(label){await this.retained.release(label);this.retained[Symbol.dispose]();return true;}
 finish(){this.anchor[Symbol.dispose]();return true;}
}
export default {async fetch(request,env){const u=new URL(request.url),[kind,method]=u.pathname.slice(1).split('/');
 try{return Response.json({ok:await env[kind.toUpperCase()].getByName(kind)[method](...JSON.parse(u.searchParams.get('args')||'[]'))});}
 catch(e){return Response.json({error:e.message},{status:500});}
}};
