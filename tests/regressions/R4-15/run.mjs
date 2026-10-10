import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const actual=await evaluate(`
const __cf={RpcPromise:class{},RpcProperty:class{}};
const __ctxNow=()=>1, __io_context_id=()=>1;
const __ctxError=()=>new Error('context');
${section('const __disposeWhenSettled =','const __makeStub =').split('// Use the native resource identity:')[0]}
(async()=>{
 let gets=0,roots=0;
 const property=__makeNode({get:()=>Promise.resolve(++gets)},['counter'],null);
 const values=[await property,await property,await property.catch(()=>0),await property.finally(()=>{})];
 const root=__makeNode({root:()=>{roots++;return Promise.resolve(5);}},[],1);
 return {values,gets,root:[await root,await root],roots};
})()`);
assert.deepEqual(JSON.parse(JSON.stringify(actual)),{values:[1,2,3,4],gets:4,root:[5,5],roots:1});
console.log(JSON.stringify({id:'R4-15',pass:true,assertions:4,actual}));
