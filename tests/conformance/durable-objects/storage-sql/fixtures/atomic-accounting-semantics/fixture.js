import { CASES } from './cases.js';
export const WAVE = 'ordinary-atomic-accounting-v1';
const canonical = value => JSON.stringify(value, (_, v) => v instanceof ArrayBuffer ? [...new Uint8Array(v)] : ArrayBuffer.isView(v) ? [...new Uint8Array(v.buffer,v.byteOffset,v.byteLength)] : v && typeof v === 'object' && !Array.isArray(v) ? Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])) : v);
class ScheduleBlocked extends Error { constructor(message) { super(message); this.name='ScheduleBlocked'; } }
function deferred() { let resolve; const promise = new Promise(r => resolve=r); return {promise,resolve}; }
async function bounded(promise, ms, label, timers) {
  let timer;
  try { return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new ScheduleBlocked(label)),ms); timers?.add(timer);})]); }
  finally { clearTimeout(timer); timers?.delete(timer); }
}
const applicationTables = "SELECT name FROM sqlite_schema WHERE type='table' AND substr(name,1,4) != '_cf_' AND name NOT IN ('_litestream_seq','_litestream_lock') AND substr(name,1,7) != 'sqlite_' ORDER BY name";
export class AccountingCase {
  constructor(state) {
    this.state=state; this.activation=crypto.randomUUID(); this.phase='fresh'; this.active=0; this.transactions=0; this.pendingTransactions=new Set();
    this.events=[]; this.assertions=[]; this.cursors=[]; this.timers=new Set(); this.calls=0; this.admitted=new Set();
    this.admission=deferred(); this.held=deferred(); this.queued=deferred(); this.pauseCount=0;
  }
  identity() { return {objectId:this.state.id.toString(),activation:this.activation}; }
  event(label,role) { if(this.events.length>=40) throw new Error('event cap'); this.events.push({sequence:this.events.length,label,role}); }
  eq(actual,expected,label) { const satisfied=canonical(actual)===canonical(expected); this.assertions.push({label,satisfied}); if(!satisfied) throw new Error(label+': '+canonical({actual,expected})); }
  call() { if(++this.calls>400) throw new Error('public storage call cap'); }
  context(storage=this.state.storage,role='setup') {
    const host=this;
    const c={s:storage,root:this.state.storage,role,
      eq:(a,b,label)=>host.eq(a,b,label),
      q(sql,...bindings) { host.call(); const cursor=storage.sql.exec(sql,...bindings); host.cursors.push(cursor); if(host.cursors.length>240) throw new Error('cursor cap'); const rows=[]; for(let n=0;n<=64;n++){ const next=cursor.next(); if(next.done)return rows; if(n===64)throw new Error('row cap'); rows.push(next.value); } },
      async get(key) {host.call();return await storage.get(key);},
      async put(...args) {host.call();return await storage.put(...args);},
      async del(key) {host.call();return await storage.delete(key);},
      async list(options) {host.call();return await storage.list(options);},
      transaction(fn) {host.call();return storage.transaction(fn);},
      child(inner) {return host.context(inner,role);},
      async pause() {
        host.eq(role,'left','only the left ordinary request owns the checkpoint');
        host.eq(++host.pauseCount,1,'one checkpoint per finite schedule');
        host.event('left-hold',role); host.held.resolve();
        await bounded(host.queued.promise,1500,'right request did not queue while left transaction was open',host.timers);
        host.event('left-release',role);
      },
    }; return c;
  }
  async operate(role) {
    if(this.phase!=='ready'||this.admitted.has(role)) throw new ScheduleBlocked('two distinct ordinary requests required');
    this.active++; this.admitted.add(role); this.event('admitted',role);
    if(this.admitted.size===2) {this.event('admission-open','both');this.admission.resolve();}
    try {
      await bounded(this.admission.promise,1500,'both requests must enter before the transaction closes its input gate',this.timers);
      if(role==='right') await bounded(this.held.promise,1500,'left did not reach its case-specific checkpoint',this.timers);
      this.event('transaction-call',role); this.call();
      const pending=this.state.storage.transaction(async storage=>{
        this.transactions++; this.event('transaction-enter',role);
        try {
          if(role==='right') this.eq(this.events.some(e=>e.label==='left-release'),true,'right transaction cannot enter before left releases');
          const value=await CASES[this.id][role](this.context(storage,role));
          this.event('body-complete',role); return value;
        } finally { this.transactions--; }
      });
      this.pendingTransactions.add(pending);
      pending.then(()=>this.pendingTransactions.delete(pending),()=>this.pendingTransactions.delete(pending));
      if(role==='right') {this.event('right-queued',role);this.queued.resolve();}
      const value=await pending; this.event('transaction-settled',role);
      return {role,status:'SETTLED',value,...this.identity()};
    } finally { this.active--; }
  }
  async finish() {
    this.eq(this.active,0,'both request handlers settled before final audit');
    this.eq(this.transactions,0,'no transaction callback survives into audit');
    this.eq(this.pendingTransactions.size,0,'all transaction promises settled before audit');
    this.eq(this.timers.size,0,'all schedule timers cleared');
    this.eq([...this.admitted].sort(),['left','right'],'exact incoming cohort');
    const index=(label,role)=>this.events.findIndex(e=>e.label===label&&(role===undefined||e.role===role));
    this.eq(index('admission-open')<index('transaction-call','left'),true,'both ordinary contexts entered before transaction admission');
    const order=[index('transaction-enter','left'),index('left-hold'),index('transaction-call','right'),index('right-queued'),index('left-release'),index('body-complete','left'),index('transaction-enter','right')];
    this.eq(order.every((v,i)=>v>=0&&(i===0||v>order[i-1])),true,'literal cross-request transaction schedule witnessed');
    await CASES[this.id].verify(this.context(this.state.storage,'verify'));
  }
  async cleanup() {
    if(this.active!==0||this.transactions!==0||this.pendingTransactions.size!==0||this.timers.size!==0) return {status:'EXTERNAL_REAP_REQUIRED'};
    for(const cursor of this.cursors) { let done=false; for(let n=0;n<=64;n++) { if(cursor.next().done) {done=true;break;} } if(!done)throw new Error('cursor cleanup cap'); }
    this.call(); await this.state.storage.deleteAll();
    this.eq((await this.context().list({limit:1})).size,0,'owned KV empty after cleanup');
    this.eq(this.context().q(applicationTables),[],'owned SQL tables absent after cleanup');
    return {status:'COMPLETE',activeRequests:0,activeTransactions:0,timers:0,trackedCursors:this.cursors.length,ownedKvEmpty:true,ownedSqlEmpty:true,externalReap:'required'};
  }
  async fetch(request) {
    const parts=new URL(request.url).pathname.split('/').filter(Boolean);
    try {
      if(parts[0]==='setup') {
        if(this.phase!=='fresh'||!Object.hasOwn(CASES,parts[1]))throw new ScheduleBlocked('fresh valid object required');
        this.phase='setup';this.id=parts[1];
        const c=this.context();
        if(typeof c.s.kv?.get!=='function'||typeof c.s.transaction!=='function')throw new ScheduleBlocked('required direct storage API missing');
        this.eq((await c.list({limit:1})).size,0,'fresh owned KV required');this.eq(c.q(applicationTables),[],'fresh owned SQL required');
        await CASES[this.id].seed(c);this.phase='ready';return Response.json({status:'READY',id:this.id,...this.identity()});
      }
      if(parts[0]==='act'&&['left','right'].includes(parts[1]))return Response.json(await this.operate(parts[1]));
      if(parts[0]==='finish') {
        let failure=null;try {await this.finish();} catch(error) {failure={name:error.name,message:String(error)};}
        let cleanup;try {cleanup=await this.cleanup();}catch(error){cleanup={status:'FAILED',error:String(error)};}
        this.phase='finished';const satisfied=!failure&&cleanup.status==='COMPLETE'&&this.assertions.every(x=>x.satisfied);
        return Response.json({id:this.id,...this.identity(),status:satisfied?'ASSERTIONS_SATISFIED':'FAIL',failure,cleanup,events:this.events,assertions:this.assertions,publicCalls:this.calls},{status:satisfied?200:500});
      }
      return new Response('unknown fixture route',{status:404});
    } catch(error) {return Response.json({id:this.id,...this.identity(),status:error instanceof ScheduleBlocked?'BLOCKED_SCHEDULE':'FAIL',error:String(error),events:this.events},{status:500});}
  }
}
export default {
  async fetch(request,env) {
    const url=new URL(request.url),match=/^\/case\/(T2\d\d)$/.exec(url.pathname);
    if(request.method!=='GET'||!match||url.search||!Object.hasOwn(CASES,match[1]))return new Response('GET /case/<manifest id>',{status:404});
    const id=match[1],rootName=WAVE+':'+id+':'+crypto.randomUUID(),objectId=env.CASE.idFromName(rootName),stub=env.CASE.get(objectId);
    const send=async path=>{const response=await stub.fetch(new Request('https://owned.fixture.invalid/'+path));return await response.json();};
    const correlated=(value,activation)=>value.objectId===objectId.toString()&&(!activation||value.activation===activation);
    const result={wave:WAVE,id,rootName,expectedObjectId:objectId.toString(),runtimeQualification:'Independent direct celld build/process/placement/teardown evidence is mandatory; fixture labels alone never earn runtime credit.'};
    try {
      const setup=await bounded(send('setup/'+id),2000,'setup deadline'); result.setup=setup;
      if(setup.status!=='READY'||!correlated(setup))return Response.json({...result,status:'BLOCKED_PRECONDITION',cleanup:{status:'EXTERNAL_REAP_REQUIRED'}},{status:500});
      // Both real fetches are issued before awaiting either response. No RPC,
      // fake storage, private runtime controls or retained handler capability.
      const cohort=await bounded(Promise.allSettled([send('act/left'),send('act/right')]),6000,'ordinary request cohort did not settle');
      result.receipts=cohort;
      const good=cohort.every((x,i)=>x.status==='fulfilled'&&x.value.status==='SETTLED'&&x.value.role===['left','right'][i]&&correlated(x.value,setup.activation));
      const blocked=cohort.some(x=>x.status==='fulfilled'&&x.value.status==='BLOCKED_SCHEDULE');
      const finished=await bounded(send('finish'),3000,'audit/cleanup deadline');result.finished=finished;
      const satisfied=good&&correlated(finished,setup.activation)&&finished.status==='ASSERTIONS_SATISFIED';
      return Response.json({...result,status:satisfied?'ASSERTIONS_SATISFIED':blocked?'BLOCKED_SCHEDULE':'FAIL'},{status:satisfied?200:500});
    } catch(error) {return Response.json({...result,status:'BLOCKED_UNSETTLED',error:String(error),cleanup:{status:'EXTERNAL_REAP_REQUIRED',reason:'No data cleanup may race live foreground work.'}},{status:500});}
  }
};
