// Tiny ownership bookkeeping checks against inert stubs. No graph evaluation,
// worker engine, network, native runtime, or VM is started.
import assert from 'node:assert/strict';
import {scope} from './fixture.mjs';
import {GRAPHS} from './graphs.mjs';
const snapshot=()=>({pending:[],active:[],calls:[]});
const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return {promise,resolve,reject};};
function root(factory){return {env:{LOADER:{load:factory}}};}
let checks=0;
{
 const startup=deferred();let disposed=0,stopped=0;
 const entry={state:()=>startup.promise,stop(){stopped++;},[Symbol.dispose](){disposed++;}};
 const s=scope(root(()=>({getEntrypoint:()=>entry,dispose(){disposed++;}})),'startup-pending');
 s.open(GRAPHS.control);const cleanup=await s.cleanup();assert.equal(cleanup.status,'BLOCKED');assert.equal(cleanup.unsettledStartupCount,1);assert.equal(disposed,0);
 startup.resolve(snapshot());await new Promise(resolve=>setTimeout(resolve,0));assert.equal(stopped,1);assert.equal(disposed,0);checks++;
}
{
 let taskSettled=false,disposed=0;
 const entry={state:snapshot,stop(){},[Symbol.dispose](){assert.equal(taskSettled,true);disposed++;}};
 const s=scope(root(()=>({getEntrypoint:()=>entry,dispose(){assert.equal(taskSettled,true);disposed++;}})),'outer-poll');const e=await s.ready(GRAPHS.control);
 const task=s.task('trace',async()=>{try{return await s.held(e,['absent'],['none']);}finally{taskSettled=true;}});task.catch(()=>{});
 await Promise.resolve();await Promise.resolve();const cleanup=await s.cleanup();await assert.rejects(task,/scope closing/);assert.equal(cleanup.status,'ok');assert.equal(cleanup.unsettledTaskCount,0);assert.equal(disposed,2);checks++;
}
{
 const late=deferred();let loads=0;const s=scope(root(()=>{loads++;throw new Error('late load should not happen');}),'late-setup');
 const task=s.task('setup',async()=>{await late.promise;return s.ready(GRAPHS.control);});task.catch(()=>{});
 const cleanup=await s.cleanup();assert.equal(cleanup.status,'BLOCKED');assert.equal(cleanup.unsettledTaskCount,1);late.resolve();await assert.rejects(task,/scope closing/);assert.equal(loads,0);checks++;
}
{
 let disposed=0;const s=scope(root(()=>({getEntrypoint(){throw new Error('entry unavailable');},dispose(){disposed++;}})),'entry-unobserved');
 assert.throws(()=>s.open(GRAPHS.control),/entry unavailable/);const cleanup=await s.cleanup();assert.equal(cleanup.status,'BLOCKED');assert.equal(cleanup.unsettledStartupCount,1);assert.equal(disposed,0);checks++;
}
{
 let stopped=0,disposed=0;const entry={state(){return Promise.reject(new Error('planned startup rejection'));},stop(){stopped++;},[Symbol.dispose](){disposed++;}};
 const s=scope(root(()=>({getEntrypoint:()=>entry,dispose(){disposed++;}})),'startup-rejected');s.open(GRAPHS.control);const cleanup=await s.cleanup();assert.equal(cleanup.status,'ok');assert.deepEqual(cleanup.startupStates,['rejected']);assert.equal(stopped,0);assert.equal(disposed,2);checks++;
}
{
 const stops=[];let next=0,disposed=0;const s=scope(root(()=>{const id=next++;return {getEntrypoint:()=>({state:snapshot,stop(){stops.push(id);if(id===0)throw new Error('stop failed');},[Symbol.dispose](){disposed++;}}),dispose(){disposed++;}};}),'independent-stops');
 await s.ready(GRAPHS.control);await s.ready(GRAPHS.control);const cleanup=await s.cleanup();assert.equal(cleanup.status,'BLOCKED');assert.deepEqual(stops,[0,1]);assert.equal(disposed,0);checks++;
}
console.log(JSON.stringify({kind:'inert-stub-bookkeeping-only',checks,sutRuns:0,graphEvaluations:0}));
