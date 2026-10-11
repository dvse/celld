import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const actual=await evaluate(`
const __cf={RpcPromise:class{},RpcProperty:class{}};
const __ctxNow=()=>1, __io_context_id=()=>1;
const __ctxError=()=>new Error('context');
const __valueSession=p=>({root:()=>p});
${section('const __disposeWhenSettled =','const __makeStub =').split('// Use the native resource identity:')[0]}
(async()=>{
 let calls=0; const root=__makeNode({root:()=>Promise.resolve(42),call:()=>{calls++;return Promise.resolve(99);}},[],1);
 const saved=root.method; root[Symbol.dispose](); root[Symbol.dispose]();
 let rejected=false; try{await saved();}catch(e){rejected=e.message.includes('disposed');}
 return {rejected,calls,awaited:await root};
})()`);
assert.deepEqual(JSON.parse(JSON.stringify(actual)),{rejected:true,calls:0,awaited:42});
console.log(JSON.stringify({id:'R4-09',pass:true,assertions:3,actual}));
