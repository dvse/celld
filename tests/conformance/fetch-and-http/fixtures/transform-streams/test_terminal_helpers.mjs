// Tiny inert mocks for XREV-08/09. No X case body, native API, SUT or network runs.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const here=new URL('.',import.meta.url),read=name=>fs.readFileSync(new URL(name,here),'utf8');
const common=await import('data:text/javascript;base64,'+Buffer.from(read('common.js')).toString('base64'));
const cc=read('context.js').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
const fc=read('fixture.js').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
function load(operations,extra={}){const deps={...common,DurableObject:class {},crypto:{randomUUID:()=> 'mock'},operations,peers:{raw:async()=>({fake:true})},...extra};const Context=Function(...Object.keys(deps),cc+'\nreturn Context;')(...Object.values(deps));return Function(...Object.keys(deps),'Context',fc+'\nreturn {Cell,Root};')(...Object.values(deps),Context);}
const tick=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
async function run(body){const {Cell}=load({X001:body});const cell=new Cell({id:'p'},{ROOT:{getByName:()=>({note:async()=>({})})}});cell.configured=true;cell.runToken='r';cell.coordinator='root';return {receipt:await cell.operation('r','main','X001','request',3),cell};}
let checks=0;
{
 const {receipt}=await run(async c=>{const e=new TypeError('planned fake native');await common.rejection(c.native(()=>Promise.reject(e)),v=>v===e,'actual public native wrapper');return {fake:true};});
 assert.equal(receipt.status,'PASS');assert.deepEqual(receipt.errors,[]);checks++;
}
{
 const expected=new Error('expected'),different=new Error('different');
 const {receipt}=await run(async c=>{await common.rejection(c.native(()=>Promise.reject(different)),v=>v===expected,'wrong error');return {fake:true};});
 assert.equal(receipt.status,'FAIL');assert.ok(receipt.errors.some(e=>e.origin==='one-shot-native'&&e.message.includes('different')));checks++;
}
{
 const {receipt}=await run(async c=>{try{await c.native(()=>Promise.reject(new Error('unasserted native')));}catch{}return {fake:true};});
 assert.equal(receipt.status,'FAIL');assert.ok(receipt.errors.some(e=>e.origin==='one-shot-public'));checks++;
}
{
 let aborts=0;
 const {receipt}=await run(async c=>{const owner={locked:true},t={terminal:false,stream:{writable:owner}};c.resources.push(t);c.openCount=1;c.maxOpen=1;
  c.handle({closed:Promise.reject(new Error('unexpected closed')),abort:async()=>{aborts++;},releaseLock(){owner.locked=false;}},'writer',t);await tick();assert.equal(c.openCount,1);return {fake:true};});
 assert.equal(receipt.status,'FAIL');assert.equal(aborts,1);assert.equal(receipt.cleanup.openOperations,1);assert.equal(receipt.cleanup.nativeUnresolved,1);assert.equal(receipt.cleanup.disposed,false);assert.ok(receipt.errors.some(e=>e.origin==='closed-observation'));checks++;
}
async function poisonedFixture(withReader,cancelFails=false){let cancels=0;const result=await run(async c=>{
 const e=new TypeError('verified BufferSource validation'),w={locked:true},r={locked:true},t={kind:'zlib',terminal:false,retirementProof:null,stream:{writable:w,readable:r}};c.resources.push(t);c.openCount=1;c.maxOpen=1;
 c.handle({closed:Promise.reject(e),abort:async()=>{},releaseLock(){w.locked=false;}},'writer',t);
 if(withReader)c.handle({closed:Promise.reject(e),cancel:async()=>{cancels++;if(cancelFails)throw new Error('unexpected native cancel failure');},releaseLock(){r.locked=false;}},'reader',t);
 await common.rejection(c.track(Promise.reject(e)),v=>v===e,'known poisoned write');await tick();assert.equal(c.openCount,1);assert.equal(t.terminal,false);return {fake:true};
 });return {...result,cancels};}
{
 const {receipt,cancels}=await poisonedFixture(true);assert.equal(receipt.status,'PASS');assert.equal(cancels,1);assert.equal(receipt.cleanup.nativeUnresolved,0);assert.equal(receipt.cleanup.nativeResources[0].proof,'reader-cancel-fulfilled');checks++;
}
{
 const {receipt,cell}=await poisonedFixture(false);assert.equal(receipt.status,'BLOCKED');assert.equal(receipt.blocker.type,'BLOCKED_NATIVE_CLEANUP');assert.equal(receipt.cleanup.jsDisposed,true);assert.equal(receipt.cleanup.disposed,false);assert.equal(receipt.cleanup.nativeUnresolved,1);assert.equal(cell.cleanup('r').status,'BLOCKED_NATIVE_CLEANUP');checks++;
}
{
 const {receipt,cancels}=await poisonedFixture(true,true);assert.equal(receipt.status,'FAIL');assert.equal(cancels,1);assert.equal(receipt.cleanup.nativeUnresolved,1);assert.equal(receipt.cleanup.nativeResources[0].proof,null);checks++;
}
{
 const {receipt}=await run(async c=>{let reject;const owner={locked:true},p=new Promise((_,r)=>reject=r);const h=c.handle({closed:p,releaseLock(){owner.locked=false;reject(new TypeError('This WritableStream writer has been released.'));}},'writer',null,owner);c.releaseHandle(h);await tick();return {fake:true};});
 assert.equal(receipt.status,'PASS');assert.deepEqual(receipt.errors,[]);checks++;
}
{
 const {receipt}=await run(async c=>{let reject;const owner={locked:true},p=new Promise((_,r)=>reject=r);const h=c.handle({closed:p,releaseLock(){owner.locked=false;reject(new Error('unrelated after release'));}},'writer',null,owner);c.releaseHandle(h);await tick();return {fake:true};});
 assert.equal(receipt.status,'FAIL');assert.ok(receipt.errors.some(e=>e.origin==='closed-observation'));checks++;
}
{
 const {receipt}=await run(async c=>{const owner={locked:true},h=c.handle({closed:Promise.reject(new TypeError('This WritableStream writer has been released.')),releaseLock(){owner.locked=false;}},'writer',null,owner);await tick();c.releaseHandle(h);return {fake:true};});
 assert.equal(receipt.status,'FAIL');checks++;
}
{
 const {receipt}=await run(async c=>{let resolve;const owner={locked:true},closed=new Promise(r=>resolve=r),t={kind:'zlib',terminal:false,retirementProof:null,stream:{writable:owner}};c.resources.push(t);c.openCount=1;c.maxOpen=1;
  const writer=c.wrapWriter({closed,close:async()=>{resolve();},releaseLock(){owner.locked=false;}},t);await writer.close();assert.equal(t.retirementProof,'writer-close-fulfilled');return {fake:true};});
 assert.equal(receipt.status,'PASS');assert.equal(receipt.cleanup.nativeUnresolved,0);checks++;
}
{
 let root;const runId='0123456789abcdef',id=role=>({root:role,instance:role,profile:common.PROFILE});
 const caller=id('caller'),primary=id('primary'),secondary=id('secondary');
 const bounded=(p,ms,label,Type=common.AssertionFailure)=>label==='actual overlap unavailable'?Promise.reject(new Type('fake no hold')):p;
 const {Root}=load({X001:async()=>({})},{bound:bounded});
 const stub=(role,recipient)=>({configure:async()=>({run:runId,role,recipient}),cleanup:async()=>({run:runId,recipient,status:role==='primary'?'BLOCKED_NATIVE_CLEANUP':'ok',active:0,contexts:1,allContextsDisposed:role!=='primary'}),operation:async(run,kind,op,requestId)=>{root.note(run,'main-enter',op,recipient,requestId);return {run,kind,id:op,requestId,recipient,traceEntered:true,status:'BLOCKED',errors:[],cleanup:{status:'BLOCKED_NATIVE_CLEANUP'}};}});
 const p=stub('primary',primary),s=stub('secondary',secondary);root=new Root({id:'caller'},{CELLS:{getByName:name=>name==='primary'?p:s}});root.token='caller';
 const receipt=await root.run({id:'X001',run:runId,primary:'primary',secondary:'secondary',expectedCaller:caller,expectedPrimary:primary,expectedSecondary:secondary},'caller');
 assert.equal(receipt.status,'BLOCKED');assert.equal(receipt.blocker.type,'BLOCKED_NATIVE_CLEANUP');assert.equal(receipt.cleanup.status,'BLOCKED_NATIVE_CLEANUP');checks++;
}
{
 const {receipt}=await run(async c=>{
  let finishClose,finishClosed;const w={locked:true},r={locked:true},closed=new Promise(resolve=>finishClosed=resolve),t={kind:'zlib',terminal:false,retirementProof:null,stream:{writable:w,readable:r}};c.resources.push(t);c.openCount=1;c.maxOpen=1;
  const writer=c.wrapWriter({closed,close:()=>new Promise(resolve=>finishClose=()=>{finishClosed();resolve();}),releaseLock(){w.locked=false;}},t);
  const reader=c.wrapReader({closed:Promise.resolve(),cancel:async()=>{},releaseLock(){r.locked=false;}},t);
  const closing=writer.close();await reader.cancel('mock cancellation during flush');assert.equal(c.openCount,1);assert.equal(t.terminal,false);finishClose();await closing;assert.equal(c.openCount,0);return {fake:true};
 });assert.equal(receipt.status,'PASS');checks++;
}
console.log(JSON.stringify({status:'PASS_HELPERS_ONLY',checks,sutRuns:0,xCaseBodiesExecuted:0,nativeOperations:0,networkRequests:0}));
