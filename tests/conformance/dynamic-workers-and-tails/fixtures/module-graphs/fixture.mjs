import {GRAPHS} from './graphs.mjs';
import {ok,eq} from './cases.mjs';
export const PROFILE='module-graph-candidate8d27-v1';
export class Blocked extends Error {constructor(message){super(message);this.blocked=true;}}
export async function bounded(p,ms,label){let timer;try{return await Promise.race([p,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Blocked('bounded wait expired: '+label)),ms);})]);}finally{clearTimeout(timer);}}
export function scope(root,requestId){
 const workers=[],pending=[],requests=[],tasks=[];let sequence=0,closed=false;
 const guard=()=>{if(closed)throw new Blocked('scope closing');};
 const observe=(collection,fn,details={})=>{
  const row={...details,settled:false};collection.push(row);
  try{row.promise=Promise.resolve(fn()).then(value=>{row.settled=true;return value;},error=>{row.settled=true;throw error;});}
  catch(error){row.settled=true;row.promise=Promise.reject(error);}
  row.promise.catch(()=>{});return row;
 };
 const track=(fn)=>{ok(requests.length<512,'total RPC bound');ok(requests.filter(x=>!x.settled).length<12,'all active RPC bound');return observe(requests,fn).promise;};
 const s={
  requestId,
  // The complete setup/trace lifetime includes local await continuations and
  // held() polling timers, not just the native RPC promises they create.
  task(label,fn){guard();ok(tasks.length<2,'outer task bound');return observe(tasks,fn,{label}).promise;},
  open(config){
   guard();ok(workers.length<4,'worker bound');const mods=Object.values(config.modules);ok(mods.length<=9,'module bound');ok(mods.every(x=>typeof x==='string'),'JS-only graph');ok(mods.reduce((n,x)=>n+new TextEncoder().encode(x).length,0)<=24576,'code-byte bound');
   const worker=root.env.LOADER.load(config);
   // Record native ownership before any later operation can throw.
   const owned={worker,entry:null,facade:null,startupState:'unobserved',startupPromise:null};workers.push(owned);
   const entry=worker.getEntrypoint();owned.entry=entry;
   const e={state(){guard();return track(()=>entry.state());},release(key){guard();return track(()=>entry.release(key));},invoke(...args){guard();return track(()=>entry.invoke(...args));}};owned.facade=e;
   // Every opened load is observed immediately, including deliberately failing
   // graphs that the case might never reach after a different setup failure.
   owned.startupState='pending';
   owned.startupPromise=track(()=>entry.state()).then(value=>{owned.startupState='fulfilled';return value;},error=>{owned.startupState='rejected';throw error;});
   owned.startupPromise.catch(()=>{});return e;
  },
  async ready(config){
   const e=s.open(config),owned=workers.find(x=>x.facade===e);const value=await owned.startupPromise;
   guard();eq(value.pending,[],'main initialized before lazy import');eq(value.active,[],'fresh receiver invocation table');return e;
  },
  start(e,op,...args){
   guard();ok(sequence<32,'call bound');ok(pending.filter(x=>!x.settled).length<8,'inflight bound');const id=requestId+':rpc:'+ ++sequence;
   return observe(pending,()=>e.invoke(op,id,args),{id,op});
  },
  call(e,op,...args){return s.start(e,op,...args).promise;},
  async held(e,keys,invocations){
   const want=[...keys].sort();let last;
   for(let n=0;n<80;n++){
    guard();last=await e.state();guard();
    if(JSON.stringify(last.pending)===JSON.stringify(want)&&invocations.every(id=>last.active.includes(id))){for(const id of invocations)eq(last.calls.filter(x=>x.id===id&&x.phase==='enter').length,1,'receiver invocation entered exactly once');return last;}
    if(pending.some(x=>invocations.includes(x.id)&&x.settled))throw new Blocked('required held overlap was not established before invocation settled');
    await new Promise(resolve=>setTimeout(resolve,10));
   }
   throw new Blocked('required held overlap absent after 80 finite polls: '+JSON.stringify(last));
  },
  async control(){const e=await s.ready(GRAPHS.control);eq(await s.call(e,'probe'),'graph-control','real Loader positive control');},
  async cleanup(){
   closed=true;const errors=[];let drained=false;
   // A successful late startup also receives gate cleanup. Rejected startup
   // is already observed and has no callable receiver. No stop probes occur
   // after disposal; unresolved startup keeps the whole owner BLOCKED.
   const stops=workers.map(async owned=>{
    if(!owned.startupPromise){errors.push({phase:'unobserved-startup',error:'native worker ownership has no startup observer'});return;}
    try{await owned.startupPromise;}catch{return;}
    try{await track(()=>owned.entry.stop());}catch(error){errors.push({phase:'release-owned-gates',error:String(error)});}
   });
   try{await bounded(Promise.all(stops),1000,'gate cleanup');}catch(error){errors.push({phase:'stop-timeout',error:String(error)});}
   // The stop promises include any stop RPC started after a late startup.
   // Closed-scope guards prevent setup/trace continuations from admitting
   // additional loads or RPCs, and the complete outer tasks must settle too.
   const complete=[...tasks.map(x=>x.promise),...workers.map(x=>x.startupPromise).filter(Boolean),...requests.map(x=>x.promise),...stops];
   try{
    await bounded(Promise.allSettled(complete),1200,'task/startup/RPC drain');
    drained=tasks.every(x=>x.settled)&&requests.every(x=>x.settled)&&pending.every(x=>x.settled)&&workers.every(x=>['fulfilled','rejected'].includes(x.startupState));
   }catch(error){errors.push({phase:'drain-timeout',error:String(error)});}
   if(drained&&errors.length===0){
    for(const {entry} of workers)try{entry?.[Symbol.dispose]?.();}catch(error){errors.push({phase:'entry-dispose',error:String(error)});}
    for(const {worker} of workers)try{worker.dispose();}catch(error){errors.push({phase:'worker-dispose',error:String(error)});}
   }
   return {status:drained&&errors.length===0?'ok':'BLOCKED',drained,pending:pending.filter(x=>!x.settled).map(x=>x.id),workers:workers.length,startupStates:workers.map(x=>x.startupState),unsettledStartupCount:workers.filter(x=>!['fulfilled','rejected'].includes(x.startupState)).length,outerTasks:tasks.map(x=>({label:x.label,settled:x.settled})),unsettledTaskCount:tasks.filter(x=>!x.settled).length,invocationCount:sequence,totalRpcCount:requests.length,unsettledRpcCount:requests.filter(x=>!x.settled).length,errors,externalTeardownRequired:true};
  }
 };return s;
}
