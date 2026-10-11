import {DurableObject} from 'cloudflare:workers';
import {PROFILE,ok,eq,bound,ScheduleBlocked,AssertionFailure,canonical} from './common.js';
import {Context} from './context.js';
import {operations,peers} from './operations.js';

const failure=(origin,error)=>({origin,name:error?.name??'Error',message:String(error),schedule:error instanceof ScheduleBlocked});
const hard=errors=>errors.some(e=>!e.schedule);

export class Cell extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.ctx=ctx;this.env=env;this.token=crypto.randomUUID();this.configured=false;this.active=0;this.contexts=[];}
 identity(){return {root:String(this.ctx.id),instance:this.token,profile:PROFILE};}
 configure(run,coordinator,role){
  ok(!this.configured,'fresh recipient required');ok(typeof CompressionStream==='function'&&typeof DecompressionStream==='function'&&typeof crypto.DigestStream==='function'&&typeof crypto.subtle?.digest==='function'&&typeof crypto.subtle?.sign==='function'&&typeof crypto.DigestStream.prototype[Symbol.dispose]==='function','source-supported native APIs required');
  this.runToken=run;this.coordinator=coordinator;this.role=role;this.configured=true;return {run,role,recipient:this.identity()};
 }
 control(){return this.env.ROOT.getByName(this.coordinator);}
 async operation(run,kind,id,requestId,nativeLimit){
  ok(this.configured&&run===this.runToken,'run mismatch');ok(this.active===0,'one original body per recipient');
  ok((kind==='main'&&Object.hasOwn(operations,id))||(kind==='peer'&&Object.hasOwn(peers,id)),'known operation required');ok(Number.isInteger(nativeLimit)&&nativeLimit>=1&&nativeLimit<=3,'bounded native quota');
  this.active++;const c=new Context(this,requestId,nativeLimit);this.contexts.push(c);const errors=[];let value,cleanup,entered=false,bodyStarted=false;
  try{
   await this.control().note(run,kind+'-enter',id,this.identity(),requestId);entered=true;
   const body=c.startBody(()=>(kind==='main'?operations[id]:peers[id])(c),()=>{this.active--;});bodyStarted=true;
   value=await bound(body,15000,'finite recipient body');
  }catch(error){errors.push(failure('body-or-entry-wait',error));}
  if(!bodyStarted)this.active--;
  try{cleanup=await c.cleanup();errors.push(...cleanup.failures,...c.failures());}
  catch(error){errors.push(failure('unexpected-cleanup',error));cleanup={status:'FAIL',run,requestId,recipient:this.identity(),...c.snapshot(),disposed:false,failures:[failure('unexpected-cleanup',error)]};}
  if(!['ok','BLOCKED_NATIVE_CLEANUP'].includes(cleanup.status)&&!hard(errors))errors.push(failure('cleanup-residual',new AssertionFailure('cleanup incomplete')));
  const nativeBlocked=cleanup.status==='BLOCKED_NATIVE_CLEANUP';const status=hard(errors)?'FAIL':errors.length||nativeBlocked?'BLOCKED':'PASS';
  if(status==='PASS'){
   try{await this.control().note(run,kind+'-done',id,this.identity(),requestId);}
   catch(error){errors.push(failure('terminal-event',error));}
  }
  return {run,kind,id,requestId,recipient:this.identity(),traceEntered:entered&&bodyStarted,status:hard(errors)?'FAIL':errors.length||nativeBlocked?'BLOCKED':'PASS',blocker:nativeBlocked?{type:'BLOCKED_NATIVE_CLEANUP',detail:'Native state absence is unproved; owned teardown required.'}:undefined,value,errors,error:errors[0],cleanup};
 }
 cleanup(run){
  ok(run===this.runToken,'cleanup run mismatch');const residual=this.contexts.map(c=>({disposed:c.disposed,jsDisposed:c.jsDisposed,...c.snapshot()}));
  return {run,recipient:this.identity(),status:this.active===0&&this.contexts.every(c=>c.disposed)?'ok':this.active===0&&this.contexts.every(c=>c.jsDisposed)?'BLOCKED_NATIVE_CLEANUP':'FAIL',active:this.active,contexts:this.contexts.length,allContextsDisposed:this.contexts.every(c=>c.disposed),residual};
 }
}
export const schedules={
 X001:['prefix-encoder','raw'],X002:['trailer-pending','digest'],X003:['decoded-prefix-retained','decode'],X004:['pending-native-read','sign'],
 X005:['unflushed-raw-state','decode'],X006:['encoder-before-source','digest'],X007:['source-tail-error','raw'],X008:['crc-awaiting-validation','digest'],
 X009:['missing-size-trailer','sign'],X010:['eof-before-trailing-write','raw'],X011:['typed-prefix-before-invalid-chunk','decode'],X012:['writer-lock-handoff','digest'],
 X013:['pipe-source-open','decode'],X014:['tee-survivor-open','sign'],X015:['consumer-not-draining','raw'],X016:['good-and-bad-decoder-handles','digest'],
 X018:['pack-header-hashed-list','archiveDigest'],X019:['digest-abort-pending','raw'],X020:['pack-body-source-failure','decode'],
 X021:['digest-close-after-peer-poison','badGzip'],X022:['unlocked-digest-dispose','digest'],X023:['imported-public-fixture-key','raw'],X024:['encoder-survives-crypto-rejections','cryptoErrors']
};

