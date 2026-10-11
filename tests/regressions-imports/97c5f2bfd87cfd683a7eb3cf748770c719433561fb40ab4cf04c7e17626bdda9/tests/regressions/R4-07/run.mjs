import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const observations=await evaluate(`
let current='holder', seen=[], ended=false;
const __ctxUnregister=()=>{}, __capability_revoke=()=>{};
const __stubEntries=new Map();
const __ctxRun=(id,fn)=>{if(ended)throw new Error('dead context'); const prev=current; current=id; try{return fn();}finally{current=prev;}};
${section('const __disposeStub =','const __stubDisposedError =')}
(async()=>{
 const entry={id:1,ctx:'source',refs:1,target:{[Symbol.dispose](){seen.push(current);}}};
 const meta={entry,disposed:false};
 await __disposeStub(meta); await __disposeStub(meta);
 ended=true; let dead=false;
 try{await __disposeStub({entry:{...entry,refs:1},disposed:false});}catch(e){dead=e.message==='dead context';}
 return {seen,current,dead};
})()`);
assert.deepEqual(JSON.parse(JSON.stringify(observations)),{seen:['source'],current:'holder',dead:true});
console.log(JSON.stringify({id:'R4-07',pass:true,assertions:3,observations}));
