import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const actual=await evaluate(`
const __durableClassMeta=new WeakMap(),__persistentMeta=new WeakMap(),__stubMeta=new WeakMap(),__svcMeta=new WeakMap(),__serviceBindings=new WeakSet(),__outboundMeta=new WeakMap(),__doStubMeta=new WeakMap();
const __cf={RpcTarget:class{},RpcPromise:class{},RpcProperty:class{}};
const __requirePersistence=()=>{},__rejectRpcMarkerData=()=>{},__rejectRpcMarkerKey=()=>{};
${section('const __storedLift =','// Encode one stub-bearing value')}
const service={},binding={};__svcMeta.set(service,{name:'Unstored',script:'static',persistent:false});
__serviceBindings.add(binding);__outboundMeta.set(binding,{script:'bound',entrypoint:'Receiver'});
const props=__storedLift({service,binding},true);
let refused=false;try{__storedLift(service);}catch(e){refused=e.name==='DataCloneError';}
({permission:props.service.a,channel:props.binding['__celld$svcb'],entrypoint:props.binding.e,refused});
`,{DOMException,ReadableStream,WritableStream});
console.log(JSON.stringify({id:'R6-02',actual}));
assert.deepEqual(JSON.parse(JSON.stringify(actual)),{permission:false,channel:'bound',entrypoint:'Receiver',refused:true});
