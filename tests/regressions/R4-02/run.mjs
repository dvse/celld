import assert from 'node:assert/strict';
import {section,evaluate,source} from '../harness_unit.mjs';
const observations=await evaluate(`
const __stubMeta=new WeakMap(), __capabilityNotExecuted=new WeakSet();
let restores=0, calls=0;
const broken=new Error('injected authenticated pre-dispatch rejection');
__capabilityNotExecuted.add(broken);
const __restoreFromRoot=()=>{restores++; const s={dup(){return this;},[Symbol.dispose](){}}; __stubMeta.set(s,{}); return Promise.resolve(s);};
const __stubDisposedError=()=>new Error('disposed');
const __rpcOut=v=>v;
const __rpcAdmit=v=>({bytes:__rpcOut(v),release(){}});
const __checkStubOwner=()=>{};
const __restoreControlNames=()=>({invoke:'invoke'});
const __stubOp=async()=>{calls++; throw broken;};
${section(source.includes('const __persistentAcquire =')?'const __persistentAcquire =':'const __persistentCall =','const __makePersistentStub =')}
(async()=>{
 const live=await __restoreFromRoot({}); const meta={descriptor:{},live,disposed:false};
 for(let i=0;i<2;i++) {try{await __persistentCall(meta,['ping'],typeof __persistentAdmit==='function'?__persistentAdmit(meta,['ping'],[]):[]);}catch(e){if(e!==broken)throw e;}}
 return {restores,calls,same:meta.live===live};
})()`);
assert.deepEqual(JSON.parse(JSON.stringify(observations)),{restores:1,calls:2,same:true});
console.log(JSON.stringify({id:'R4-02',pass:true,assertions:3,observations}));
