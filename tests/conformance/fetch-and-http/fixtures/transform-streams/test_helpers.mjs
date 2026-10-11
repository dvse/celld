// Tiny helper checks only. Does not import fixture.js, operations.js, or any SUT.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const common=await import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(new URL('./common.js',import.meta.url))).toString('base64'));
const {AssertionFailure,ScheduleBlocked,rejection,typeError,collect}=common;
await assert.rejects(rejection(Promise.resolve('EOF'),typeError,'negative oracle'),AssertionFailure);
await assert.rejects(rejection(Promise.reject(new AssertionFailure('wrong bytes')),()=>true,'negative oracle'),AssertionFailure);
await assert.rejects(rejection(Promise.reject(new ScheduleBlocked('no overlap')),()=>true,'negative oracle'),AssertionFailure);
await assert.rejects(rejection(Promise.reject(new Error('wrong family')),typeError,'negative oracle'),AssertionFailure);
assert.equal((await rejection(Promise.reject(new TypeError('native fixture')),typeError,'positive helper')).name,'TypeError');
const marker=new Error('planned-helper');assert.equal((await rejection(Promise.reject(marker),e=>e===marker,'identity helper')).name,'Error');
let n=0,charged=0;const joined=await collect({async read(){return n++?{done:true}:{done:false,value:Uint8Array.of(1,2,3)};}},count=>charged+=count);
assert.deepEqual([...joined],[1,2,3]);assert.equal(charged,3);
await assert.rejects(collect({async read(){return {done:false,value:new Uint8Array(262145)};}},()=>{}),AssertionFailure);
console.log('8 no-network helper checks; zero SUT case executions');
