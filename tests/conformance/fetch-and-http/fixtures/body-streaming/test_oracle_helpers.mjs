// Local no-network helper regressions. Not celld case executions.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const base=new URL('./',import.meta.url);
const common=await readFile(new URL('common.js',base),'utf8');
const commonUrl='data:text/javascript;base64,'+Buffer.from(common).toString('base64');
const labSource=(await readFile(new URL('lab.js',base),'utf8')).replace("'./common.js'",JSON.stringify(commonUrl));
const {Lab}=await import('data:text/javascript;base64,'+Buffer.from(labSource).toString('base64'));
const {bytes}=await import(commonUrl);
const lab=()=>new Lab({recipient:'peer',run:'run'},{root:'origin'},'http://127.0.0.1:18080');
let count=0;
for(const reason of ['premature EOF','byte mismatch','correlation mismatch','deadline']) {
 const t=lab();await assert.rejects(t.failure(t.watch(Promise.reject(new Error(reason)))),/helper\/assertion failure/);count++;
}
{
 const t=lab(),r={read:async()=>{throw new TypeError('source failed');}};
 await t.failure(t.watch(t.nativeRead(r)));assert.equal(t.events.at(-1).nativeOperation,'reader.read');count++;
}
for(const mode of ['premature-eof','corrupt-bytes']) {
 const t=lab();t.expected.set('broken',{label:'broken',n:4});
 const held={response:{},reader:{read:async()=>({done:true}),cancel:async()=>{},releaseLock(){}},parts:mode==='premature-eof'?[bytes('broken',2)]:[new Uint8Array(4)],total:mode==='premature-eof'?2:4};
 await assert.rejects(t.failure(t.watch(t.remainder(held,'broken'))),/helper\/assertion failure/);count++;
}
{
 const t=lab();let released=false;
 t.readers.add({cancel:async()=>{throw new Error('cancel failed');},releaseLock(){released=true;}});
 t.control=async()=>({status:'ok',run:'run',root:'peer',isolate:'peer-isolate',active:0,readers:0,controllers:0});
 t.owner={root:'peer',isolate:'peer-isolate'};
 await assert.rejects(t.cleanup(),/caller cancellation/);assert.equal(released,true);assert.equal(t.readers.size,0);count++;
}
console.log(JSON.stringify({support_checks_passed:count,network:false,celld_case_executions:0}));
