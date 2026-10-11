import { CASES } from './cases.js';
const WAVE='public-identity-admission-v1';
const identity=state=>({objectId:state.id.toString(),name:state.id.name??null});
const canonical=value=>JSON.stringify(value,(_,v)=>v===undefined?{'$undefined':true}:v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
class ScheduleBlocked extends Error {constructor(message){super(message);this.name='ScheduleBlocked';}}
async function bounded(promise,ms,label){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new ScheduleBlocked(label)),ms);})]);}finally{clearTimeout(timer);}}
async function call(stub,path,body={}) {
  const response=await stub.fetch(new Request('https://owned.fixture.invalid/'+path,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}));
  const value=await response.json(); if(!response.ok)throw new Error('fixture response '+response.status+': '+JSON.stringify(value)); return value;
}
async function clearOwned(state) {await state.storage.deleteAll();return {...identity(state),status:'COMPLETE',empty:(await state.storage.list({limit:1})).size===0};}
export class Record {
  constructor(state){this.state=state;this.calls=0;}
  async fetch(request){
    if(++this.calls>24)throw new Error('record call cap');
    const path=new URL(request.url).pathname;
    if(path==='/cleanup')return Response.json(await clearOwned(this.state));
    if(path==='/write'){const body=await request.json();if(typeof body.value!=='string'||body.value.length>32)throw new Error('fixture data cap');await this.state.storage.put('value',body.value);}
    return Response.json({...identity(this.state),value:await this.state.storage.get('value')??null});
  }
}
// A real independent DO controls one finite wait and records actual incoming
// target handlers. It does not implement target addressing, storage or gating.
export class Control {
  constructor(state){this.state=state;this.phase='fresh';this.entries=[];this.resolve=null;this.timer=null;this.waiters=0;this.fallbackUsed=false;this.targetId=null;this.calls=0;}
  snapshot(){return {...identity(this.state),phase:this.phase,entries:this.entries.slice(),waiters:this.waiters,fallbackUsed:this.fallbackUsed,targetId:this.targetId};}
  release(explicit){
    if(this.resolve){const resolve=this.resolve;this.resolve=null;clearTimeout(this.timer);this.timer=null;this.phase=explicit?'released':'fallback';this.fallbackUsed=!explicit;resolve({explicitRelease:explicit});}
  }
  async fetch(request){
    if(++this.calls>90)throw new Error('control call cap');
    const path=new URL(request.url).pathname,body=await request.json();
    if(path==='/hold'){
      if(this.phase!=='fresh')throw new Error('one control hold only');
      this.phase='held';this.targetId=body.targetId;this.waiters++;
      // This fuse RESOLVES normally. Its use marks the schedule BLOCKED; it
      // never throws inside blockConcurrencyWhile or tests its timeout path.
      const result=await new Promise(resolve=>{this.resolve=resolve;this.timer=setTimeout(()=>this.release(false),2500);});
      this.waiters--;return Response.json({...identity(this.state),...result});
    }
    if(path==='/release')this.release(true);
    if(path==='/entered'){
      if(this.entries.length>=2)throw new Error('admission log cap');
      this.entries.push({request:body.request,ready:body.ready,targetId:body.targetId,afterRelease:this.phase==='released'});
    }
    if(path==='/cleanup'){
      if(this.resolve||this.waiters||this.timer)throw new Error('control is still in use');
      const cleared=await clearOwned(this.state);this.entries=[];return Response.json({...cleared,waiters:0,timers:0});
    }
    return Response.json(this.snapshot());
  }
}
export class InitTarget {
  constructor(state,env){
    this.state=state;this.env=env;this.ready=false;this.explicitRelease=false;this.calls=0;
    this.control=env.CONTROL.getByName(state.id.name);
    state.blockConcurrencyWhile(async()=>{
      const held=await call(this.control,'hold',{targetId:state.id.toString()});
      this.explicitRelease=held.explicitRelease;
      await state.storage.put('value','initialized');this.ready=true;
    });
  }
  async fetch(request){
    if(++this.calls>8)throw new Error('initialization target call cap');
    if(new URL(request.url).pathname==='/cleanup')return Response.json(await clearOwned(this.state));
    const body=await request.json();
    const entryReady=this.ready;
    await call(this.control,'entered',{request:body.request,ready:entryReady,targetId:this.state.id.toString()});
    return Response.json({...identity(this.state),value:await this.state.storage.get('value')??null,ready:entryReady,explicitRelease:this.explicitRelease});
  }
}
export class EventTarget {
  constructor(state,env){this.state=state;this.control=env.CONTROL.getByName(state.id.name);this.ready=false;this.explicitRelease=false;this.calls=0;}
  async fetch(request){
    if(++this.calls>8)throw new Error('event target call cap');
    const path=new URL(request.url).pathname;
    if(path==='/cleanup')return Response.json(await clearOwned(this.state));
    if(path==='/seed'){await this.state.storage.put('value','seed');return Response.json({...identity(this.state),value:'seed'});}
    if(path==='/block'){
      await this.state.blockConcurrencyWhile(async()=>{
        await this.state.storage.put('value','intermediate');
        const held=await call(this.control,'hold',{targetId:this.state.id.toString()});this.explicitRelease=held.explicitRelease;
        await this.state.storage.put('value','committed');this.ready=true;
      });
    } else {
      const body=await request.json(),entryReady=this.ready;
      await call(this.control,'entered',{request:body.request,ready:entryReady,targetId:this.state.id.toString()});
    }
    return Response.json({...identity(this.state),value:await this.state.storage.get('value')??null,ready:this.ready,explicitRelease:this.explicitRelease});
  }
}
class CaseContext {
  constructor(env,id){this.env=env;this.id=id;this.run=WAVE+':'+id+':'+crypto.randomUUID();this.owned=[];this.pending=new Set();this.assertions=[];this.receipts=[];this.calls=0;this.polls=0;this.controlStub=null;}
  eq(actual,expected,label){const satisfied=canonical(actual)===canonical(expected);this.assertions.push({label,satisfied});if(!satisfied)throw new Error(label+': '+canonical({actual,expected}));}
  own(binding,stub){if(!this.owned.some(x=>x.binding===binding&&x.id===stub.id.toString())){if(this.owned.length>=3)throw new Error('owned root cap');this.owned.push({binding,id:stub.id.toString(),stub});}return stub;}
  control(){if(!this.controlStub)this.controlStub=this.own('CONTROL',this.env.CONTROL.getByName(this.run));return this.controlStub;}
  send(stub,path,body={}){
    if(++this.calls>100)throw new Error('supervisor direct fetch cap');
    const promise=call(stub,path,body).then(value=>{
      this.eq(value.objectId,stub.id.toString(),'actual recipient matches valid public handle');
      if(path!=='snapshot')this.receipts.push({path,objectId:value.objectId,value:value.value??null});return value;
    });
    this.pending.add(promise);promise.then(()=>this.pending.delete(promise),()=>this.pending.delete(promise));return promise;
  }
  start(stub,path,body={}){const item={settled:false,promise:this.send(stub,path,body)};item.promise.then(()=>{item.settled=true;},()=>{item.settled=true;});return item;}
  requireSchedule(state){if(state.fallbackUsed)throw new ScheduleBlocked('finite control fuse fired; requested overlap is not established');}
  requireResults(rows){if(rows.some(x=>!x.explicitRelease))throw new ScheduleBlocked('control did not complete by explicit successful release');}
  async held(control){
    for(let i=0;i<60;i++){
      this.polls++;const state=await this.send(control,'snapshot');
      if(state.phase==='held'&&state.waiters===1)return state;
      if(state.phase!=='fresh')throw new ScheduleBlocked('required hold was missed');
      await new Promise(resolve=>setTimeout(resolve,15));
    }
    throw new ScheduleBlocked('constructor/request did not reach explicit hold');
  }
  async cleanup(){
    if(this.controlStub)await this.send(this.controlStub,'release');
    await bounded(Promise.allSettled([...this.pending]),3000,'pending request cleanup deadline');
    if(this.pending.size)throw new ScheduleBlocked('live requests prevent owned storage cleanup');
    const rows=[];
    // Control is last so all admitted targets finish using it before clearing.
    for(const item of [...this.owned.filter(x=>x.binding!=='CONTROL'),...this.owned.filter(x=>x.binding==='CONTROL')]){
      const row=await this.send(item.stub,'cleanup');this.eq([row.status,row.empty],['COMPLETE',true],'owned object storage cleanup is verified empty');rows.push({binding:item.binding,id:item.id,...row});
    }
    return {status:'COMPLETE',objects:rows,pendingRequests:this.pending.size,externalReap:'required'};
  }
}
export default {
  async fetch(request,env){
    const url=new URL(request.url),match=/^\/case\/(A20[1-5])$/.exec(url.pathname);
    if(request.method!=='GET'||url.search||!match||!Object.hasOwn(CASES,match[1]))return new Response('GET /case/<manifest id>',{status:404});
    const c=new CaseContext(env,match[1]);let failure=null,settled=false,cleanup={status:'EXTERNAL_REAP_REQUIRED'};
    const trace=(async()=>{try{await CASES[c.id](c);}finally{settled=true;}})();
    try{await bounded(trace,6000,'case trace deadline');}catch(error){failure={name:error.name,message:String(error)};}
    // An unsettled trace may still dispatch: never race it with storage cleanup.
    if(settled){try{cleanup=await bounded(c.cleanup(),3500,'owned cleanup deadline');}catch(error){cleanup={status:'EXTERNAL_REAP_REQUIRED',error:String(error)};}}
    const ok=!failure&&settled&&cleanup.status==='COMPLETE'&&c.assertions.length>0&&c.assertions.every(x=>x.satisfied);
    const blocked=!settled||failure?.name==='ScheduleBlocked'||cleanup.status!=='COMPLETE';
    return Response.json({wave:WAVE,id:c.id,rootName:c.run,status:ok?'ASSERTIONS_SATISFIED':blocked?'BLOCKED':'FAIL',traceSettled:settled,failure,cleanup,assertions:c.assertions,receipts:c.receipts,directFetches:c.calls,polls:c.polls,qualification:'Component evidence only; independent executable/source/process/store teardown evidence required.'},{status:ok?200:500});
  }
};
