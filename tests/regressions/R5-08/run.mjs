import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const actual=await evaluate(`
let current='source',seen=[],ended=0,revokeThrows=false;
const __ctxNow=()=>current,__currentActorScope=()=>undefined;
const __cellBlocks=new Map(),__stubEntries=new Map(),__rpcCompletions=new Map();
let __nextStubId=1;
__rpcCompletions.set('source',{exports:new Set()});
const __ctxUnregister=()=>{};
const __capability_revoke=()=>{if(revokeThrows)throw new Error('revoke failed');};
const __rpcMaybeComplete=()=>{if(!__rpcCompletions.get('source').exports.size)ended++;};
const __ctxRun=(id,fn)=>{const prev=current;current=id;try{return fn();}finally{current=prev;}};
${section('const __newEntry =','// Actors broken in JS')}
${section('const __disposeStub =','const __stubDisposedError =')}
(async()=>{
 const target={get [Symbol.dispose](){seen.push('lookup:'+current);return function(){seen.push('body:'+current);};}};
 const entry=__newEntry(target);
 Object.defineProperty(target,Symbol.dispose,{value(){seen.push('replacement');}});
 current='holder';const handle={entry,disposed:false};
 await __disposeStub(handle);await __disposeStub(handle);
 current='source';let exportRejected=false;
 try{__newEntry({get [Symbol.dispose](){throw new Error('lookup failed');}});}catch(e){exportRejected=e.message==='lookup failed';}
 const retainedAfterThrow=__rpcCompletions.get('source').exports.size;
 const last=__newEntry({[Symbol.dispose](){seen.push('cleanup:'+current);}});last.route='route';
 current='holder';revokeThrows=true;let revokeRejected=false;
 try{await __disposeStub({entry:last,disposed:false});}catch(e){revokeRejected=e.message==='revoke failed';}
 return {seen,exportRejected,retainedAfterThrow,revokeRejected,retained:__rpcCompletions.get('source').exports.size,routable:__stubEntries.size,current};
})()`);
console.log(JSON.stringify({id:'R5-08',actual}));
assert.deepEqual(JSON.parse(JSON.stringify(actual)),{seen:['lookup:source','body:source','cleanup:source'],exportRejected:true,retainedAfterThrow:0,revokeRejected:true,retained:0,routable:0,current:'holder'});
