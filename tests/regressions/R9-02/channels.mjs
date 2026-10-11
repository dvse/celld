import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const result=await evaluate(`
const trees=new Map();let next=0;
const __sc_decode=bytes=>trees.get(bytes[0]);
const encoded=tree=>{const id=++next;trees.set(id,tree);return new Uint8Array([1,id]);};
${section('const __validateStoredProps =','const __captureLoaderProps =')}
const service=(a,q)=>({'__celld$svc':'Inner',a,q});
const cls=(a,q)=>({'__celld$class':JSON.stringify({allow_storage:a}),q});
const denied=encoded(service(false));
const cases=[denied,encoded(service(true,denied)),encoded(cls(true,denied)),encoded(cls(false)),encoded({descriptor:{steps:[new Map([['arg',service(true,denied)]])]}}),encoded({'__celld$svcb':'configured'})];
let rejected=0;for(const bytes of cases)try{__validateStoredProps(bytes);}catch(e){if(e.name==='DataCloneError')rejected++;}
const allowed=encoded(service(true,encoded(cls(true,encoded(service(true))))));__validateStoredProps(allowed);
const cycle={};cycle.self=cycle;__validateStoredProps(encoded(cycle));
({rejected,allowed:true,cycle:true});
`,{DOMException});
console.log(JSON.stringify({id:'R9-02-channels',...result}));
assert.deepEqual(JSON.parse(JSON.stringify(result)),{rejected:6,allowed:true,cycle:true});
