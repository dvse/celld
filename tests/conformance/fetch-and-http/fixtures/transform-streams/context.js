import {ok,eq,same,hex,bound,collect,ScheduleBlocked,AssertionFailure,registerPromise} from './common.js';

const detail=(origin,error)=>({origin,name:error?.name??'Error',message:String(error),schedule:error instanceof ScheduleBlocked});
export class Context {
 constructor(cell,requestId,nativeLimit){
  this.cell=cell;this.requestId=requestId;this.nativeLimit=nativeLimit;
  this.resources=[];this.handles=[];this.records=[];this.stoppers=[];this.expectedErrors=new Set();
  this.totalBytes=0;this.openCount=0;this.maxOpen=0;this.nativeCalls=0;
  this.closing=false;this.disposed=false;this.jsDisposed=false;this.bodyRecord=null;this.cleanupReport=null;
 }
 checkOpen(){ok(!this.closing,'context is closing; no new body work permitted');}
 charge(n){this.totalBytes+=n;ok(this.totalBytes<=2097152,'per-recipient 2MiB byte cap');}
 acceptExpected(error){
  this.expectedErrors.add(error);
  for(const t of this.resources)if(t.kind==='digest'&&t.digestRecord?.status==='rejected'&&t.digestRecord.error===error)this.retire(t,'digest-result-verified-rejection');
 }
 track(p,role='operation'){
  const q=Promise.resolve(p),existing=this.records.find(r=>r.promise===q);if(existing)return q;
  ok(this.records.length<128,'finite promise bound');const r={promise:q,role,status:'pending',error:null};this.records.push(r);registerPromise(q,this);
  q.then(value=>{r.status='fulfilled';r.value=value;},error=>{r.status='rejected';r.error=error;});return q;
 }
 startBody(fn,onSettled){
  this.checkOpen();ok(!this.bodyRecord,'one original body');
  const p=this.track(Promise.resolve().then(fn),'body');this.bodyRecord=this.records.find(r=>r.promise===p);
  p.then(onSettled,onSettled);return p;
 }
 ownStopper(label,fn){this.checkOpen();ok(this.stoppers.length<4,'source stopper bound');this.stoppers.push({label,fn,settled:false});}
 collect(reader){this.checkOpen();return this.track(collect(reader,n=>this.charge(n)),'collector');}
 async until(predicate,label){for(let i=0;i<64;i++){this.checkOpen();if(predicate())return;await this.track(new Promise(resolve=>setTimeout(resolve,2)),'local-yield');}throw new ScheduleBlocked(label+' not observed');}
 async hold(label){this.checkOpen();const p=this.track(this.cell.control().hold(this.cell.runToken,label,this.cell.identity(),this.requestId,this.openCount),'hold');const value=await p;this.checkOpen();return value;}
 allocate(){this.checkOpen();ok(this.openCount<this.nativeLimit,'simultaneous native-operation quota');ok(this.resources.length<12,'native lifecycle creation bound');this.openCount++;this.maxOpen=Math.max(this.maxOpen,this.openCount);}
 retire(t,proof){
  const supported=(proof==='writer-close-fulfilled'&&['zlib','digest'].includes(t.kind))||(proof==='reader-cancel-fulfilled'&&t.kind==='zlib')||(['digest-result-fulfilled','digest-result-verified-rejection'].includes(proof)&&t.kind==='digest');
  if(!supported)return false;
  if(proof==='reader-cancel-fulfilled'&&t.closePending){t.cancelObservedDuringClose=true;return false;}
  if(!t.terminal){t.terminal=true;t.retirementProof=proof;this.openCount--;}return true;
 }
 native(fn){
  // The public Promise itself is registered, not just the inner host-operation Promise.
  const publicPromise=(async()=>{
   this.checkOpen();ok(++this.nativeCalls<=16,'finite one-shot native calls');this.allocate();
   try{this.charge(8192);const value=await this.track(fn(),'one-shot-native');this.checkOpen();if(value instanceof ArrayBuffer||ArrayBuffer.isView(value)){ok(value.byteLength<=262144,'native output cap');this.charge(value.byteLength);}return value;}finally{this.openCount--;}
  })();
  return this.track(publicPromise,'one-shot-public');
 }
 releaseHandle(h){
  h.releaseClosedWasPending=h.closed==='pending';
  h.raw.releaseLock();ok(h.stream?.locked===false,'released fixture handle must be visibly unlocked');h.released=true;
 }
 releaseObservationExpected(record){
  const h=this.handles.find(h=>h.closedPromise===record.promise);
  return !!h&&h.kind==='writer'&&h.released&&h.releaseClosedWasPending&&record.error?.name==='TypeError'&&record.error?.message==='This WritableStream writer has been released.';
 }
 handle(raw,kind,t=null,stream=null){
  this.checkOpen();ok(this.handles.length<32,'owned handle bound');stream??=t?(kind==='writer'?(t.stream.writable??t.stream):t.stream.readable):null;const h={raw,kind,t,stream,released:false,closed:'pending',closedError:null,releaseClosedWasPending:false,cleanupActions:[]};this.handles.push(h);
  // JS terminal state alone proves no native transition. Retain every unexpected rejection.
  h.closedPromise=this.track(raw.closed,'closed-observation');
  h.closedPromise.then(()=>{h.closed='fulfilled';},e=>{h.closed='rejected';h.closedError=e;});
  return h;
 }
 wrapReader(raw,t=null,stream=null){
  const c=this,h=this.handle(raw,'reader',t,stream);const reader={
   get closed(){return raw.closed;},
   read(...args){c.checkOpen();return c.track(raw.read(...args),'read');},
   cancel(reason){c.checkOpen();return c.track(Promise.resolve(raw.cancel(reason)).then(value=>{if(t)c.retire(t,'reader-cancel-fulfilled');return value;}),'cancel');},
   releaseLock(){c.checkOpen();c.releaseHandle(h);},
   _handle:h
  };return reader;
 }
 ownReader(raw,stream){this.checkOpen();return this.wrapReader(raw,null,stream);}
 wrapWriter(raw,t){
  const c=this,h=this.handle(raw,'writer',t);return {
   get closed(){return raw.closed;},
   write(value){c.checkOpen();c.charge(typeof value==='string'?new TextEncoder().encode(value).length:value?.byteLength??0);return c.track(raw.write(value),'write');},
   close(){c.checkOpen();t.closePending=true;return c.track(Promise.resolve(raw.close()).then(value=>{t.closePending=false;c.retire(t,'writer-close-fulfilled');return value;},error=>{t.closePending=false;if(t.cancelObservedDuringClose)c.retire(t,'reader-cancel-fulfilled');throw error;}),'close');},
   abort(reason){c.checkOpen();return c.track(raw.abort(reason),'abort');},
   releaseLock(){c.checkOpen();c.releaseHandle(h);},_handle:h
  };
 }
 open(format,decompress=false,drain=true){
  this.allocate();const t={kind:'zlib',stream:null,reader:null,terminal:false,retirementProof:null,observedOutputBytes:0};this.resources.push(t);
  t.stream=decompress?new DecompressionStream(format):new CompressionStream(format);
  let writer;Object.defineProperty(t,'writer',{get:()=>writer,set:raw=>{this.checkOpen();writer=this.wrapWriter(raw,t);}});
  t.writer=t.stream.writable.getWriter();t.reader=this.wrapReader(t.stream.readable.getReader(),t);
  t.output=drain?this.track(collect(t.reader,n=>{this.charge(n);t.observedOutputBytes+=n;}),'collector'):null;return t;
 }
 digest(){
  this.allocate();const t={kind:'digest',stream:null,reader:null,terminal:false,retirementProof:null};this.resources.push(t);t.stream=new crypto.DigestStream('SHA-1');
  let writer;Object.defineProperty(t,'writer',{get:()=>writer,set:raw=>{this.checkOpen();writer=this.wrapWriter(raw,t);}});t.writer=t.stream.getWriter();this.charge(20);const result=this.track(t.stream.digest,'digest-result');t.digestRecord=this.records.find(r=>r.promise===result);result.then(()=>this.retire(t,'digest-result-fulfilled'),error=>{if(this.expectedErrors.has(error))this.retire(t,'digest-result-verified-rejection');});return t;
 }
 sink(t){
  this.checkOpen();t.acceptedInputBytes=0;const c=this;
  return new WritableStream({
   async write(value){await t.writer.write(value);t.acceptedInputBytes+=value.byteLength;},
   close(){return t.writer.close();},
   abort(reason){
    // Abort is a destination shutdown callback, also allowed during owned cleanup.
    const h=t.writer._handle;return c.track(h.raw.abort(reason),'sink-abort');
   }
  });
 }
 pipe(source,destination){this.checkOpen();return this.track(source.pipeTo(destination),'pipe');}
 async decodeChecked(format,input,expected){const t=this.open(format,true);await t.writer.write(input);await t.writer.close();same(await t.output,expected,'fixed public vector decoded exactly');}
 async roundtrip(encoded,format,expected){this.checkOpen();ok(encoded.length>0&&encoded.length<=262144,'finite encoded bytes');await this.decodeChecked(format,encoded,expected);}
 async encodeChecked(format,input){const t=this.open(format);await t.writer.write(input);await t.writer.close();await this.roundtrip(await t.output,format,input);}
 async digestChecked(input,expected){const d=this.digest();await d.writer.write(input);await d.writer.close();eq(hex(await d.stream.digest),expected,'independent SHA1 vector');}
 failures(){return this.records.filter(r=>r.status==='rejected'&&!this.expectedErrors.has(r.error)&&!(r.role==='closed-observation'&&this.releaseObservationExpected(r))).map(r=>detail(r.role,r.error));}
 snapshot(){return {pending:this.records.filter(r=>r.status==='pending').length,bodyPending:this.bodyRecord?.status==='pending',bodyStarted:!!this.bodyRecord,unreleasedHandles:this.handles.filter(h=>!h.released).length,openOperations:this.openCount,nativeUnresolved:this.resources.filter(t=>!t.terminal).length};}
 async cleanup(){
  if(this.cleanupReport)return this.cleanupReport;this.closing=true;
  const reason=new Error('fixture-owned cleanup');const failures=[],actions=[];
  const attempt=async(origin,fn)=>{
   let original;try{original=Promise.resolve(fn());}catch(error){original=Promise.reject(error);}
   const action={origin,status:'pending'};actions.push(action);this.track(original,'cleanup-action');
   original.then(()=>action.status='fulfilled',error=>{action.status='rejected';action.error=detail(origin,error);});
   try{await bound(original,500,origin+' cleanup bound');if(origin==='writer-abort'||origin==='reader-cancel'||origin.startsWith('source-stop:'))this.acceptExpected(reason);return true;}catch(error){failures.push(detail(origin,error));return false;}
  };
  // Every shutdown and every release is attempted independently, even after another action times out.
  const workers=[];
  for(const s of this.stoppers)workers.push((async()=>{s.settled=await attempt('source-stop:'+s.label,()=>s.fn(reason));})());
  for(const h of this.handles)workers.push((async()=>{
   if(h.released)return;
   if(h.closed==='pending'||(h.t&&!h.t.terminal)){
    const stopped=await attempt(h.kind==='writer'?'writer-abort':'reader-cancel',()=>h.kind==='writer'?h.raw.abort(reason):h.raw.cancel(reason));
    if(stopped&&h.t&&h.kind==='reader')this.retire(h.t,'reader-cancel-fulfilled');
   }
   // An unresolved native transform still gets a public cancel attempt after JS error; release is independent.
   const released=await attempt(h.kind+'-release',()=>this.releaseHandle(h));
   if(!released)h.released=false;
  })());
  for(const worker of workers)this.track(worker,'cleanup-worker');
  try{const outcomes=await bound(Promise.allSettled(workers),1200,'independent shutdown workers');for(const outcome of outcomes)if(outcome.status==='rejected')failures.push(detail('cleanup-worker',outcome.reason));}catch(error){failures.push(detail('shutdown-workers',error));}
  // This includes the ORIGINAL body, native operations, reads, holds and cleanup actions.
  // Timeout wrappers do not replace those records or decrement their pending counters.
  try{await bound(Promise.allSettled(this.records.map(r=>r.promise)),2000,'original body and promise drain');}catch(error){failures.push(detail('promise-drain',error));}
  const residual=this.snapshot();for(const action of actions)if(action.status==='rejected')failures.push(action.error);
  if(residual.pending||residual.bodyPending||residual.unreleasedHandles||residual.openOperations>residual.nativeUnresolved)failures.push({origin:'residual-resources',name:'FixtureAssertion',message:JSON.stringify(residual),schedule:false});
  const unexpected=this.failures();const cleanupUnexpected=unexpected.filter(e=>e.origin==='cleanup-action'||e.origin==='closed-observation');failures.push(...cleanupUnexpected);
  this.jsDisposed=failures.length===0&&residual.pending===0&&!residual.bodyPending&&residual.unreleasedHandles===0;
  this.disposed=this.jsDisposed&&residual.openOperations===0&&residual.nativeUnresolved===0;
  const status=this.disposed?'ok':this.jsDisposed?'BLOCKED_NATIVE_CLEANUP':'FAIL';
  const report={status,run:this.cell.runToken,requestId:this.requestId,recipient:this.cell.identity(),...residual,jsDisposed:this.jsDisposed,disposed:this.disposed,fixtureHandlesReleased:this.handles.filter(h=>h.released).length,maxOpenOperations:this.maxOpen,totalBytes:this.totalBytes,actions:actions.map(({origin,status,error})=>({origin,status,error})),failures,unhandledRejections:unexpected,nativeResources:this.resources.map(t=>({kind:t.kind??'unknown',retired:t.terminal===true,proof:t.retirementProof??null})),nativeRegistryReclamation:'whole-registry-unobserved-external-teardown-required'};
  this.cleanupReport=report;return report;
 }
}
