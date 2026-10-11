import assert from 'node:assert/strict';
import {section,evaluate,source} from '../harness_unit.mjs';
// One admission mechanism for every dispatcher: the invoking trap snapshots
// parameters synchronously; queued dispatchers (pipelines, loaders, facets)
// run the owned operation later and release it exactly once.
const unified=source.includes('// ---- RPC call admission');
const result=await evaluate(`(async()=>{
let cancel,owned=0,lateDisposed=0;
const __ctxNow=()=>1,__opTrack=(_ctx,fail)=>{cancel=fail;return()=>{};};
const __rpcOut=args=>{const value=structuredClone(args);owned++;return Object.assign(new Uint8Array([4]),{value});};
const __capability_packet_cancel=bytes=>{if(!bytes.canceled){bytes.canceled=true;owned--;}};
${unified?section('// ---- RPC call admission','const __stubOp ='):section('const __admitRpcArgs =','const __stubOp =')}
const admitted=(args,operation)=>${unified?'__admittedCall(__rpcAdmit(args),operation)':'__admitRpcArgs(args,operation)'};
const arg={v:1};let deliver;
const call=admitted([arg],async(bytes,check)=>{await new Promise(r=>deliver=r);check();return bytes.value;});arg.v=2;deliver();assert.equal((await call)[0].v,1);assert.equal(owned,0);
await assert.rejects(admitted([arg],()=>Promise.reject(Error('parent failed'))),/parent failed/);assert.equal(owned,0);
let resolve;
const canceled=admitted([arg],()=>new Promise(r=>resolve=r));canceled.catch(()=>{});cancel(Error('context aborted'));await assert.rejects(canceled,/context aborted/);assert.equal(owned,0);
resolve({[Symbol.dispose](){lateDisposed++;}});await new Promise(r=>setTimeout(r,0));assert.equal(lateDisposed,1);
let cases=3;
if(${unified}){
  // The trap admits before the session runs; an envelope is part of it.
  const seen=[];let go;
  const session={admit:(path,args)=>__rpcAdmit([path,args]),call:(path,a)=>new Promise(r=>go=()=>r(a.bytes.value))};
  const x={v:1};const p=__invokeAdmitted(session,['m'],[x]);x.v=9;go();
  assert.equal(JSON.stringify(await p),JSON.stringify([['m'],[{v:1}]]));await new Promise(r=>setTimeout(r,0));assert.equal(owned,0);
  // A dispatcher that throws synchronously still releases the snapshot.
  await assert.rejects(__invokeAdmitted({call:()=>{throw Error('sync');}},['m'],[x]),/sync/);assert.equal(owned,0);
  // An unserializable parameter rejects the call instead of throwing.
  await assert.rejects(__invokeAdmitted({call:()=>assert.fail('dispatched')},['m'],[Symbol('x')]));assert.equal(owned,0);
  // A disposed client rejects before its parameters are captured or moved.
  let admitted=0;
  await assert.rejects(__invokeAdmitted({acquire:()=>{throw Error('RPC stub used after being disposed.');},admit:()=>{admitted++;},call:()=>assert.fail('dispatched')},['m'],[x]),/disposed/);
  assert.equal(admitted,0);assert.equal(owned,0);
  cases+=4;
}
return {owned,lateDisposed,cases};
})()`,{assert,structuredClone});
console.log(JSON.stringify({id:'R9-06-admission',unified,...result}));
