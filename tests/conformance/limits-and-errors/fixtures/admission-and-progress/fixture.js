import * as cf from 'cloudflare:workers';
export const PROFILE = 'bounded-load-native-2026-09-04';
export const INSTANCE = crypto.randomUUID();
export const FRAME = 8192, TOTAL = FRAME * 3, MAX_READS = 65536;
export function ok(value, why) { if (!value) throw new Error(why); }
export function eq(a, b, why) { ok(JSON.stringify(a) === JSON.stringify(b), why + ': ' + JSON.stringify({actual:a, expected:b})); }
export function requireApi(value, why) { if (!value) { const e = new Error(why); e.code='PRECONDITION'; throw e; } }
export const drop = value => value?.[Symbol.dispose]?.();
export const pattern = (seed, offset) => (seed + offset * 17) & 255;
export function chunk(seed, start, size=FRAME) { return Uint8Array.from({length:size}, (_,i)=>pattern(seed,start+i)); }
export function checkBytes(bytes, seed, offset) {
  ok(bytes instanceof Uint8Array, 'native stream did not deliver bytes');
  for(let i=0;i<bytes.length;i++) ok(bytes[i]===pattern(seed,offset+i), 'byte mismatch at '+(offset+i));
}
export async function rejection(promise, marker) {
  try { await promise; } catch(error) { ok(String(error).includes(marker), 'wrong rejection: '+String(error)); return String(error); }
  throw new Error('expected rejection: '+marker);
}
export class Book {
  constructor() { this.counts={}; this.waiters=[]; this.gates=new Map(); this.events=[]; }
  mark(key, detail=null) {
    ok(this.events.length<512, 'event bound'); this.events.push({key,detail}); this.counts[key]=(this.counts[key]??0)+1;
    const rest=[]; for(const w of this.waiters) { if((this.counts[w.key]??0)>=w.n) w.resolve(this.counts[w.key]); else rest.push(w); } this.waiters=rest;
  }
  wait(key,n=1) { return (this.counts[key]??0)>=n ? Promise.resolve(this.counts[key]) : new Promise(resolve=>this.waiters.push({key,n,resolve})); }
  gate(key) { if(!key) return Promise.resolve(); let value=this.gates.get(key); if(!value) { let resolve; const promise=new Promise(r=>resolve=r); value={promise,resolve,open:false}; this.gates.set(key,value); } return value.promise; }
  release(key) { this.gate(key); const value=this.gates.get(key); if(value && !value.open) {value.open=true;value.resolve();} }
  releaseAll() { for(const key of this.gates.keys()) this.release(key); }
}
export function state() { return {book:new Book(), jobs:new Set(), active:0, maxActive:0, lanes:new Map(), queued:new Map(), sources:new Map(), sinks:new Map(), readers:new Set(), closing:false}; }
function track(s,promise) { const p=Promise.resolve(promise); s.jobs.add(p); p.then(()=>s.jobs.delete(p),()=>s.jobs.delete(p)); p.catch(()=>{}); return p; }
function snapshot(s) {
  const summarize=map=>Object.fromEntries([...map].map(([k,v])=>[k,{bytes:v.bytes,closed:v.closed,cancelled:v.cancelled,error:v.error??null,reason:v.reason??null}]));
  return {counts:{...s.book.counts}, events:[...s.book.events], active:s.active,maxActive:s.maxActive,pending:s.jobs.size,queued:[...s.queued.keys()].sort(),lanes:Object.fromEntries([...s.lanes].map(([k,v])=>[k,{active:v.active,maxActive:v.maxActive,limit:v.limit,queue:v.queue.map(x=>x.id)}])),sources:summarize(s.sources),sinks:summarize(s.sinks)};
}
function makeSource(s,id,seed,gate,fail=false,total=TOTAL) {
  ok(!s.sources.has(id),'source reused'); const value={bytes:0,closed:0,cancelled:0,error:null,reason:null,controller:null}; s.sources.set(id,value);
  return new ReadableStream({
    start(controller) {value.controller=controller;s.book.mark('source-open:'+id);},
    async pull(controller) {
      if(value.closed || value.cancelled || value.error) return;
      if(value.bytes===FRAME && gate) {s.book.mark('source-paused:'+id);await s.book.gate(gate);}
      if(value.cancelled || value.error) return;
      if(fail && value.bytes===FRAME) {value.error='planned:source:'+id;s.book.mark('source-error:'+id);controller.error(new Error(value.error));return;}
      const bytes=chunk(seed,value.bytes,Math.min(FRAME,total-value.bytes)); value.bytes+=bytes.length;controller.enqueue(bytes);s.book.mark('source-frame:'+id);
      if(value.bytes===total) {value.closed++;controller.close();s.book.mark('source-close:'+id);}
    },
    cancel(reason) { if(!value.cancelled) {value.cancelled++;value.reason=String(reason);s.book.mark('source-cancel:'+id,value.reason);} if(gate)s.book.release(gate); }
  },{highWaterMark:0});
}
function makeSink(s,id,seed,gate,fail=false,total=TOTAL) {
  ok(!s.sinks.has(id),'sink reused'); const value={bytes:0,closed:0,cancelled:0,error:null,controller:null};s.sinks.set(id,value);
  return new WritableStream({
    start(controller) {value.controller=controller;},
    async write(bytes) {
      if(value.bytes===0) {s.book.mark('sink-enter:'+id);await s.book.gate(gate);}
      if(fail) {value.error='planned:sink:'+id;s.book.mark('sink-error:'+id);throw new Error(value.error);}
      checkBytes(bytes,seed,value.bytes);value.bytes+=bytes.length;ok(value.bytes<=total,'sink overflow');
    },
    close() {eq(value.bytes,total,'sink terminal bytes');value.closed++;s.book.mark('sink-close:'+id);},
    abort(reason) {value.cancelled++;value.reason=String(reason);s.book.mark('sink-abort:'+id);}
  },{highWaterMark:1});
}
async function work(s,id,gate,callback,fail=false) {
  ok(!s.closing,'fixture closing');ok(s.active<16,'active call bound');s.active++;s.maxActive=Math.max(s.maxActive,s.active);s.book.mark('enter:'+id);
  try {await s.book.gate(gate);let value=callback?await callback.visit(id):'ok:'+id;s.book.mark('effect:'+id);if(fail)throw new Error('planned:work:'+id);return {id,value};}
  finally {s.active--;s.book.mark('settle:'+id);}
}
function pump(s,lane) {
  while(lane.active<lane.limit && lane.queue.length) {
    const job=lane.queue.shift();s.queued.delete(job.id);lane.active++;lane.maxActive=Math.max(lane.maxActive,lane.active);
    const p=work(s,job.id,job.gate,job.callback,job.fail);
    p.then(value=>{lane.active--;pump(s,lane);job.resolve(value);},error=>{lane.active--;pump(s,lane);job.reject(error);}).catch(()=>{});
  }
}
export class RootBase extends cf.DurableObject {
  constructor(ctx,env) {super(ctx,env);this.states=new Map();this.finishedTags=new Set();}
  inspect() {return {root:String(this.ctx.id),isolate:INSTANCE};}
  profile() {return {modern:globalThis.Cloudflare?.compatibilityFlags?.rpc_params_dup_stubs===true,rpcStub:typeof cf.RpcStub==='function',dispose:typeof Symbol.dispose==='symbol',streams:typeof ReadableStream==='function'&&typeof WritableStream==='function',loader:!!this.env.LOADER,waitUntil:typeof cf.waitUntil==='function',crypto:typeof crypto.subtle?.digest==='function'};}
  state(tag) {ok(!this.finishedTags.has(tag),'fixture tag already closed');let s=this.states.get(tag);if(!s){s=state();this.states.set(tag,s);}return s;}
  stats(tag) {return snapshot(this.state(tag));}
  barrier(tag,key,n=1) {return this.state(tag).book.wait(key,n);}
  release(tag,keys) {for(const key of keys)this.state(tag).book.release(key);return keys;}
  note(tag,key,detail=null) {const s=this.state(tag);s.book.mark(key,detail);if(key.startsWith('background-ok:')||key.startsWith('background-failed:'))s.book.mark('background-terminal:'+key.slice(key.indexOf(':')+1));return {key,owner:this.inspect()};}
  work(tag,id,gate=null,callback=null,fail=false) {const s=this.state(tag);return track(s,work(s,id,gate,callback,fail));}
  async broadcast(tag,ids,callback,background=false) {
    const s=this.state(tag);ok(ids.length>=2&&ids.length<=12,'fanout bound');
    const target=background?callback.dup():callback;
    const task=Promise.allSettled(ids.map(id=>track(s,work(s,id,null,target)))).then(values=>values.map((v,i)=>v.status==='fulfilled'?{id:ids[i],status:'fulfilled',value:v.value}:{id:ids[i],status:'rejected',error:String(v.reason)}));
    if(background) {const retained=track(s,task.then(async result=>{s.book.mark('background-settled',result);await drop(target);},async error=>{await drop(target);throw error;}));this.ctx.waitUntil(retained);return {scheduled:ids.length};}
    return await task;
  }
  admit(tag,laneName,id,gate,callback=null,fail=false) {
    const s=this.state(tag);ok(s.jobs.size<16,'admission request bound');ok(!s.queued.has(id),'queued ID reused');let lane=s.lanes.get(laneName);
    if(!lane){lane={active:0,maxActive:0,limit:2,queue:[]};s.lanes.set(laneName,lane);}
    const p=new Promise((resolve,reject)=>{const job={id,gate,callback,fail,resolve,reject,lane};lane.queue.push(job);s.queued.set(id,job);s.book.mark('admitted:'+id);pump(s,lane);});return track(s,p);
  }
  cancelQueued(tag,id) {const s=this.state(tag),job=s.queued.get(id);ok(job,'cancellation target not queued');job.lane.queue.splice(job.lane.queue.indexOf(job),1);s.queued.delete(id);s.book.mark('queue-cancel:'+id);job.reject(new Error('planned:cancel:'+id));return 'cancelled:'+id;}
  source(tag,id,seed,gate=null,fail=false) {return makeSource(this.state(tag),id,seed,gate,fail);}
  sink(tag,id,seed,gate=null,fail=false) {return makeSink(this.state(tag),id,seed,gate,fail);}
  consume(tag,id,stream,seed,gate=null,fail=false) {
    const s=this.state(tag),reader=stream.getReader();s.readers.add(reader);reader.closed.catch(()=>{});
    return track(s,(async()=>{let bytes=0,ended=false;try {
      for(let reads=0;reads<MAX_READS;reads++){const next=await reader.read();if(next.done){ended=true;break;}checkBytes(next.value,seed,bytes);bytes+=next.value.length;ok(bytes<=TOTAL,'consume overflow');
        if(bytes>0&&(s.book.counts['consume-prefix:'+id]??0)===0){s.book.mark('consume-prefix:'+id,bytes);await s.book.gate(gate);if(fail)throw new Error('planned:consumer:'+id);}}
      ok(ended,'consume read-operation bound');eq(bytes,TOTAL,'consume terminal bytes');s.book.mark('consume-effect:'+id);return {id,bytes};
    } catch(error){s.book.mark('consume-error:'+id,String(error));await reader.cancel('planned:consumer-stop:'+id);throw error;}
    finally{s.readers.delete(reader);reader.releaseLock();s.book.mark('consume-settle:'+id);}})());
  }
  unblockForCleanup(tag) {const s=this.states.get(tag);if(s)s.book.releaseAll();return {released:true};}
  async cleanup(tag,backgroundIds=[]) {
    const s=this.states.get(tag);if(!s)return {status:'ok',empty:true};s.closing=true;s.book.releaseAll();
    for(const [id,job] of [...s.queued]) {job.lane.queue.splice(job.lane.queue.indexOf(job),1);s.queued.delete(id);job.reject(new Error('fixture-cleanup:'+id));}
    for(const value of s.sources.values()) if(!value.closed&&!value.cancelled&&!value.error){value.error='fixture-cleanup';try{value.controller.error(new Error(value.error));}catch{}}
    for(const value of s.sinks.values()) if(!value.closed&&!value.cancelled&&!value.error){value.error='fixture-cleanup';try{value.controller.error(new Error(value.error));}catch{}}
    await Promise.allSettled([...s.readers].map(r=>r.cancel('fixture-cleanup')));await Promise.allSettled([...s.jobs]);await Promise.all(backgroundIds.map(id=>s.book.wait('background-terminal:'+id)));
    const out=snapshot(s);ok(out.active===0&&out.pending===0&&out.queued.length===0&&s.readers.size===0,'provider cleanup has pending work');
    return {status:'ok',phase:'released',active:out.active,pending:out.pending,queued:out.queued.length,readers:s.readers.size,sources:out.sources,sinks:out.sinks};
  }
  finishCleanup(tag) {const s=this.states.get(tag);if(!s)return {status:'ok',empty:true};const out=snapshot(s);ok(out.active===0&&out.pending===0&&out.queued.length===0&&s.readers.size===0,'provider final cleanup has pending work');this.states.delete(tag);this.finishedTags.add(tag);return {status:'ok',phase:'complete',active:0,pending:0,queued:0,readers:0};}
}
class Callback extends cf.RpcTarget {
  constructor(local,config) {super();this.local=local;this.config=config;this.active=0;this.maxActive=0;}
  async visit(id) {
    this.active++;this.maxActive=Math.max(this.maxActive,this.active);this.local.mark('callback-enter:'+id);
    try {if(this.config.gates?.[id])await this.local.gate(this.config.gates[id]);if(this.config.reenter)await this.config.reenter(id);if(this.config.fail?.includes(id))throw new Error('planned:callback:'+id);this.local.mark('callback-effect:'+id);return 'ok:'+id;}
    finally {this.active--;this.local.mark('callback-settle:'+id);}
  }
  [Symbol.dispose]() {this.local.mark('callback-disposed');}
}
export class Scope {
  constructor(root,peer,tag,peerName) {this.root=root;this.peer=peer;this.tag=tag;this.peerName=peerName;this.local=state();this.callbacks=[];this.pending=[];this.drains=[];this.writers=[];this.handles=[];this.workers=[];this.entries=[];this.backgroundIds=[];}
  watch(value) {const p=Promise.resolve(value);p.catch(()=>{});this.pending.push(p);return p;}
  stats() {return this.peer.stats(this.tag);}
  wait(key,n=1) {return this.peer.barrier(this.tag,key,n);}
  release(...keys) {return this.peer.release(this.tag,keys);}
  callback(config={}) {const book=new Book(),target=new Callback(book,config),stub=new cf.RpcStub(target);const item={book,target,stub};this.callbacks.push(item);return item;}
  localSource(id,seed,gate=null,fail=false) {return makeSource(this.local,id,seed,gate,fail);}
  async download(id,seed,gate=null,fail=false) {return await this.peer.source(this.tag,id,seed,gate,fail);}
  drain(id,stream,seed,total=TOTAL) {
    const reader=stream.getReader(),item={id,reader,stream,bytes:0,readCalls:0,cancelled:false,settled:false};this.drains.push(item);this.watch(reader.closed.then(()=>({status:'closed'}),error=>({status:'rejected',error:String(error)})));
    item.promise=this.watch((async()=>{let ended=false;try {
      for(;item.readCalls<MAX_READS;){item.readCalls++;const next=await reader.read();if(next.done){ended=true;break;}checkBytes(next.value,seed,item.bytes);item.bytes+=next.value.length;ok(item.bytes<=total,'drain overflow');if(item.bytes>0&&!this.local.book.counts['read:'+id])this.local.book.mark('read:'+id,item.bytes);}
      ok(ended,'drain read-operation bound');if(!item.cancelled)eq(item.bytes,total,'drain terminal bytes');return {status:item.cancelled?'cancelled':'ok',bytes:item.bytes};
    }catch(error){return {status:'error',bytes:item.bytes,error:String(error)};}finally{item.settled=true;reader.releaseLock();eq(stream.locked,false,'reader lock released');}})());return item;
  }
  writer(stream) {const writer=stream.getWriter(),item={writer,stream,released:false,lifecycle:null};item.lifecycle=this.watch(writer.closed.then(()=>({status:'closed'}),error=>({status:'rejected',error:String(error)})));this.writers.push(item);return writer;}
  async cancel(item,reason) {ok(!item.settled,'cancellation unexpectedly late');item.cancelled=true;await item.reader.cancel(reason);}
  background(entry,id,gate,fail=false) {this.backgroundIds.push(id);return this.watch(entry.background(id,gate,fail));}
  async healthy() {const value=await this.peer.note(this.tag,'recovery');eq(value.owner,await this.peer.inspect(),'post-load owner identity');return value;}
  async cleanup() {
    const failures=[];const attempt=async(label,fn)=>{try{return await fn();}catch(error){failures.push(label+': '+String(error));}};
    this.local.book.releaseAll();for(const cb of this.callbacks)cb.book.releaseAll();
    await attempt('provider gate release',()=>this.peer.unblockForCleanup(this.tag));
    for(const reader of [...this.local.readers]){await attempt('tee reader cancel',()=>reader.cancel('fixture-cleanup'));await attempt('tee reader lock release',()=>{reader.releaseLock();this.local.readers.delete(reader);});}
    for(const item of this.drains)if(!item.settled)await attempt('reader '+item.id,()=>item.reader.cancel('fixture-cleanup'));
    for(const item of this.writers){await attempt('writer abort',()=>item.writer.abort('fixture-cleanup'));await attempt('writer lock release',()=>{item.writer.releaseLock();item.released=true;eq(item.stream.locked,false,'writer lock remains held');});}
    const remote=await attempt('provider cleanup',()=>this.peer.cleanup(this.tag,this.backgroundIds));
    await attempt('pending settlement',()=>Promise.allSettled(this.pending));
    const finalRemote=await attempt('provider final cleanup',()=>this.peer.finishCleanup(this.tag));
    for(const e of this.entries)await attempt('entrypoint dispose',()=>drop(e));
    for(const w of this.workers)await attempt('worker dispose',()=>w.dispose());
    for(const cb of this.callbacks)await attempt('callback dispose',()=>drop(cb.stub));
    for(const cb of this.callbacks)await attempt('callback cohort terminal',async()=>{await cb.book.wait('callback-disposed');eq(cb.book.counts['callback-disposed'],1,'callback destructor count');eq(cb.target.active,0,'callback still active');});
    for(const value of this.local.sources.values())if(!value.closed&&!value.cancelled&&!value.error){value.error='fixture-cleanup';try{value.controller.error(new Error(value.error));}catch{}}
    ok(this.local.readers.size===0,'local reader set remains nonempty');for(const item of this.drains)eq(item.stream.locked,false,'drain lock remains held after cleanup');for(const item of this.writers)eq(item.stream.locked,false,'writer lock remains held after cleanup');
    ok(failures.length===0,'CLEANUP_FAILURE: '+JSON.stringify(failures));return {status:'ok',remote,finalRemote,callbacks:this.callbacks.map(c=>({disposed:c.book.counts['callback-disposed'],active:c.target.active,maxActive:c.target.maxActive})),workerHandles:this.workers.length,entrypointHandles:this.entries.length,localReaderCount:this.local.readers.size,drains:this.drains.map(x=>({id:x.id,settled:x.settled,readCalls:x.readCalls,locked:x.stream.locked})),writers:await Promise.all(this.writers.map(async x=>({released:x.released,locked:x.stream.locked,lifecycle:await x.lifecycle}))),localSources:snapshot(this.local).sources};
  }
}
