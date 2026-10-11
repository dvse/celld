const BUILD = "v2-binding"; const MODE = "base";
// Concatenated after an immutable BUILD/MODE declaration, then native no_bundle deployment.
import { DurableObject, WorkerEntrypoint } from 'cloudflare:workers';
const ISOLATE = crypto.randomUUID();
const check = (ok, text) => { if (!ok) throw new Error(text); };
const ident = x => { check(typeof x === 'string' && /^[A-Za-z0-9:_-]{1,100}$/.test(x), 'bounded identifier'); return x; };
export class UpgradeRoot extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.gates = new Map(); this.jobs = new Map(); }
  identity() { return { root: String(this.ctx.id), isolate: ISOLATE, build: BUILD, mode: MODE }; }
  async prepare() {
    const s = this.ctx.storage.sql;
    s.exec('CREATE TABLE IF NOT EXISTS items (k TEXT PRIMARY KEY, value INTEGER NOT NULL, label TEXT NOT NULL)');
    s.exec('CREATE TABLE IF NOT EXISTS ops (id TEXT PRIMARY KEY, k TEXT NOT NULL, delta INTEGER NOT NULL, writer TEXT NOT NULL)');
    s.exec('CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v INTEGER NOT NULL)');
    s.exec("INSERT OR IGNORE INTO meta VALUES ('schema',1),('migrations',0)");
    s.exec('CREATE TABLE IF NOT EXISTS alarm_plan (id INTEGER PRIMARY KEY, op TEXT NOT NULL, due INTEGER NOT NULL)');
    s.exec('CREATE TABLE IF NOT EXISTS alarm_receipts (op TEXT PRIMARY KEY, writer TEXT NOT NULL, schema_version INTEGER NOT NULL, total INTEGER NOT NULL)');
    await this.ctx.storage.sync(); return this.snapshot();
  }
  gate(name) {
    ident(name); check(this.gates.size < 24 || this.gates.has(name), 'gate count bound');
    if (!this.gates.has(name)) { let resolve; const promise = new Promise(r => { resolve = r; }); this.gates.set(name, { promise, resolve }); }
    return this.gates.get(name);
  }
  async waitGate(name) {
    if (!name) return;
    if (name.startsWith('external:')) {
      ident(name);const token='UPG_RELEASE '+String(this.ctx.id)+' '+name,deadline=Date.now()+45000;
      for(let attempt=0;attempt<45 && Date.now()<deadline;attempt++) {
        const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),Math.min(3000,Math.max(1,deadline-Date.now())));
        try {
          const response=await fetch('http://192.168.77.2:19000/__state',{signal:controller.signal,redirect:'error'});check(response.status===200,'external gate control unavailable');
          const reader=response.body.getReader(),parts=[];let size=0,done=false;
          try {for(let read=0;read<256;read++){const part=await reader.read();if(part.done){done=true;break;}size+=part.value.byteLength;if(size>2097152){await reader.cancel();throw new Error('external gate evidence bound');}parts.push(part.value);}if(!done){await reader.cancel();throw new Error('external gate read-operation bound');}}
          finally {reader.releaseLock();}
          const bytes=new Uint8Array(size);let offset=0;for(const part of parts){bytes.set(part,offset);offset+=part.byteLength;}
          const state=JSON.parse(new TextDecoder().decode(bytes));check(Date.now()<deadline,'external gate deadline');if(state.effects.includes(token))return;
        } catch(error) {throw new Error('external gate control unavailable: '+String(error));}
        finally {clearTimeout(timer);}
        await new Promise(resolve=>setTimeout(resolve,Math.min(1000,Math.max(0,deadline-Date.now()))));
      }
      throw new Error('external gate deadline');
    }
    let timer;
    try { await Promise.race([this.gate(name).promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('gate deadline')), 45000); })]); }
    finally { clearTimeout(timer); }
  }
  release({gates}) { check(Array.isArray(gates) && gates.length <= 24, 'release bound'); for (const name of gates) this.gate(name).resolve(); return {released:gates}; }
  status() { return {...this.identity(), jobs:[...this.jobs].map(([request,phase]) => ({request,phase}))}; }
  snapshot() {
    const s = this.ctx.storage.sql;
    return {columns:[...s.exec('PRAGMA table_info(items)')].map(x => x.name), items:[...s.exec('SELECT * FROM items ORDER BY k')], ops:[...s.exec('SELECT * FROM ops ORDER BY id')], meta:[...s.exec('SELECT * FROM meta ORDER BY k')], indexes:[...s.exec("SELECT name FROM sqlite_master WHERE type='index' AND name='unique_label'")], plans:[...s.exec('SELECT * FROM alarm_plan ORDER BY id')], alarms:[...s.exec('SELECT * FROM alarm_receipts ORDER BY op')]};
  }
  seed({items}) { check(Array.isArray(items) && items.length <= 8,'seed bound'); this.ctx.storage.transactionSync(() => { for (const row of items) { ident(row.k); ident(row.label); check(Number.isSafeInteger(row.value) && Math.abs(row.value) <= 100, 'seed value'); this.ctx.storage.sql.exec('INSERT INTO items(k,value,label) VALUES (?,?,?)',row.k,row.value,row.label); } }); return this.snapshot(); }
  business() { const field = MODE === 'rebuild' ? 'units' : 'value'; return [...this.ctx.storage.sql.exec('SELECT k,'+field+' AS amount,label FROM items ORDER BY k')]; }
  async apply({request,op,key='a',delta=1,gate=''}) {
    ident(request); ident(op); ident(key); check(Number.isSafeInteger(delta) && Math.abs(delta)<=9,'delta bound'); check(this.jobs.size<96,'job bound'); this.jobs.set(request,'waiting');
    try { await this.waitGate(gate); let changed=false;
      this.ctx.storage.transactionSync(() => {
        const s=this.ctx.storage.sql; if ([...s.exec('SELECT id FROM ops WHERE id=?',op)].length) return;
        const field=MODE==='rebuild'?'units':'value'; check([...s.exec('SELECT k FROM items WHERE k=?',key)].length===1,'missing item');
        s.exec('UPDATE items SET '+field+'='+field+'+? WHERE k=?',MODE==='rebuild'?delta*10:delta,key);
        s.exec('INSERT INTO ops VALUES (?,?,?,?)',op,key,delta,BUILD); changed=true;
      }); this.jobs.set(request,'sql-finished'); console.log('UPG_SQL '+String(this.ctx.id)+' '+request);
      return {op,changed,writer:BUILD,identity:this.identity()};
    } finally { this.jobs.set(request,'settled'); }
  }
  async migrate({request='migration',gate=''}) {
    ident(request); check(this.jobs.size<96,'job bound'); this.jobs.set(request,'waiting');
    try { await this.waitGate(gate); let changed=false;
      this.ctx.storage.transactionSync(() => {
        const s=this.ctx.storage.sql, schema=s.exec("SELECT v FROM meta WHERE k='schema'").one().v;
        const target=MODE==='add'?2:MODE==='rebuild'||MODE==='abort'?3:MODE==='unique'?4:0;
        check(target!==0,'no migration in this build'); if(schema===target)return; check(schema===1,'unsupported schema transition');
        if(MODE==='add')s.exec("ALTER TABLE items ADD COLUMN note TEXT NOT NULL DEFAULT 'legacy'");
        if(MODE==='unique')s.exec('CREATE UNIQUE INDEX unique_label ON items(label)');
        if(MODE==='rebuild'||MODE==='abort') {
          s.exec('CREATE TABLE replacement (k TEXT PRIMARY KEY, units INTEGER NOT NULL, label TEXT NOT NULL)');
          s.exec('INSERT INTO replacement SELECT k,value*10,label FROM items'); s.exec('DROP TABLE items');
          if(MODE==='abort')throw new Error('planned migration abort after DROP');
          s.exec('ALTER TABLE replacement RENAME TO items');
        }
        s.exec("UPDATE meta SET v=? WHERE k='schema'",target); s.exec("UPDATE meta SET v=v+1 WHERE k='migrations'"); changed=true;
      }); return {changed,build:BUILD,snapshot:this.snapshot()};
    } finally { this.jobs.set(request,'settled'); }
  }
  relabel({key,label}) {ident(key);ident(label);this.ctx.storage.sql.exec('UPDATE items SET label=? WHERE k=?',label,key);return this.snapshot();}
  note({key,note}) {ident(key);ident(note);check(MODE==='add','note feature absent');this.ctx.storage.sql.exec('UPDATE items SET note=? WHERE k=?',note,key);return this.snapshot();}
  async arm({op,delayMs}) {ident(op);check(Number.isInteger(delayMs)&&delayMs>=1000&&delayMs<=120000,'alarm deadline bound');const due=Date.now()+delayMs;this.ctx.storage.sql.exec('INSERT OR REPLACE INTO alarm_plan VALUES (1,?,?)',op,due);await this.ctx.storage.setAlarm(due);await this.ctx.storage.sync();return {op,due,build:BUILD};}
  async cancelAlarm() {await this.ctx.storage.deleteAlarm();this.ctx.storage.sql.exec('DELETE FROM alarm_plan');await this.ctx.storage.sync();return {alarm:await this.ctx.storage.getAlarm()};}
  async alarmState() {return {now:Date.now(),alarm:await this.ctx.storage.getAlarm(),snapshot:this.snapshot()};}
  async alarm() {
    const s=this.ctx.storage.sql, plans=[...s.exec('SELECT op FROM alarm_plan WHERE id=1')];if(!plans.length)return;
    this.ctx.storage.transactionSync(() => {const op=plans[0].op;if([...s.exec('SELECT op FROM alarm_receipts WHERE op=?',op)].length)return;const schema=s.exec("SELECT v FROM meta WHERE k='schema'").one().v;const field=schema===3?'units':'value';const total=s.exec('SELECT SUM('+field+') AS n FROM items').one().n; s.exec('INSERT INTO alarm_receipts VALUES (?,?,?,?)',op,BUILD,schema,total);});
    await this.ctx.storage.sync();console.log('UPG_ALARM '+String(this.ctx.id)+' '+plans[0].op+' '+BUILD);
  }
}
export class SiblingRoot extends UpgradeRoot {}
export class OldAPI extends WorkerEntrypoint { async call(input) { const root=this.env.ROOT.getByName(ident(input.root));try{return {entry:'OldAPI',value:await root[input.method](input.args||{})};}finally{root[Symbol.dispose]?.();} } }
export class NewAPI extends WorkerEntrypoint { async call(input) { const root=this.env.ROOT.getByName(ident(input.root));try{return {entry:'NewAPI',value:await root[input.method](input.args||{})};}finally{root[Symbol.dispose]?.();} } }
const METHODS=new Set(['prepare','identity','seed','snapshot','business','status','release','apply','migrate','relabel','note','arm','cancelAlarm','alarmState']);
export default {async fetch(request,env) {
  if(new URL(request.url).pathname==='/health')return Response.json({profile:'deployment-recovery',build:BUILD});
  try { const input=await request.json();check(METHODS.has(input.method),'unsupported fixture method'); const namespace=input.namespace==='sibling'?env.SIBLING:(env.ROOT||env.RENAMED);check(namespace,'class namespace absent');const root=namespace.getByName(ident(input.root));try {return Response.json(await root[input.method](input.args||{}));}finally{root[Symbol.dispose]?.();} }
  catch(error){return Response.json({error:String(error),build:BUILD},{status:500});}
}};
