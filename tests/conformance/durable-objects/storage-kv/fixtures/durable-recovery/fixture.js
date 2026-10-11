// Ordinary DO RPC only. No Loader, STATELESS service, retained RpcTarget or raw wire path.
import { DurableObject } from 'cloudflare:workers';
const ISOLATE = crypto.randomUUID();
const check = (ok, message) => { if (!ok) throw new Error(message); };
const id = value => { check(typeof value === 'string' && /^[a-zA-Z0-9:_-]{1,100}$/.test(value), 'invalid bounded identifier'); return value; };
export class RecoveryRoot extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.gates = new Map(); this.jobs = new Map(); this.alarmStage = 'idle'; }
  identity() { return { root: String(this.ctx.id), isolate: ISOLATE }; }
  async prepare() {
    const sql = this.ctx.storage.sql;
    sql.exec('CREATE TABLE IF NOT EXISTS ledger (op TEXT PRIMARY KEY, kind TEXT NOT NULL, value INTEGER NOT NULL)');
    sql.exec('CREATE TABLE IF NOT EXISTS accounts (name TEXT PRIMARY KEY, balance INTEGER NOT NULL CHECK(balance>=0))');
    sql.exec('CREATE TABLE IF NOT EXISTS pairs (op TEXT PRIMARY KEY, left_value INTEGER NOT NULL, right_value INTEGER NOT NULL)');
    sql.exec('CREATE TABLE IF NOT EXISTS documents (name TEXT PRIMARY KEY, version INTEGER NOT NULL, value TEXT NOT NULL)');
    sql.exec('CREATE TABLE IF NOT EXISTS alarm_plan (id INTEGER PRIMARY KEY, op TEXT NOT NULL, gate TEXT NOT NULL)');
    sql.exec("INSERT OR IGNORE INTO accounts VALUES ('a',1000),('b',1000),('count',0)");
    sql.exec("INSERT OR IGNORE INTO documents VALUES ('cas',0,'initial')");
    await this.ctx.storage.sync(); return this.snapshot();
  }
  gate(name) {
    id(name); check(this.gates.size < 24 || this.gates.has(name), 'gate bound');
    if (!this.gates.has(name)) {
      let resolve; const promise = new Promise(r => { resolve = r; });
      this.gates.set(name, { promise, resolve, open: false });
    }
    return this.gates.get(name);
  }
  async waitGate(name) {
    if (!name) return;
    const gate = this.gate(name); let timer;
    try { await Promise.race([gate.promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('fixture gate deadline')), 20000); })]); }
    finally { clearTimeout(timer); }
  }
  release({ gates }) {
    check(Array.isArray(gates) && gates.length <= 24, 'release bound');
    for (const name of gates) { const gate = this.gate(name); gate.open = true; gate.resolve(); }
    return { released: gates };
  }
  status() { return { ...this.identity(), jobs: [...this.jobs].map(([request, phase]) => ({ request, phase })), alarmStage: this.alarmStage }; }
  snapshot() {
    const sql = this.ctx.storage.sql;
    return {
      ledger: [...sql.exec('SELECT op,kind,value FROM ledger ORDER BY op')],
      accounts: [...sql.exec('SELECT name,balance FROM accounts ORDER BY name')],
      pairs: [...sql.exec('SELECT op,left_value,right_value FROM pairs ORDER BY op')],
      documents: [...sql.exec('SELECT name,version,value FROM documents ORDER BY name')]
    };
  }
  async read({ request, gate = '' }) {
    id(request); check(this.jobs.size < 96, 'job bound'); this.jobs.set(request, 'waiting');
    try { await this.waitGate(gate); this.jobs.set(request, 'read'); const snapshot = this.snapshot(); console.log('DRS_READ ' + String(this.ctx.id) + ' ' + request); return snapshot; }
    finally { this.jobs.set(request, 'settled'); }
  }
  async apply(spec) {
    const { request, op, kind, gate = '', value = 1, key = '', egress = false } = spec;
    id(request); id(op); check(Number.isSafeInteger(value) && Math.abs(value) <= 100, 'value bound');
    check(this.jobs.size < 96, 'job bound'); this.jobs.set(request, 'waiting');
    try {
      await this.waitGate(gate); this.jobs.set(request, 'executing');
      const sql = this.ctx.storage.sql; let changed = true, rolledBack = false;
      const insert = (suffix = '', k = kind) => sql.exec('INSERT INTO ledger VALUES (?,?,?)', op + suffix, k, value);
      const tx = callback => this.ctx.storage.transactionSync(callback);
      if (kind === 'append' || kind === 'alarm') tx(() => insert());
      else if (kind === 'increment') tx(() => { insert(); sql.exec("UPDATE accounts SET balance=balance+? WHERE name='count'", value); });
      else if (kind === 'transfer') tx(() => {
        insert(); sql.exec("UPDATE accounts SET balance=balance-? WHERE name='a'", value);
        sql.exec("UPDATE accounts SET balance=balance+? WHERE name='b'", value);
      });
      else if (kind === 'dedup') tx(() => {
        changed = [...sql.exec('SELECT op FROM ledger WHERE op=?', op)].length === 0;
        if (changed) { insert(); sql.exec("UPDATE accounts SET balance=balance+? WHERE name='count'", value); }
      });
      else if (kind === 'cas') tx(() => {
        changed = sql.exec("SELECT version FROM documents WHERE name='cas'").one().version === 0;
        insert('', changed ? 'cas-win' : 'cas-lose');
        if (changed) sql.exec("UPDATE documents SET version=1,value=? WHERE name='cas'", op);
      });
      else if (kind === 'delete') tx(() => { id(key); insert(); sql.exec('DELETE FROM documents WHERE name=?', key); });
      else if (kind === 'document') tx(() => { id(key); insert(); sql.exec('INSERT INTO documents VALUES (?,1,?) ON CONFLICT(name) DO UPDATE SET version=version+1,value=excluded.value', key, op); });
      else if (kind === 'pair') tx(() => { insert(); sql.exec('INSERT INTO pairs VALUES (?,?,?)', op, value, -value); });
      else if (kind === 'rollback' || kind === 'constraint') {
        try { tx(() => { insert(); sql.exec("UPDATE accounts SET balance=balance+? WHERE name='count'", value);
          if (kind === 'constraint') sql.exec("UPDATE accounts SET balance=-1 WHERE name='a'");
          else throw new Error('planned rollback');
        }); } catch (error) {
          check(kind === 'constraint' ? /CHECK|constraint/i.test(String(error)) : String(error).includes('planned rollback'), 'unexpected rollback error'); rolledBack = true;
        }
        check(rolledBack, 'rollback not reached'); changed = false;
      } else if (kind === 'nested') tx(() => {
        insert(':outer', 'outer');
        try { tx(() => { insert(':inner', 'inner'); sql.exec("UPDATE accounts SET balance=balance+100 WHERE name='count'"); throw new Error('inner rollback'); }); }
        catch (error) { check(String(error).includes('inner rollback'), 'unexpected nested failure'); }
        insert(':after', 'after'); sql.exec("UPDATE accounts SET balance=balance+? WHERE name='count'", value);
      });
      else throw new Error('unsupported operation');
      this.jobs.set(request, 'sql-finished'); console.log('DRS_SQL ' + String(this.ctx.id) + ' ' + request);
      // Deliberately no explicit sync: actual response/egress output gates prove writes.
      if (egress) {
        const response = await fetch('http://192.168.77.2:19000/__effect', { method: 'POST', body: JSON.stringify({ op, kind, changed }) });
        check(response.status === 200, 'effect endpoint failed');
      }
      return { op, kind, changed, rolledBack };
    } finally { this.jobs.set(request, 'settled'); }
  }
  async arm({ op, gate = '', delayMs }) {
    id(op); if (gate) id(gate); check(Number.isInteger(delayMs) && delayMs >= 200 && delayMs <= 120000, 'alarm deadline bound');
    this.ctx.storage.sql.exec('INSERT OR REPLACE INTO alarm_plan VALUES (1,?,?)', op, gate);
    const at = Date.now() + delayMs; await this.ctx.storage.setAlarm(at); await this.ctx.storage.sync();
    return { op, at };
  }
  async alarm() {
    const plan = [...this.ctx.storage.sql.exec('SELECT op,gate FROM alarm_plan WHERE id=1')][0];
    if (!plan) return;
    this.alarmStage = 'waiting'; await this.waitGate(plan.gate); this.alarmStage = 'writing';
    this.ctx.storage.transactionSync(() => {
      this.ctx.storage.sql.exec("INSERT OR IGNORE INTO ledger VALUES (?,'alarm',1)", plan.op);
      this.ctx.storage.sql.exec('DELETE FROM alarm_plan WHERE id=1');
    });
    this.alarmStage = 'done';
  }
  async cleanup() {
    for (const gate of this.gates.values()) gate.resolve();
    await this.ctx.storage.deleteAlarm();
    await this.ctx.storage.sync();
    return { active: [...this.jobs.values()].filter(phase => phase !== 'settled').length, alarmStage: this.alarmStage };
  }
}
export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname === '/health') return Response.json({ profile: 'durable-recovery-stress-v1', operations: ['prepare','identity','status','release','read','snapshot','apply','arm','cleanup'] });
    check(request.method === 'POST', 'POST required');
    const body = await request.json(); id(body.root);
    const root = env.ROOT.getByName(body.root);
    switch (body.method) {
      case 'prepare': return Response.json(await root.prepare());
      case 'identity': return Response.json(await root.identity());
      case 'status': return Response.json(await root.status());
      case 'release': return Response.json(await root.release(body.args));
      case 'read': return Response.json(await root.read(body.args));
      case 'snapshot': return Response.json(await root.snapshot());
      case 'apply': return Response.json(await root.apply(body.args));
      case 'arm': return Response.json(await root.arm(body.args));
      case 'cleanup': return Response.json(await root.cleanup());
      default: return new Response('unknown fixture method', { status: 400 });
    }
  }
};
