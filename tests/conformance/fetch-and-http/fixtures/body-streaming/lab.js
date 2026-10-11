import { PROFILE, LIMITS, check, ident, bytes, join, equal, hash, gate, bounded, requireReady } from './common.js';
class NativeHttpFailure extends Error {
  constructor(error, operation) { super(String(error)); this.name='NativeHttpFailure'; this.operation=operation; this.original=error; this.originalName=error?.name; this.originalMessage=error?.message; }
}
export class Lab {
  async nativeRead(reader) { try { return await reader.read(); } catch(error) { throw new NativeHttpFailure(error,'reader.read'); } }
  constructor(input,caller,origin) {this.input=input;this.caller=caller;this.origin=origin;this.root=ident(input.recipient);this.run=ident(input.run);this.responses=new Set();this.branches=new Set();this.localGates=[];this.closing=false;this.readers=new Set();this.controllers=new Set();this.tasks=[];this.events=[];this.calls=0;this.live=0;this.maxLive=0;this.logical=0;this.started=Date.now();this.expected=new Map();this.pending=new Set();}
  note(kind,data={}) {check(this.events.length<256,'caller event bound');this.events.push({seq:this.events.length+1,kind,...data});}
  async net(path,init={}) {
    check(!this.closing||init.__cleanup===true,'case closing');const cleanup=init.__cleanup;delete init.__cleanup;check(++this.calls<=160,'HTTP attempt bound');check(++this.live<=LIMITS.networkRequests,'simultaneous HTTP bound');this.maxLive=Math.max(this.maxLive,this.live);
    let response;const controller=this.controller();if(init.signal){const supplied=init.signal;if(supplied.aborted)controller.abort(supplied.reason);else supplied.addEventListener('abort',()=>controller.abort(supplied.reason),{once:true});}init.signal=controller.signal;
    try {response=await fetch(this.origin+'/root/'+this.root+'/'+path,{redirect:'error',...init});this.responses.add(response);return response;}
    catch(error){this.live--;throw new NativeHttpFailure(error,'fetch');}
  }
  finish(response) {if(this.responses.delete(response))this.live--;}
  async raw(response) {
    check(response.body,'expected HTTP body');const reader=response.body.getReader();this.readers.add(reader);const parts=[];let total=0;
    try {for(let i=0;i<LIMITS.readOperations;i++){const value=await this.nativeRead(reader);if(value.done){check((await this.nativeRead(reader)).done,'EOF must remain terminal');return join(parts);}const part=new Uint8Array(value.value);total+=part.length;check(total<=LIMITS.operationBytes,'client body bound');parts.push(part);}throw new Error('client read bound');}
    finally {try{await reader.cancel('reader cleanup');}catch{}reader.releaseLock();this.readers.delete(reader);this.finish(response);}
  }
  async control(action,extra={}) {const r=await this.net('control',{method:'POST',body:JSON.stringify({run:this.run,action,...extra}),__cleanup:action==='cleanup',headers:{'content-type':'application/json'}});check(r.status===200,'control response status');return JSON.parse(new TextDecoder().decode(await this.raw(r)));}
  async init() {requireReady(typeof fetch==='function'&&typeof ReadableStream==='function'&&typeof AbortController==='function'&&typeof crypto?.subtle?.digest==='function','required native HTTP/stream/abort/hash APIs unavailable');const r=await this.net('identity');this.owner=JSON.parse(new TextDecoder().decode(await this.raw(r)));requireReady(this.owner.profile===PROFILE,'profile identity');requireReady(this.owner.root!==this.caller.root&&this.owner.isolate!==this.caller.isolate,'distinct caller/recipient witnesses');requireReady(['root','isolate','profile'].every(k=>this.owner[k]===this.input.expectedRecipient?.[k]),'supervisor recipient placement witness');requireReady(['root','isolate','profile'].every(k=>this.caller[k]===this.input.expectedCaller?.[k]),'supervisor caller placement witness');const s=await this.control('snapshot');requireReady(s.run===this.run&&s.ops.length===0&&s.active===0,'fresh correlated recipient state');this.note('identities',{caller:this.caller,recipient:this.owner});}
  async config(name,kind,options={}) {ident(name);const c={name,kind,n:32768,label:name,...options};this.logical+=c.n*4;check(this.logical<=LIMITS.payloadBytes,'cumulative routed payload allowance');this.expected.set(name,c);await this.control('configure',{config:c});return c;}
  async release(...names) {return this.control('release',{names});}
  async stop(name) {return this.control('stop',{name});}
  async snapshot() {return this.control('snapshot');}
  async wait(name,predicate,description) {
    for(let attempt=0;attempt<40;attempt++){const s=await this.snapshot(),op=s.ops.find(o=>o.name===name);if(op&&predicate(op)){this.note('barrier',{name,description});return op;}await new Promise(r=>setTimeout(r,20));}
    throw new Error('unreached finite barrier: '+name+' '+description);
  }
  watch(promise) {const task=promise.then(value=>({ok:true,value}),error=>({ok:false,error:String(error),nativeOperation:error instanceof NativeHttpFailure?error.operation:null,original:error instanceof NativeHttpFailure?error.original:null,errorName:error instanceof NativeHttpFailure?error.originalName:null,errorMessage:error instanceof NativeHttpFailure?error.originalMessage:null}));this.tasks.push(task);this.pending.add(task);task.then(()=>this.pending.delete(task));return task;}
  async success(task) {const result=await bounded(task,5000,'HTTP task');check(result.ok,'unexpected task rejection: '+result.error);return result.value;}
  async failure(task,expected={}) {const result=await bounded(task,5000,'expected rejection');check(!result.ok,'expected rejection became success');check(result.nativeOperation==='fetch'||result.nativeOperation==='reader.read','expected native rejection instead received helper/assertion failure: '+result.error);if('same' in expected)check(result.original===expected.same,'native rejection lost expected reason identity');if(expected.name)check(result.errorName===expected.name,'unexpected native error name');if(expected.message)check(result.errorMessage===expected.message,'unexpected native error message');this.note('expected-error',{error:result.error,nativeOperation:result.nativeOperation,errorName:result.errorName,errorMessage:result.errorMessage});return result.error;}
  localGate() {const g=gate();this.localGates.push(g);return g;}
  controller() {const c=new AbortController();this.controllers.add(c);return c;}
  async open(name,init={}) {const r=await this.net('op/'+name,init);check(r.headers.get('x-http-case-op')===name&&r.headers.get('x-http-run')===this.run,'HTTP response correlation');check(r.headers.get('x-http-root')===this.owner.root&&r.headers.get('x-http-isolate')===this.owner.isolate,'HTTP recipient identity');return r;}
  async download(name) {const r=await this.open(name);check(r.status===200,'download status');const value=await this.raw(r);const c=this.expected.get(name);equal(value,bytes(c.label,c.n),name+' response');this.note('download',{name,bytes:value.length,hash:await hash(value)});return value;}
  async receipt(response,name,status=200) {
    check(response.status===status,'upload response status');const c=this.expected.get(name);
    if(status===204){if(response.body)check((await this.raw(response)).length===0,'204 body');else this.finish(response);return;}
    const v=JSON.parse(new TextDecoder().decode(await this.raw(response)));check(v.name===name&&v.run===this.run&&v.effect===1&&v.bytes===c.n&&v.hash===await hash(bytes(c.label,c.n))&&v.root===this.owner.root&&v.isolate===this.owner.isolate,'receipt byte/effect identity');return v;
  }
  async upload(name,body,options={}) {const c=this.expected.get(name);const r=await this.open(name,{method:'POST',body:body===undefined?bytes(c.label,c.n):body,...options});return this.receipt(r,name,c.kind==='empty'?204:200);}
  async relay(source,target,options={}) {const r=await this.open(source);try{return await this.upload(target,r.body,options);}finally{try{if(r.body&&!r.body.locked)await r.body.cancel('relay terminal');}catch{}this.finish(r);}}
  async echo(name,body) {const c=this.expected.get(name),r=await this.open(name,{method:'POST',body});check(r.status===200,'echo status');const value=await this.raw(r);equal(value,bytes(c.label,c.n),'echo HTTP bytes');return value;}
  async prefix(response,count) {
    const reader=response.body.getReader();this.readers.add(reader);const parts=[];let total=0;
    for(let reads=0;total<count;reads++){check(reads<LIMITS.readOperations,'prefix read operation safety bound');const r=await this.nativeRead(reader);check(!r.done,'premature EOF before byte barrier');parts.push(new Uint8Array(r.value));total+=r.value.length;check(total<=LIMITS.operationBytes,'prefix bound');}
    return {response,reader,parts,total};
  }
  async remainder(held,name) {
    try{for(let i=0;i<LIMITS.readOperations;i++){const r=await this.nativeRead(held.reader);if(r.done){check((await this.nativeRead(held.reader)).done,'stable HTTP EOF');const value=join(held.parts),c=this.expected.get(name);equal(value,bytes(c.label,c.n),'held HTTP bytes');return value;}held.parts.push(new Uint8Array(r.value));held.total+=r.value.length;check(held.total<=LIMITS.operationBytes,'remainder bound');}throw new Error('remainder read bound');}
    finally{try{await held.reader.cancel('remainder cleanup');}catch{}held.reader.releaseLock();this.readers.delete(held.reader);this.finish(held.response);}
  }
  async cancel(held) {await held.reader.cancel('consumer intentionally stops');check((await this.nativeRead(held.reader)).done,'cancelled consumer terminal');held.reader.releaseLock();this.readers.delete(held.reader);this.finish(held.response);}
  async effect(name,expected=1) {const s=await this.snapshot(),o=s.ops.find(o=>o.name===name);check(o&&o.effect===expected,'exact effect count '+name);if(expected)check(o.inputTerminal==='eof'&&o.inputHash===await hash(bytes(this.expected.get(name).label,this.expected.get(name).n)),'effect requires exact complete input');return o;}
  async recovery(label='recovery') {await this.config(label,'upload',{n:257});await this.upload(label);await this.effect(label);this.note('recovery',{label});}
  async cleanup() {
    this.closing=true;for(const g of this.localGates)g.resolve();
    for(const c of this.controllers)c.abort(new Error('case cleanup'));
    const failures=[];
    const readers=[...this.readers].map(async reader=>{try{await bounded(reader.cancel('case cleanup'),600,'reader cancel');}catch(error){failures.push('cancel: '+String(error));}try{reader.releaseLock();this.readers.delete(reader);}catch(error){failures.push('release: '+String(error));}});
    const bodies=[...this.branches,...[...this.responses].map(r=>r.body)].filter(Boolean);
    await Promise.all([...readers,...bodies.map(async body=>{if(!body.locked)try{await bounded(body.cancel('case cleanup'),600,'body cancel');this.branches.delete(body);}catch(error){failures.push(String(error));}})]);
    // A dedicated final request is owned even when earlier requests were aborted.
    let remote;try{remote=await this.control('cleanup');}catch(error){failures.push('remote cleanup: '+String(error));}
    try{await bounded(Promise.all(this.tasks),1500,'joining HTTP tasks');}catch(error){failures.push('task join: '+String(error));}
    for(const r of [...this.responses])this.finish(r);
    check(failures.length===0&&this.readers.size===0&&this.pending.size===0,'caller cancellation or settlement incomplete: '+failures.join(';'));
    check(remote.status==='ok'&&remote.run===this.run&&remote.root===this.owner?.root&&remote.isolate===this.owner?.isolate&&remote.active===0&&remote.readers===0&&remote.controllers===0,'recipient cleanup receipt');
    check(this.live===0&&this.responses.size===0,'caller resource cleanup');
    return {status:'ok',remote,local:{live:this.live,readers:0,responses:0,pending:0},tasks:this.tasks.length};
  }
}
