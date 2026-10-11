import assert from 'node:assert/strict';
import {section,evaluate} from '../harness_unit.mjs';
const actual=await evaluate(`
let calls=[], fail=false;
const __facet_clone=async(_scope,a,b)=>{calls.push('clone:'+a+'->'+b);if(fail)throw new Error('copy failed');};
const __facet_delete=async(_scope,a)=>{calls.push('delete:'+a);};
const __facet_snapshot=(_scope,a,b)=>({a,b});
const __facet_apply=(scope,snapshot)=>snapshot.a===null
 ? __facet_delete(scope,snapshot.b) : __facet_clone(scope,snapshot.a,snapshot.b);
let __nextFacetOwner=1;
${section('class DurableObjectFacets {','// The reason a failed critical section')}
(async()=>{
 const state={_scope:'root'}, manager=new DurableObjectFacets(state);
 manager.clone('a','b');manager.delete('b');
 await manager._barriers.get('b');
 const order=[...calls];fail=true;manager.clone('a','c');
 try{await manager._barriers.get('c');}catch{}
 await Promise.resolve();
 let failedSync=false;
 try{await Promise.all([...state._facetClones]);}catch(e){failedSync=e.message==='copy failed';}
 return {order,failedSync};
})()`,{TextEncoder});
console.log(JSON.stringify({id:'R4-03',actual}));
assert.deepEqual(JSON.parse(JSON.stringify(actual)),{order:['clone:a->b','delete:b'],failedSync:true});
