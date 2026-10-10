import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const actual=await evaluate(`
let routes=[],remaining=['good','unread'],released=[],adopted=false;
const __capability_packet=(bytes,json)=>{routes=JSON.parse(json);return bytes;};
const __capability_packet_inspect=()=>JSON.stringify([1,'authenticated-session']);
const __capability_packet_take=(_packet,r)=>{const i=remaining.indexOf(r);if(i<0)throw Error('unknown');remaining.splice(i,1);};
const __capability_packet_cancel=()=>{released.push(...remaining);remaining=[];};
const __capability_packet_adopt=()=>{if(remaining.length)throw Error('unclaimed');adopted=true;};
const __stubIsolate='local',__stubEntries=new Map(),__stubMeta=new WeakMap();
const __foreignStub=(v,session)=>{if(session!=='authenticated-session')throw Error('lost session');const stub={};__stubMeta.set(stub,{r:v.r});return stub;};
const __disposeStub=meta=>released.push(meta.r);
${section('const __reviveRequest =','const __reviveResponse =')}
${section('const __stubRevive =','// A foreign heap capability')}
${section('const __rpcPacket =','const __rpcOut =')}
const rs={'__celld$rs':1,r:'read'},ws={'__celld$ws':2,r:'write'};
__rpcPacket(new Uint8Array([1]),[rs,rs,new Map([[ws,{'__celld$stub':3,r:'stub'}]])]);
let failed=false;
try{__rpcRead(new Uint8Array([4,1]),(_bytes,session,take)=>__stubRevive([
 {'__celld$stub':1,t:'remote',r:'good'}, {'__celld$req':'invalid-url',m:'GET',h:[],b:null}
],session,take));}catch{failed=true;}
({routes,failed,adopted,released:released.sort(),remaining});
`,{Request});
console.log(JSON.stringify({id:'R6-03',actual}));
assert.deepEqual(JSON.parse(JSON.stringify(actual)),{routes:['read','write','stub'],failed:true,adopted:false,released:['good','unread'],remaining:[]});
