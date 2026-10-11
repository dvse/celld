// Ordinary HTTP handlers and DO.fetch only. All coordinator work stays inside its active handler.
import { DurableObject } from 'cloudflare:workers';
import { PROFILE, LIMITS, check, ident, bytes, join, equal, hash, gate, bounded, privateOrigin } from './common.js';
import { runCase, CASE_IDS } from './cases.js';
const ISOLATE = crypto.randomUUID();
export class HttpRoot extends DurableObject {
  constructor(ctx,env) { super(ctx,env); this.ops=new Map(); this.gates=new Map(); this.closing=false; this.events=[]; this.total=0; this.run=null; }
  identity() { return {root:String(this.ctx.id),isolate:ISOLATE,profile:PROFILE}; }
  note(op,kind,extra={}) { check(this.events.length<LIMITS.events,'journal bound'); this.events.push({seq:this.events.length+1,op,kind,...extra}); }
  barrier(name) { if(!name)return {promise:Promise.resolve(),open:true}; ident(name); if(!this.gates.has(name)) {check(this.gates.size<64,'gate count');this.gates.set(name,gate());} return this.gates.get(name); }
  async wait(name) { if(name) await bounded(this.barrier(name).promise,16000,'fixture gate '+name); }
  release(names) { check(Array.isArray(names)&&names.length<=64,'release bound'); for(const name of names){const g=this.barrier(name);g.open=true;g.resolve();} }
  state() { return {...this.identity(),run:this.run,ops:[...this.ops].map(([name,o])=>({name,...o.record})),events:this.events,active:[...this.ops.values()].filter(o=>o.record.active).length}; }
  configure(config) {
    check(!this.closing,'recipient closing');check(this.ops.size<LIMITS.operations,'operation count'); ident(config.name); check(!this.ops.has(config.name),'operation must be fresh');
    check(['download','upload','echo','reject','empty'].includes(config.kind),'known operation');
    const n=config.n ?? 32768; bytes(config.label||config.name,n); this.total+=n*2; check(this.total<=LIMITS.payloadBytes,'fixture logical-byte budget');
    for(const key of ['headerGate','tailGate','consumeGate','commitGate','replyGate']) if(config[key]) ident(config[key]);
    check(!config.prefix||Number.isInteger(config.prefix)&&config.prefix>=1&&config.prefix<=n,'prefix bound');
    const o={config:{...config,n},record:{entered:0,active:false,inputBytes:0,outputBytes:0,inputTerminal:'unopened',outputTerminal:'unopened',effect:0,cancelled:false},reader:null,controller:null,done:gate()};
    this.ops.set(config.name,o); return {configured:config.name};
  }
  async stop(name) {
    const o=this.ops.get(name);check(o,'known stop operation');o.record.cancelled=true;this.note(name,'application-stop');
    for(const key of ['headerGate','tailGate','consumeGate','commitGate','replyGate']) if(o.config[key])this.release([o.config[key]]);
    if(o.reader){try{await o.reader.cancel('fixture cleanup');}catch{}}
    if(o.controller){try{o.controller.error(new Error('fixture stopped'));}catch{}o.controller=null;o.record.outputTerminal='stopped';o.record.active=false;o.done.resolve();}
  }
  async cleanup() {
    this.closing=true;for(const o of this.ops.values())o.record.cancelled=true;
    for(const g of this.gates.values()){g.open=true;g.resolve();}
    await Promise.all([...this.ops].map(([name])=>this.stop(name)));
    await bounded(Promise.all([...this.ops.values()].filter(o=>o.record.entered).map(o=>o.done.promise)),2000,'fixture cleanup');
    check([...this.ops.values()].every(o=>!o.record.active&&!o.reader&&!o.controller),'fixture resources remain');
    return {...this.identity(),run:this.run,active:0,readers:0,controllers:0,status:'ok'};
  }
  async operation(request,name) {
    check(!this.closing,'recipient closing');const o=this.ops.get(name);check(o,'operation not configured');const c=o.config,r=o.record;
    check(r.entered===0,'operation cannot be dispatched twice');r.entered=1;r.active=true;this.note(name,'entered',{method:request.method});
    const headers={'content-type':c.contentType||'application/octet-stream','x-http-case-op':name,'x-http-run':this.run,'x-http-root':String(this.ctx.id),'x-http-isolate':ISOLATE};
    if(c.lengthHeader)headers['content-length']=String(c.n);
    const finish=terminal=>{if(!r.active)return;r.outputTerminal=terminal;r.active=false;o.controller=null;o.done.resolve();this.note(name,'output-'+terminal);};
    try {
      await this.wait(c.headerGate);
      if(r.cancelled){if(request.body)await request.body.cancel('stopped before consumption');finish('stopped');return new Response('stopped',{status:409,headers});}
      if(c.kind==='reject'){r.inputTerminal='not-consumed';if(request.body)await request.body.cancel('application rejects upload');finish('rejected');return new Response(bytes('rejection',31),{status:409,headers});}
      if(c.kind==='download') {
        r.inputTerminal='absent';
        if(request.method==='HEAD'){finish('head');return new Response(null,{headers:{...headers,'content-length':String(c.n)}});}
        const data=bytes(c.label||name,c.n);let pos=0;const self=this;
        if(c.buffered){r.outputBytes=data.length;finish('eof');return new Response(data,{headers});}
        const body=new ReadableStream({
          start(controller){o.controller=controller;},
          async pull(controller){
            try {
              if(r.cancelled){finish('stopped');controller.error(new Error('application stopped'));return;}
              if(pos>0 || c.errorBefore){if(c.tailGate)await self.wait(c.tailGate);if(r.cancelled){finish('stopped');controller.error(new Error('application stopped'));return;}if(c.errorBefore||c.errorAfter){r.plannedError='planned HTTP body error';finish('error');controller.error(new Error('planned HTTP body error'));return;}}
              if(pos>=data.length){finish('eof');controller.close();return;}
              const end=pos===0&&c.prefix?c.prefix:data.length;const view=data.subarray(pos,end);pos=end;r.outputBytes+=view.length;self.note(name,'produced',{bytes:r.outputBytes});controller.enqueue(view);
            } catch(error){finish('error');controller.error(error);}
          },
          cancel(){finish('cancelled');}
        },{highWaterMark:0});
        return new Response(body,{headers});
      }
      r.inputTerminal='reading';const chunks=[];o.reader=request.body?.getReader()||null;
      if(o.reader)try {
        let gated=false;
        for(let reads=0;reads<LIMITS.readOperations;reads++) {
          const v=await o.reader.read();if(v.done){r.inputTerminal='eof';break;}
          const copy=new Uint8Array(v.value);chunks.push(copy);r.inputBytes+=copy.length;check(r.inputBytes<=LIMITS.operationBytes,'upload byte bound');if(chunks.length===1)this.note(name,'first-consumed',{bytes:r.inputBytes});
          if(!gated&&c.consumeGate&&r.inputBytes>=(c.prefix||1)){gated=true;await this.wait(c.consumeGate);}
          check(reads<LIMITS.readOperations-1,'read operation safety bound');
        }
      }catch(error){r.inputTerminal='error';throw error;}finally{o.reader.releaseLock();o.reader=null;}
      else r.inputTerminal='eof';
      const value=join(chunks);equal(value,bytes(c.label||name,c.n),'recipient upload');r.inputHash=await hash(value);
      await this.wait(c.commitGate);
      if(r.cancelled){finish('stopped');return new Response('stopped',{status:409,headers});}
      r.effect=1;this.note(name,'effect',{bytes:value.length,hash:r.inputHash});await this.wait(c.replyGate);
      if(c.kind==='empty'){finish('empty');return new Response(null,{status:204,headers});}
      if(c.kind==='echo'){r.outputBytes=value.length;finish('eof');return new Response(value,{headers});}
      finish('receipt');return Response.json({name,run:this.run,bytes:value.length,hash:r.inputHash,effect:1,root:String(this.ctx.id),isolate:ISOLATE},{headers});
    }catch(error){r.active=false;o.done.resolve();this.note(name,'handler-error',{message:String(error).slice(0,180)});throw error;}
  }
  async fetch(request) {
    const u=new URL(request.url),path=u.pathname.split('/').filter(Boolean),action=path[2];
    if(action==='identity')return Response.json(this.identity());
    if(action==='run') {
      check(this.run===null,'fresh coordinator required');const input=await request.json();this.run=ident(input.run);
      check(CASE_IDS.includes(input.id),'unknown case');return Response.json(await runCase(input,this.identity(),privateOrigin(this.env.PRIVATE_ORIGIN)));
    }
    if(action==='control') {
      const input=await request.json();check(input.run===this.run||this.run===null,'fresh run correlation');if(this.run===null)this.run=ident(input.run);
      switch(input.action){
        case 'configure':return Response.json(this.configure(input.config));
        case 'snapshot':return Response.json(this.state());
        case 'release':this.release(input.names);return Response.json({released:input.names});
        case 'stop':await this.stop(input.name);return Response.json({stopped:input.name});
        case 'cleanup':return Response.json(await this.cleanup());
        default:throw new Error('unknown control');
      }
    }
    if(action==='op')return this.operation(request,ident(path[3]));
    return new Response('unknown fixture route',{status:404});
  }
}
export default { async fetch(request,env) {
  const u=new URL(request.url);if(u.pathname==='/health')return Response.json({profile:PROFILE,caseIds:CASE_IDS,limits:LIMITS});
  const path=u.pathname.split('/').filter(Boolean);check(path[0]==='root'&&path.length>=3,'fixture path');ident(path[1]);
  // Forward the original host-backed body unchanged through the ordinary DO.fetch seam.
  return env.ROOT.getByName(path[1]).fetch(request);
} };