export class Root extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.ctx=ctx;this.env=env;this.token=crypto.randomUUID();this.used=false;this.book=null;}
 identity(){return {root:String(this.ctx.id),instance:this.token,profile:PROFILE};}
 verify(run){ok(this.book?.run===run,'coordinator run mismatch');return this.book;}
 note(run,kind,label,recipient,requestId){
  const b=this.verify(run);ok(b.events.length<64,'event bound');ok(b.allowed.some(x=>canonical(x)===canonical(recipient)),'recipient identity witness');ok(requestId===b.mainId||requestId===b.peerId,'dispatched request ID required');
  b.events.push({run,kind,label,recipient,requestId,sequence:b.events.length});if(kind==='main-enter')b.entryObserved=true;for(const notify of b.waiters)notify();return {run,kind,label};
 }
 async hold(run,label,recipient,requestId,nativeOpen){
  const b=this.verify(run);ok(Number.isInteger(nativeOpen)&&nativeOpen>=0&&nativeOpen<=3,'held native count');ok(!b.hold&&requestId===b.mainId&&label===b.label,'one expected main hold');
  let release;const original=new Promise(resolve=>release=resolve);b.hold={release,settled:false,recipient,requestId,nativeOpen};this.note(run,'held',label,recipient,requestId);
  try{await bound(original,8000,'held native state',ScheduleBlocked);}finally{b.hold.settled=true;}
  return {run,label};
 }
 async waitHeld(){const b=this.book;if(b.hold)return;await bound(new Promise(resolve=>b.waiters.push(()=>{if(b.hold)resolve();})),8000,'actual overlap unavailable',ScheduleBlocked);}
 async run(spec,name){
  const started=Date.now(),caller=this.identity();const errors=[],pending=[],receipts=[],configured=[],remote=[];let value,dispatchAttempted=false;
  const targets=[this.env.CELLS.getByName(spec.primary),this.env.CELLS.getByName(spec.secondary)],expected=[spec.expectedPrimary,spec.expectedSecondary];
  try{
   ok(!this.used,'fresh coordinator required');this.used=true;ok(Object.hasOwn(schedules,spec.id),'unknown case');eq(caller,spec.expectedCaller,'caller identity');ok(spec.primary!==spec.secondary&&expected[0].root!==expected[1].root,'distinct recipient roots');
   const [label,peer]=schedules[spec.id];this.book={run:spec.run,events:[],waiters:[],allowed:expected,mainId:spec.run+':primary:1',peerId:spec.run+':secondary:2',label,hold:null,entryObserved:false};
   for(const [i,target] of targets.entries()){configured.push(i);eq(await target.configure(spec.run,name,i?'secondary':'primary'),{run:spec.run,role:i?'secondary':'primary',recipient:expected[i]},'configured recipient identity');}
   const receive=(promise,i,kind,id,requestId)=>{
    const record={status:'pending',kind};pending.push(record);
    const q=Promise.resolve(promise).then(receipt=>{
     eq(receipt.run,spec.run,'operation run');eq(receipt.recipient,expected[i],'recipient identity');eq([receipt.kind,receipt.id,receipt.requestId],[kind,id,requestId],'actual request correlation');receipts.push(receipt);
     const reported=Array.isArray(receipt.errors)?receipt.errors:receipt.error?[{origin:'legacy-recipient-error',...receipt.error,schedule:receipt.error.name==='ScheduleBlocked'}]:[];
     errors.push(...reported.map(e=>({...e,origin:kind+':'+e.origin})));
     if(!['ok','BLOCKED_NATIVE_CLEANUP'].includes(receipt.cleanup?.status))errors.push(failure(kind+':cleanup',new AssertionFailure('recipient cleanup failed')));
     if(receipt.status!=='PASS'){
      if(receipt.status==='BLOCKED'&&['ok','BLOCKED_NATIVE_CLEANUP'].includes(receipt.cleanup?.status)&&!hard(reported))throw new ScheduleBlocked('recipient schedule unavailable');
      throw new AssertionFailure('recipient body failed: '+JSON.stringify(reported));
     }
     ok(receipt.cleanup?.status==='ok'&&reported.length===0,'PASS receipt contains failure');return receipt.value;
    });record.promise=q;q.then(()=>record.status='fulfilled',error=>{record.status='rejected';record.error=error;});return q;
   };
   dispatchAttempted=true;const main=receive(targets[0].operation(spec.run,'main',spec.id,this.book.mainId,3),0,'main',spec.id,this.book.mainId);await this.waitHeld();
   const peerValue=await receive(targets[1].operation(spec.run,'peer',peer,this.book.peerId,Math.min(3,4-this.book.hold.nativeOpen)),1,'peer',peer,this.book.peerId);
   this.note(spec.run,'released',label,expected[0],this.book.mainId);this.book.hold.release();const mainValue=await main;
   const kinds=this.book.events.map(e=>e.kind),at=k=>kinds.indexOf(k);
   if(!(at('main-enter')<at('held')&&at('held')<at('peer-enter')&&at('peer-enter')<at('peer-done')&&at('peer-done')<at('released')&&at('released')<at('main-done')))throw new ScheduleBlocked('actual causal overlap order missing');
   value={main:mainValue,peer:peerValue};
  }catch(error){errors.push(failure('coordinator-trace',error));}
  const cleanupFailures=[];
  try{if(this.book?.hold)this.book.hold.release();}catch(error){cleanupFailures.push(failure('hold-release',error));}
  try{await bound(Promise.allSettled(pending.map(r=>r.promise)),4000,'coordinator original request drain');}catch(error){cleanupFailures.push(failure('request-drain',error));}
  // Preserve every non-schedule rejection, even if waitHeld already expired.
  for(const r of pending)if(r.status==='rejected')errors.push(failure(r.kind+':request',r.error));
  for(const i of configured){
   try{const result=await bound(targets[i].cleanup(spec.run),1000,'recipient terminal cleanup');eq(result.run,spec.run,'cleanup run');eq(result.recipient,expected[i],'cleanup identity');remote.push(result);if(!['ok','BLOCKED_NATIVE_CLEANUP'].includes(result.status))cleanupFailures.push(failure('recipient-terminal',new AssertionFailure('recipient still owns work')));}
   catch(error){remote.push({status:'FAIL',error:String(error)});cleanupFailures.push(failure('recipient-cleanup-request',error));}
  }
  const pendingCount=pending.filter(r=>r.status==='pending').length,held=this.book?.hold&&!this.book.hold.settled?1:0;
  const nativeBlocked=receipts.some(r=>r.cleanup?.status==='BLOCKED_NATIVE_CLEANUP')||remote.some(r=>r.status==='BLOCKED_NATIVE_CLEANUP');
  const drained=!cleanupFailures.length&&!pendingCount&&!held&&remote.length===2&&remote.every(r=>['ok','BLOCKED_NATIVE_CLEANUP'].includes(r.status));
  const cleanup={run:spec.run,status:drained?(nativeBlocked?'BLOCKED_NATIVE_CLEANUP':'ok'):'FAIL',pending:pendingCount,held,remote,failures:cleanupFailures};errors.push(...cleanupFailures);
  const mainReceipt=receipts.find(r=>r.kind==='main'),entered=mainReceipt?.traceEntered===true,unknown=dispatchAttempted&&!mainReceipt;
  const witnessedBodyFailure=receipts.some(r=>r.traceEntered===true&&r.status==='FAIL');let status='PASS',phase='complete',blocker;
  if(witnessedBodyFailure||(entered&&(hard(errors)||cleanup.status==='FAIL'))){status='FAIL';phase=cleanup.status==='ok'?'trace':'cleanup';}
  else if(unknown){status='BLOCKED';phase='trace-unknown';blocker={type:'BLOCKED_UNCERTAIN_DISPATCH',detail:'Dispatched main request has no validated terminal body receipt; owned teardown required, do not retry.'};}
  else if(!entered){status='BLOCKED';phase='precondition';blocker={type:'BLOCKED_PREREQUISITE',detail:JSON.stringify(errors)};}
  else if(nativeBlocked){status='BLOCKED';phase='cleanup';blocker={type:'BLOCKED_NATIVE_CLEANUP',detail:'Native state absence remains unproved; require owned teardown, no local PASS.'};}
  else if(errors.length){status='BLOCKED';phase='trace';blocker={type:'BLOCKED_SCHEDULE',detail:JSON.stringify(errors)};}
  return {id:spec.id,run:spec.run,profile:PROFILE,caller,recipients:{primary:expected[0],secondary:expected[1]},status,phase,traceEntered:entered,dispatchAttempted,traceEntryUnknown:unknown,bodyEntryObserved:this.book?.entryObserved===true,bodyReceiptMissing:!mainReceipt,blocker,errors,value,evidence:{events:this.book?.events??[],receipts,wallMs:Date.now()-started},cleanup,qualification:'PENDING_EXTERNAL_SUPERVISOR_REVIEW'};
 }
}
