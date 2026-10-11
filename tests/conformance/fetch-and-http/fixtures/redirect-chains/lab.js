import {PROFILE,LIMITS,check,ready,ident,bytes,equal,join,hash,bounded} from './common.js';
export class NativeFailure extends Error {constructor(error,operation){super(String(error));this.name='NativeFailure';this.original=error;this.operation=operation;}}
export class Lab {
  constructor(input,caller,origin){Object.assign(this,{input,caller,origin,root:ident(input.recipient),run:ident(input.run),started:Date.now(),calls:0,live:0,maxLive:0,logical:0,closing:false});this.expected=new Map();this.responses=new Set();this.readers=new Map();this.controllers=new Set();this.tasks=[];this.pendingNet=new Set();this.events=[];this.cleanupReason=new Error('fixture cleanup abort');}
  note(kind,extra={}){check(this.events.length<256,'caller journal cap');this.events.push({seq:this.events.length+1,kind,...extra});}
  url(name,query=''){ident(name);return this.origin+'/root/'+this.root+'/op/'+(this.expected.get(name)?.route||name)+query;}
  controller(){const c=new AbortController();return c;}
  async net(path,init={},cleanup=false){
    check(!this.closing||cleanup,'coordinator closing');check(++this.calls<=160,'HTTP attempt cap');check(this.live<LIMITS.networkRequests,'simultaneous HTTP cap');this.live++;this.maxLive=Math.max(this.maxLive,this.live);
    const controller=new AbortController(),supplied=init.signal;this.controllers.add(controller);const abort=()=>controller.abort(supplied.reason);
    if(supplied){if(supplied.aborted)abort();else supplied.addEventListener('abort',abort,{once:true});}
    const request=fetch(this.origin+'/root/'+this.root+'/'+path,{redirect:'manual',...init,signal:controller.signal});
    const observed=request.then(value=>({ok:true,value}),error=>({ok:false,error}));this.pendingNet.add(observed);
    try{const result=await observed;if(!result.ok){this.live--;throw new NativeFailure(result.error,'fetch');}const r=result.value;this.responses.add(r);if(this.closing&&!cleanup){await this.cancelResponse(r);throw this.cleanupReason;}return r;}
    finally{this.pendingNet.delete(observed);this.controllers.delete(controller);if(supplied)supplied.removeEventListener('abort',abort);}
  }
  finish(r){if(this.responses.delete(r))this.live--;}
  async nativeRead(reader){try{return await reader.read();}catch(error){throw new NativeFailure(error,'reader.read');}}
  async raw(r){
    if(!r.body){this.finish(r);return new Uint8Array();}const reader=r.body.getReader();this.readers.set(reader,r);const parts=[];let terminal=false;
    try{for(let i=0;i<LIMITS.readOperations;i++){const x=await this.nativeRead(reader);if(x.done){check((await this.nativeRead(reader)).done,'stable EOF');terminal=true;return join(parts);}parts.push(new Uint8Array(x.value));join(parts);}throw new Error('read cap');}
    finally{if(terminal){reader.releaseLock();this.readers.delete(reader);this.finish(r);}}
  }
  async cancelResponse(r){if(r.body){check(!r.body.locked,'cancelResponse requires unlocked body');await bounded(r.body.cancel('fixture body cancellation'),800,'cancel body');}this.finish(r);}
  async control(action,extra={}){const r=await this.net('control',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({run:this.run,action,...extra})},action==='cleanup');check(r.status===200,'control response status');return JSON.parse(new TextDecoder().decode(await this.raw(r)));}
  async init(){ready(typeof fetch==='function'&&typeof ReadableStream==='function'&&typeof AbortController==='function'&&typeof crypto?.subtle?.digest==='function','native APIs unavailable');const r=await this.net('identity');this.owner=JSON.parse(new TextDecoder().decode(await this.raw(r)));ready(this.owner.profile===PROFILE,'recipient profile');ready(this.owner.root!==this.caller.root&&this.owner.isolate!==this.caller.isolate,'distinct coordinator/recipient identities');for(const key of ['root','isolate','profile']){ready(this.caller[key]===this.input.expectedCaller?.[key],'caller placement mismatch');ready(this.owner[key]===this.input.expectedRecipient?.[key],'recipient placement mismatch');}const s=await this.snapshot();ready(s.run===this.run&&s.ops.length===0&&s.active===0&&s.faults.length===0,'fresh recipient');this.note('identities',{caller:this.caller,recipient:this.owner});}
  async config(name,options={}){const c={name,route:name,method:'GET',status:200,inputLabel:name,inputN:0,outputLabel:name,outputN:8193,location:null,query:'',commit:false,...options};this.logical+=4*(c.inputN+c.outputN);check(this.logical<=LIMITS.payloadBytes,'logical payload allowance');this.expected.set(name,c);await this.control('configure',{config:c});return c;}
  async redirect(name,target,options={}){return this.config(name,{status:302,outputN:173,location:this.url(target,this.expected.get(target).query),...options});}
  snapshot(){return this.control('snapshot');}
  release(...names){return this.control('release',{names});}
  stop(name){return this.control('stop',{name});}
  async wait(name,predicate,description){for(let attempt=0;attempt<40;attempt++){const s=await this.snapshot(),o=s.ops.find(x=>x.name===name);check(s.faults.length===0,'recipient fault while waiting: '+s.faults.join(';'));if(o&&predicate(o)){this.note('barrier',{name,description,recipientSequence:s.events.length});return o;}}throw new Error('unreached journal barrier: '+name+' '+description);}
  watch(promise){const record={observed:false,result:null,promise:null};record.promise=promise.then(value=>(record.result={ok:true,value}),error=>(record.result={ok:false,error}));this.tasks.push(record);return record;}
  async success(record){const r=await bounded(record.promise,5000,'owned task');record.observed=true;check(r.ok,'unexpected task rejection: '+String(r.error));return r.value;}
  async aborted(record,reason){const r=await bounded(record.promise,5000,'intentional abort');record.observed=true;check(!r.ok&&r.error instanceof NativeFailure&&r.error.operation==='fetch','abort requires native fetch rejection, not helper failure');check(r.error.original===reason&&reason.message==='F009 planned intermediate abort','exact intentional abort reason');this.note('expected-error',{operation:'fetch',name:reason.name,message:reason.message});}
  async open(start,endpoint=start,init={}){const c=this.expected.get(start);const r=await this.net('op/'+c.route+c.query,init);check(r.headers.get('x-fetch-op')===endpoint&&r.headers.get('x-fetch-run')===this.run,'final endpoint/run identity');check(r.headers.get('x-fetch-root')===this.owner.root&&r.headers.get('x-fetch-isolate')===this.owner.isolate,'final recipient identity');return r;}
  async complete(start,endpoint=start,init={}){const r=await this.open(start,endpoint,init),c=this.expected.get(endpoint);check(r.status===c.status,'terminal response status');equal(await this.raw(r),bytes(c.outputLabel,c.method==='HEAD'?0:c.outputN),'terminal '+endpoint);this.note('complete',{start,endpoint,status:r.status});return r;}
  async expect(name,{entered=1,method,inputN,effect=0}={}){const s=await this.snapshot(),o=s.ops.find(x=>x.name===name),c=this.expected.get(name);check(o&&o.entered===entered,'entry count '+name);check(o.effect===effect,'effect count '+name);if(entered){check(o.method===(method||c.method)&&o.inputTerminal==='eof'&&o.inputBytes===(inputN??c.inputN),'method/input boundary '+name);check(o.inputHash===await hash(bytes(c.inputLabel,c.inputN)),'recipient hash '+name);}return o;}
  async prefix(r,n){check(r.body,'prefix body required');const reader=r.body.getReader();this.readers.set(reader,r);const parts=[];let total=0;for(let i=0;total<n;i++){check(i<LIMITS.readOperations,'prefix read cap');const x=await this.nativeRead(reader);check(!x.done,'prefix premature EOF');const b=new Uint8Array(x.value);parts.push(b);total+=b.length;check(total<=LIMITS.operationBytes,'prefix byte cap');}return {r,reader,parts};}
  async drainHeld(held,name){for(let i=0;i<LIMITS.readOperations;i++){const x=await this.nativeRead(held.reader);if(x.done){check((await this.nativeRead(held.reader)).done,'held stable EOF');const c=this.expected.get(name);equal(join(held.parts),bytes(c.outputLabel,c.outputN),'held '+name);held.reader.releaseLock();this.readers.delete(held.reader);this.finish(held.r);return;}held.parts.push(new Uint8Array(x.value));join(held.parts);}throw new Error('held read cap');}
  async cancelHeld(held){await bounded(held.reader.cancel('manual redirect consumed only prefix'),800,'reader cancel');check((await this.nativeRead(held.reader)).done,'cancelled reader terminal');held.reader.releaseLock();this.readers.delete(held.reader);this.finish(held.r);this.note('reader-cancelled');}
  async probe(){await this.config('probe',{method:'POST',inputN:257,outputN:67,commit:true});await this.complete('probe','probe',{method:'POST',body:bytes('probe',257)});await this.expect('probe',{effect:1});this.note('probe-complete');}
  async recovery(){await this.config('recovery',{method:'POST',inputN:131,outputN:31,commit:true});await this.complete('recovery','recovery',{method:'POST',body:bytes('recovery',131)});await this.expect('recovery',{effect:1});this.note('recovery',{label:'recovery'});}
  async cleanup(){
    this.closing=true;const failures=[];for(const c of this.controllers)c.abort(this.cleanupReason);
    let remote;try{remote=await this.control('cleanup');}catch(error){failures.push('remote: '+String(error));}
    for(const [reader,r] of [...this.readers]){try{await bounded(reader.cancel('owned cleanup'),600,'cleanup reader');reader.releaseLock();this.readers.delete(reader);this.finish(r);}catch(error){failures.push('reader: '+String(error));}}
    try{await bounded(Promise.all([...this.pendingNet]),600,'pending network');}catch(error){failures.push(String(error));}
    for(const r of [...this.responses]){try{await this.cancelResponse(r);}catch(error){failures.push('response: '+String(error));}}
    try{await bounded(Promise.all(this.tasks.map(x=>x.promise)),900,'owned tasks');}catch(error){failures.push(String(error));}
    for(const task of this.tasks){if(task.result&&!task.result.ok&&!task.observed&&task.result.error!==this.cleanupReason&&task.result.error?.original!==this.cleanupReason)failures.push('unobserved task failure: '+String(task.result.error));}
    check(failures.length===0,'cleanup incomplete: '+failures.join(';'));
    check(remote?.status==='ok'&&remote.run===this.run&&remote.root===this.owner?.root&&remote.isolate===this.owner?.isolate&&['active','readers','controllers','pulls'].every(k=>remote[k]===0),'matched remote drain required');
    check(this.live===0&&this.readers.size===0&&this.responses.size===0&&this.controllers.size===0&&this.pendingNet.size===0&&this.tasks.every(x=>x.result),'local resources remain');
    return {status:'ok',remote,local:{live:0,readers:0,responses:0,pending:0,controllers:0},tasks:this.tasks.length};
  }
}
