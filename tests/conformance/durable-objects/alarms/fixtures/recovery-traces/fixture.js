// Real Durable Object storage and native scheduled events. No direct dispatch hook.
import { DurableObject } from 'cloudflare:workers';
const ISOLATE = crypto.randomUUID();
const check = (ok, message) => { if (!ok) throw new Error(message); };
const ident = value => { check(typeof value === 'string' && /^[a-zA-Z0-9:_-]{1,140}$/.test(value), 'invalid identifier'); return value; };
const modes = new Set(['normal','inspect-rearm','throw-once','rollback-throw','rearm-throw','delete-throw','hold-throw','rollback-rearm-throw','always-throw']);
export class AlarmRoot extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.gates = new Map(); this.active = new Map(); this.jobs = new Map(); }
  identity() { return { root: String(this.ctx.id), isolate: ISOLATE }; }
  receipt(request, phase) {
    ident(request);
    const meta = this.ctx.storage.sql.exec('SELECT run_id,case_id FROM meta WHERE id=1').one();
    return { ...this.identity(), run_id:meta.run_id, case_id:meta.case_id, request, phase, now:Date.now() };
  }
  answer(request, value, phase='returned') { return { receipt:this.receipt(request,phase), value }; }
  async prepare({ request, run_id, case_id }) {
    ident(run_id);ident(case_id);
    const sql=this.ctx.storage.sql;
    sql.exec('CREATE TABLE IF NOT EXISTS meta(id INTEGER PRIMARY KEY,run_id TEXT,case_id TEXT)');
    sql.exec('CREATE TABLE IF NOT EXISTS plan(id INTEGER PRIMARY KEY,body TEXT)');
    sql.exec('CREATE TABLE IF NOT EXISTS markers(name TEXT PRIMARY KEY,value INTEGER)');
    sql.exec('CREATE TABLE IF NOT EXISTS entries(seq INTEGER PRIMARY KEY AUTOINCREMENT,label TEXT,scheduled INTEGER,retry INTEGER,is_retry INTEGER,entered INTEGER,initial_alarm INTEGER,terminal TEXT,after_alarm INTEGER)');
    sql.exec('CREATE TABLE IF NOT EXISTS effects(label TEXT PRIMARY KEY,value INTEGER)');
    sql.exec('INSERT OR IGNORE INTO meta VALUES(1,?,?)',run_id,case_id);
    const meta=sql.exec('SELECT run_id,case_id FROM meta WHERE id=1').one();
    check(meta.run_id===run_id&&meta.case_id===case_id,'fresh namespace reused');
    await this.ctx.storage.sync();return this.answer(request,await this.state(),'prepared');
  }
  async state() {
    const sql=this.ctx.storage.sql;
    return { ...this.identity(), now:Date.now(), alarm:await this.ctx.storage.getAlarm(),
      plans:[...sql.exec('SELECT body FROM plan ORDER BY id')].map(row=>JSON.parse(row.body)),
      markers:[...sql.exec('SELECT name,value FROM markers ORDER BY name')],
      entries:[...sql.exec('SELECT seq,label,scheduled,retry,is_retry,entered,initial_alarm,terminal,after_alarm FROM entries ORDER BY seq')],
      effects:[...sql.exec('SELECT label,value FROM effects ORDER BY label')],
      active:[...this.active.values()], jobs:[...this.jobs.values()] };
  }
  async inspect({ request }) { return this.answer(request,await this.state(),'observed'); }
  gate(name) {
    ident(name);check(this.gates.size<12||this.gates.has(name),'gate bound');
    if(!this.gates.has(name)){let resolve;const promise=new Promise(r=>{resolve=r;});this.gates.set(name,{resolve,promise,open:false});}
    return this.gates.get(name);
  }
  async waitGate(name) {
    if(!name)return;
    let timer;try{await Promise.race([this.gate(name).promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('PRECONDITION_GATE_EXPIRED')),45000);})]);}
    finally{clearTimeout(timer);}
  }
  release({ request, gates }) {
    check(Array.isArray(gates)&&gates.length<=12,'release bound');
    for(const name of gates){const gate=this.gate(name);gate.open=true;gate.resolve();}
    return this.answer(request,{released:gates},'gate-released');
  }
  normalize(spec) {
    ident(spec.label);check(modes.has(spec.mode||'normal'),'unsupported handler mode');
    if(spec.gate)ident(spec.gate);
    check(!spec.nextDelay||Number.isInteger(spec.nextDelay)&&spec.nextDelay>=1500&&spec.nextDelay<=120000,'next alarm bound');
    if(spec.nextLabel)ident(spec.nextLabel);
    return {label:spec.label,mode:spec.mode||'normal',gate:spec.gate||'',nextDelay:spec.nextDelay||2000,nextLabel:spec.nextLabel||spec.label+'-next'};
  }
  due(spec) {
    if(spec.at!==undefined){check(Number.isSafeInteger(spec.at)&&spec.at>Date.now()-15000&&spec.at<Date.now()+120001,'absolute schedule bound');return spec.at;}
    check(Number.isInteger(spec.delayMs)&&spec.delayMs>=500&&spec.delayMs<=120000,'delay bound');return Date.now()+spec.delayMs;
  }
  async writePlan(storage, spec, at) {
    const body=this.normalize(spec);
    storage.sql.exec('INSERT OR REPLACE INTO plan VALUES(1,?)',JSON.stringify(body));
    await storage.setAlarm(at);return body;
  }
  async arm({ request, ...spec }) {
    const at=this.due(spec);const plan=await this.writePlan(this.ctx.storage,spec,at);
    await this.ctx.storage.sync();return this.answer(request,{at,plan,alarm:await this.ctx.storage.getAlarm()},'armed');
  }
  async cancel({ request }) {
    await this.ctx.storage.deleteAlarm();await this.ctx.storage.sync();
    return this.answer(request,{alarm:await this.ctx.storage.getAlarm()},'canceled');
  }
  async transaction({ request, steps, abort='none' }) {
    check(Array.isArray(steps)&&steps.length>=1&&steps.length<=6,'transaction step bound');
    check(['none','throw','explicit'].includes(abort),'abort mode');
    const apply=async(storage,step)=>{
      if(step.op==='set')await this.writePlan(storage,step,this.due(step));
      else if(step.op==='delete')await storage.deleteAlarm();
      else if(step.op==='marker'){ident(step.name);check(Number.isInteger(step.value)&&Math.abs(step.value)<=100,'marker bound');storage.sql.exec('INSERT OR REPLACE INTO markers VALUES(?,?)',step.name,step.value);}
      else if(step.op==='nested'){
        check(Array.isArray(step.steps)&&step.steps.length<=3&&!step.steps.some(s=>s.op==='nested'),'nested bound');
        try{await storage.transaction(async inner=>{for(const child of step.steps)await apply(inner,child);if(step.abort)throw new Error('PLANNED_CHILD_ROLLBACK');});}
        catch(error){check(step.abort&&String(error).includes('PLANNED_CHILD_ROLLBACK'),'unexpected child failure');}
      }else throw new Error('unsupported transaction step');
    };
    let rolledBack=false;
    try{await this.ctx.storage.transaction(async tx=>{
      for(const step of steps)await apply(tx,step);
      if(abort==='throw')throw new Error('PLANNED_OUTER_ROLLBACK');
      if(abort==='explicit'){tx.rollback();rolledBack=true;}
    });}catch(error){check(abort==='throw'&&String(error).includes('PLANNED_OUTER_ROLLBACK'),'unexpected outer failure');rolledBack=true;}
    await this.ctx.storage.sync();return this.answer(request,{rolledBack,state:await this.state()},'transaction-finished');
  }
  async foreground({ request, gate='', name, value=1 }) {
    ident(name);check(Number.isInteger(value)&&Math.abs(value)<=100,'foreground value bound');
    check(this.jobs.size<24,'job bound');this.jobs.set(request,{request,phase:'waiting'});
    console.log('AES_ENTER '+JSON.stringify(this.receipt(request,'foreground-waiting')));
    try{await this.waitGate(gate);this.ctx.storage.sql.exec('INSERT INTO markers VALUES(?,?)',name,value);await this.ctx.storage.sync();this.jobs.set(request,{request,phase:'done'});return this.answer(request,{name,value},'foreground-done');}
    catch(error){this.jobs.set(request,{request,phase:'failed',error:String(error).slice(0,160)});throw error;}
  }
  async alarm(info) {
    // A001 is the only ordinary RPC call to alarm. No helper invokes this handler.
    if(info&&info.probe===true){this.ctx.storage.sql.exec("INSERT OR REPLACE INTO markers VALUES('rpc-alarm-body',1)");return {rpcBodyRan:true};}
    check(info&&Number.isSafeInteger(info.scheduledTime)&&Number.isInteger(info.retryCount)&&info.retryCount>=0&&typeof info.isRetry==='boolean','native alarm metadata missing');
    const sql=this.ctx.storage.sql;check(sql.exec('SELECT count(*) AS n FROM entries').one().n<16,'alarm invocation bound');
    const raw=[...sql.exec('SELECT body FROM plan WHERE id=1')][0];check(raw,'native alarm has no plan');const plan=JSON.parse(raw.body);
    const initial=await this.ctx.storage.getAlarm();
    sql.exec('INSERT INTO entries(label,scheduled,retry,is_retry,entered,initial_alarm,terminal,after_alarm) VALUES(?,?,?,?,?,?,?,NULL)',plan.label,info.scheduledTime,info.retryCount,info.isRetry?1:0,Date.now(),initial,'entered');
    const seq=sql.exec('SELECT max(seq) AS n FROM entries').one().n;
    const entry={...this.receipt('event:'+seq,'alarm-entered'),seq,label:plan.label,scheduled:info.scheduledTime,retry:info.retryCount,isRetry:info.isRetry};
    this.active.set(seq,entry);console.log('AES_EVENT '+JSON.stringify(entry));await this.ctx.storage.sync();
    try{
      await this.waitGate(plan.gate);
      const first=info.retryCount===0;
      if(plan.mode==='inspect-rearm'||plan.mode==='rearm-throw'){
        const at=Date.now()+plan.nextDelay;
        await this.writePlan(this.ctx.storage,{label:plan.nextLabel,mode:'normal'},at);
      }
      if(plan.mode==='delete-throw')await this.ctx.storage.deleteAlarm();
      if(plan.mode==='rollback-throw'&&first){
        try{this.ctx.storage.transactionSync(()=>{sql.exec('INSERT INTO effects VALUES(?,999)',plan.label);throw new Error('PLANNED_EFFECT_ROLLBACK');});}
        catch(error){check(String(error).includes('PLANNED_EFFECT_ROLLBACK'),'wrong effect rollback');}
      }
      if(plan.mode==='rollback-rearm-throw'&&first){
        try{await this.ctx.storage.transaction(async tx=>{await tx.setAlarm(Date.now()+60000);throw new Error('PLANNED_REARM_ROLLBACK');});}
        catch(error){check(String(error).includes('PLANNED_REARM_ROLLBACK'),'wrong rearm rollback');}
      }
      const fail=plan.mode==='always-throw'||plan.mode==='rearm-throw'||plan.mode==='delete-throw'||first&&['throw-once','rollback-throw','hold-throw','rollback-rearm-throw','always-throw'].includes(plan.mode);
      const after=await this.ctx.storage.getAlarm();
      if(fail){sql.exec("UPDATE entries SET terminal='failed',after_alarm=? WHERE seq=?",after,seq);await this.ctx.storage.sync();throw new Error('PLANNED_HANDLER_FAILURE');}
      this.ctx.storage.transactionSync(()=>{sql.exec('INSERT OR IGNORE INTO effects VALUES(?,1)',plan.label);sql.exec("UPDATE entries SET terminal='success',after_alarm=? WHERE seq=?",after,seq);});
      await this.ctx.storage.sync();
    }catch(error){
      if(String(error).includes('PRECONDITION_GATE_EXPIRED'))sql.exec("UPDATE entries SET terminal='gate-expired' WHERE seq=?",seq);
      throw error;
    }finally{this.active.delete(seq);console.log('AES_SETTLED '+JSON.stringify({...entry,phase:'alarm-settled'}));}
  }
  async cleanup({ request }) {
    for(const gate of this.gates.values())gate.resolve();await this.ctx.storage.deleteAlarm();await this.ctx.storage.sync();
    return this.answer(request,{active:this.active.size,alarm:await this.ctx.storage.getAlarm()},'cleanup');
  }
}
export default {
  async fetch(request,env){
    const path=new URL(request.url).pathname;
    if(path==='/health')return Response.json({profile:'alarm-event-stress-v1'});
    check(path==='/op'&&request.method==='POST','unsupported route');
    const body=await request.json();ident(body.root);const root=env.ROOT.getByName(body.root);
    const args=body.args||{};
    switch(body.method){
      case 'prepare':return Response.json(await root.prepare(args));
      case 'identity':return Response.json(await root.identity());
      case 'inspect':return Response.json(await root.inspect(args));
      case 'arm':return Response.json(await root.arm(args));
      case 'cancel':return Response.json(await root.cancel(args));
      case 'transaction':return Response.json(await root.transaction(args));
      case 'foreground':return Response.json(await root.foreground(args));
      case 'release':return Response.json(await root.release(args));
      case 'cleanup':return Response.json(await root.cleanup(args));
      case 'probeAlarm':{
        // Public stub method syntax. No raw capability transport, auth, or internal hook.
        try{return Response.json({request:args.request,rejected:false,value:await root.alarm({probe:true})});}
        catch(error){return Response.json({request:args.request,rejected:true,name:error?.name,remote:error?.remote===true,error:String(error).slice(0,400)});}
      }
      default:return new Response('unknown operation',{status:400});
    }
  }
};
