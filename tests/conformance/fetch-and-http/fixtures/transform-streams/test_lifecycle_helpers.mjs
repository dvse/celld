// Tiny fake-object control tests. Imports are replaced with inert dependencies.
// No X operation body, native transform, DO runtime, SUT or network is executed.
import fs from 'node:fs';
import assert from 'node:assert/strict';
const here=new URL('.',import.meta.url);
const common=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(new URL('./common.js',here))).toString('base64'));
const contextCode=fs.readFileSync(new URL('./context.js',here),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
const fixtureCode=fs.readFileSync(new URL('./fixture.js',here),'utf8').replace(/^import .*;\n/gm,'').replace(/^export /gm,'');
const fakeIdentity=root=>({root,instance:root+'-instance',profile:common.PROFILE});
function load(extra={}){
 const deps={...common,DurableObject:class {},crypto:{randomUUID:()=> 'fake-instance'},operations:{X001:async()=>({fake:true})},peers:{raw:async()=>({fake:true})},...extra};
 const Context=Function(...Object.keys(deps),contextCode+'\nreturn Context;')(...Object.values(deps));
 return Function(...Object.keys(deps),'Context',fixtureCode+'\nreturn {Context,Cell,Root};')(...Object.values(deps),Context);
}
const ticks=async()=>{for(let i=0;i<12;i++)await Promise.resolve();};
const cellStub={runToken:'r',identity:()=>fakeIdentity('p')};
let checks=0;
{
 const {Context}=load();const c=new Context(cellStub,'request',3),attempts=[];
 const fail=label=>()=>{attempts.push(label);throw new Error('unexpected '+label);};
 const t={terminal:false,stream:{writable:{locked:true},readable:{locked:true}}};c.resources.push(t);c.openCount=1;
 c.handle({closed:new Promise(()=>{}),abort:fail('abort'),releaseLock:fail('writer-release')},'writer',t);
 c.handle({closed:new Promise(()=>{}),cancel:fail('cancel'),releaseLock:fail('reader-release')},'reader',t);
 const r=await c.cleanup();assert.equal(r.status,'FAIL');assert.equal(r.disposed,false);assert.equal(r.unreleasedHandles,2);assert.equal(r.openOperations,1);assert.equal(attempts.length,4);assert.equal(r.actions.filter(a=>a.status==='rejected').length,4);checks++;
}
{
 const {Context}=load();const c=new Context(cellStub,'request',3),owner={locked:true};
 c.handle({closed:Promise.resolve(),releaseLock(){}},'reader',null,owner);await ticks();
 const r=await c.cleanup();assert.equal(r.status,'FAIL');assert.equal(r.unreleasedHandles,1);assert.equal(r.disposed,false);checks++;
}
{
 let completeBody,completeAbort;const seen=[];
 const bounded=(p,ms,label,Type=common.AssertionFailure)=>{
  seen.push(label);if(label==='writer-abort cleanup bound'||label==='original body and promise drain')return Promise.reject(new Type('fake pending deadline'));return p;
 };
 const {Context}=load({bound:bounded});const c=new Context(cellStub,'request',3),owner={locked:true},t={terminal:false,stream:{writable:owner}};c.resources.push(t);c.openCount=1;
 c.handle({closed:new Promise(()=>{}),abort:()=>new Promise(resolve=>completeAbort=resolve),releaseLock(){owner.locked=false;}},'writer',t);
 c.startBody(async()=>{await new Promise(resolve=>completeBody=resolve);assert.throws(()=>c.allocate(),/context is closing/);},()=>{});await ticks();
 const r=await c.cleanup();assert.equal(r.status,'FAIL');assert.equal(r.bodyPending,true);assert.ok(r.pending>=2);assert.equal(r.unreleasedHandles,0);assert.equal(r.openOperations,1);assert.ok(seen.includes('writer-release cleanup bound'));assert.ok(seen.includes('original body and promise drain'));assert.equal(c.disposed,false);
 completeAbort();completeBody();await ticks();assert.equal(c.disposed,false);checks++;
}
{
 const bounded=(p,ms,label,Type=common.AssertionFailure)=>label==='actual overlap unavailable'?Promise.reject(new Type('fake no hold')):p;
 const {Root}=load({bound:bounded});let root;const run='0123456789abcdef',caller=fakeIdentity('caller'),primary=fakeIdentity('primary'),secondary=fakeIdentity('secondary');
 const cell=(role,recipient)=>({configure:async()=>({run,role,recipient}),cleanup:async()=>({run,recipient,status:'ok',active:0,contexts:1,allContextsDisposed:true}),operation:async(_run,kind,id,requestId)=>{root.note(run,'main-enter',id,recipient,requestId);return {run,kind,id,requestId,recipient,status:'FAIL',traceEntered:true,errors:[{origin:'body',name:'FixtureAssertion',message:'original oracle assertion',schedule:false}],cleanup:{status:'ok'}};}});
 const p=cell('primary',primary),s=cell('secondary',secondary);root=new Root({id:'caller'},{CELLS:{getByName:name=>name==='primary'?p:s}});root.token=caller.instance;
 const r=await root.run({id:'X001',run,primary:'primary',secondary:'secondary',expectedCaller:caller,expectedPrimary:primary,expectedSecondary:secondary},'caller');
 assert.equal(r.status,'FAIL');assert.ok(r.errors.some(e=>e.message==='original oracle assertion'));assert.ok(r.errors.some(e=>e.schedule));checks++;
}
{
 let complete,resumed=false;
 const bounded=(p,ms,label,Type=common.AssertionFailure)=>['finite recipient body','original body and promise drain'].includes(label)?Promise.reject(new Type('fake body deadline')):p;
 const {Cell}=load({bound:bounded,operations:{X001:async c=>{await new Promise(resolve=>complete=resolve);resumed=true;c.checkOpen();return {};}}});
 const cell=new Cell({id:'primary'},{ROOT:{getByName:()=>({note:async()=>({})})}});cell.configured=true;cell.runToken='r';cell.coordinator='root';
 const r=await cell.operation('r','main','X001','request',3);
 assert.equal(r.status,'FAIL');assert.equal(resumed,false);assert.equal(r.cleanup.status,'FAIL');assert.equal(r.cleanup.bodyPending,true);assert.ok(r.cleanup.pending>=1);assert.equal(cell.active,1);assert.equal(cell.cleanup('r').status,'FAIL');assert.equal(cell.contexts[0].disposed,false);
 complete();await ticks();assert.equal(resumed,true);assert.equal(cell.active,0);assert.equal(cell.contexts[0].disposed,false);checks++;
}
{
 const {Cell}=load({operations:{X001:async c=>{c.track(Promise.reject(new Error('unasserted failure')));return {fake:true};}}});
 const cell=new Cell({id:'primary'},{ROOT:{getByName:()=>({note:async()=>({})})}});cell.configured=true;cell.runToken='r';cell.coordinator='root';const r=await cell.operation('r','main','X001','request',3);
 assert.equal(r.status,'FAIL');assert.ok(r.errors.some(e=>e.message.includes('unasserted failure')));checks++;
}
{
 const {Cell}=load({operations:{X001:async c=>{const e=new Error('expected fixture rejection');await common.rejection(c.track(Promise.reject(e)),v=>v===e,'explicit mock oracle');return {fake:true};}}});
 const cell=new Cell({id:'primary'},{ROOT:{getByName:()=>({note:async()=>({})})}});cell.configured=true;cell.runToken='r';cell.coordinator='root';const r=await cell.operation('r','main','X001','request',3);
 assert.equal(r.status,'PASS');assert.deepEqual(r.errors,[]);assert.equal(r.cleanup.bodyPending,false);assert.equal(r.cleanup.disposed,true);assert.equal(cell.active,0);checks++;
}
console.log(JSON.stringify({status:'PASS_HELPERS_ONLY',checks,sutRuns:0,xCaseBodiesExecuted:0,nativeOperations:0,networkRequests:0}));
