import {DurableObject,WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
class Target extends RpcTarget {
 constructor(report,label){super();this.report=report;this.label=label;}
 ping(){return 42;}
 async slow(ms){await this.report.entered(this.label);await new Promise(r=>setTimeout(r,ms));return 42;}
 [Symbol.dispose](){return this.report.disposed(this.label);}
}
export class Factory extends WorkerEntrypoint {make(label){return new Target(this.env.SOURCE.getByName('source'),label);}}
export class Source extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.keep=new Map();}
 init(){return true;}
 async get(label,keep=false){const s=await this.ctx.exports.Factory.make(label);if(keep)this.keep.set(label,s.dup());return s;}
 async disposed(label){const k='disposed:'+label;await this.ctx.storage.put(k,(await this.ctx.storage.get(k)||0)+1);}
 async entered(label){await this.ctx.storage.put('entered:'+label,true);}
 async ledger(){return Object.fromEntries(await this.ctx.storage.list());}
 async retained(){return await this.keep.get('local').ping();}
 release(){this.keep.get('local')[Symbol.dispose]();this.keep.delete('local');return true;}
}
export class Holder extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.handles=new Map();}
 init(){return true;}
 async hold(label,keep=false){const s=await this.env.SOURCE.getByName('source').get(label,keep);this.handles.set(label,s);return await s.ping();}
 async forward(label,retain){const s=await this.env.SOURCE.getByName('source').get(label);if(retain)this.handles.set(label,s.dup());return s;}
 async alive(){return await this.handles.get('forward-kept').ping();}
 async slow(ms){return await this.handles.get('active').slow(ms);}
 async pending(){this.ctx.waitUntil(this.handles.get('active').slow(3600000).catch(()=>{}));return true;}
}
export class Receiver extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.handles=[];}
 init(){return true;}
 async take(){for(const [label,retain] of [['forward-only',false],['forward-kept',true]]){const s=await this.env.HOLDER.getByName('holder').forward(label,retain);this.handles.push(s,s.dup());if(await s.ping()!==42)throw Error('forwarded call');}return true;}
}
export default {async fetch(request,env){
 const u=new URL(request.url),[kind,method]=u.pathname.slice(1).split('/');
 const s=env[kind.toUpperCase()].getByName(kind);
 const args=u.searchParams.has('args')?JSON.parse(u.searchParams.get('args')):[];
 try{return Response.json({ok:await s[method](...args)});}catch(e){return Response.json({error:e.message},{status:500});}
}};
