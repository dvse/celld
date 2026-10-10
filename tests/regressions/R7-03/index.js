import {DurableObject,WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
class Child extends RpcTarget {
 constructor(report,label){super();this.report=report;this.label=label;}
 ping(){return 42;}
 [Symbol.dispose](){return this.report.record(this.label+':child');}
}
class Session extends RpcTarget {
 constructor(report,ctx){super();this.report=report;this.ctx=ctx;this.gates=new Map();}
 ping(){return 42;}
 async late(label,kind){
  const ready=new Promise(resolve=>this.gates.set(label,resolve));
  await this.report.record(label+':started');
  await ready;
  this.ctx.waitUntil(this.report.record(label+':background'));
  if(kind==='error')throw new Error('late failure');
  if(kind==='child')return new Child(this.report,label);
  if(kind==='bad')return {child:new Child(this.report,label),bad:Symbol()};
  const report=this.report;
  return {child:new Child(report,label),read:new ReadableStream({cancel(){return report.record(label+':read');}}),write:new WritableStream({abort(){return report.record(label+':write');}}),[Symbol.dispose](){return report.record(label+':graph');}};
 }
 open(label){this.gates.get(label)?.();this.gates.delete(label);return true;}
 [Symbol.dispose](){return this.report.record('session');}
}
export class Factory extends WorkerEntrypoint {make(){return new Session(this.env.RECEIVER.getByName('receiver'),this.ctx);}}
export class Receiver extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.gates=new Map();}
 init(){return true;}
 make(){return this.ctx.exports.Factory.make();}
 async record(label){await this.ctx.storage.put(label,(await this.ctx.storage.get(label)||0)+1);}
 async wait(label){const promise=new Promise(resolve=>this.gates.set(label,resolve));await this.record(label+':started');await promise;}
 release(label){this.gates.get(label)?.();this.gates.delete(label);return true;}
 async ledger(){return Object.fromEntries(await this.ctx.storage.list());}
}
export class Sender extends DurableObject {
 init(){return true;}
 async setup(){this.anchor=await this.env.RECEIVER.getByName('receiver').make();return await this.anchor.ping();}
 alive(){return this.anchor.ping();}
 async call(label,kind){try{const result=await this.anchor.late(label,kind);result?.[Symbol.dispose]?.();return 'ok';}catch(e){return 'failed';}}
 release(label){return this.anchor.open(label);}
 finish(){this.anchor[Symbol.dispose]();return true;}
}
export default {async fetch(request,env){const u=new URL(request.url),[kind,method]=u.pathname.slice(1).split('/');try{return Response.json({ok:await env[kind.toUpperCase()].getByName(kind)[method](...JSON.parse(u.searchParams.get('args')||'[]'))});}catch(e){return Response.json({error:e.message},{status:500});}}};
