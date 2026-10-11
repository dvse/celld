import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const result=await evaluate(`
(async()=>{
 const __checkStubOwner=()=>{},__stubDisposedError=()=>Error('disposed');
 let pending, canceledPackets=0, revivedPackets=0;
 const __capability_packet_cancel=()=>{canceledPackets++;};
 const __rpcDes=reply=>{revivedPackets++;return reply;};
 const __opTrack=()=>()=>{};
 const __disposeStub=owner=>{if(!owner.disposed){owner.disposed=true;owner.entry.refs--;}};
 const __dispatchStubOp=()=>pending;
 ${section('const __stubOp =','const __dispatchStubOp =')}
 for(let i=0;i<1000;i++){
  let complete,cancel;pending=new Promise(r=>complete=r);
  const cancellation=new Promise((_,r)=>cancel=r),meta={entry:{refs:1},disposed:false};
  const call=__stubOp.length>=6?__stubOp(meta,[],null,undefined,undefined,cancellation):__stubOp(meta,[],null,undefined,cancellation);call.catch(()=>{});
  assert.equal(meta.entry.refs,2);
  cancel(Error('canceled'));await assert.rejects(call,/canceled/);
  assert.equal(meta.entry.refs,1,'cancellation releases target export; the continuation owns its result settlement');
  complete(new Uint8Array([4,1]));await new Promise(r=>setTimeout(r,0));
  assert.equal(meta.entry.refs,1);
  pending=Promise.resolve(new Uint8Array([4,2]));
  const live=await __stubOp(meta,[],null);assert.equal(live[1],2);
  await new Promise(r=>setTimeout(r,0));assert.equal(meta.entry.refs,1);
 }
 return {canceledPackets,revivedPackets};
})()
`,{assert});
console.log(JSON.stringify({id:'R7-03-settlement',...result}));
assert.deepEqual(JSON.parse(JSON.stringify(result)),{canceledPackets:1000,revivedPackets:1000});
