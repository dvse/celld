// Native Workers RPC only. No local transport, raw envelope or runtime-private hooks.
import * as cf from 'cloudflare:workers';
export const INSTANCE = crypto.randomUUID();
export const check = (value, why) => { if (!value) throw new Error(why); };
export const equal = (a, b, why) => check(JSON.stringify(a) === JSON.stringify(b), why + ': ' + JSON.stringify(a));
export const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
export async function poll(read, accept, why) {
  for (let n = 0; n < 150; n++) { const value = await read(); if (accept(value)) return value; await delay(10); }
  throw new Error('SETTLEMENT_TIMEOUT: ' + why);
}
export async function rejected(call, category, why) {
  let seen = false, error;
  try { await call(); } catch (e) { seen = true; error = e; }
  check(seen, 'expected rejection: ' + why);
  if (category === 'disposed') check(error?.name === 'Error' && /disposed/i.test(String(error)), 'wrong disposed error: ' + String(error));
  else if (category === 'clone') equal(error?.name, 'DataCloneError', 'wrong clone error');
  else check(error?.name === 'Error' && String(error).includes(category), 'wrong application error: ' + String(error));
  return { name: error?.name, message: String(error) };
}
export async function drop(value) { if (value != null && typeof value[Symbol.dispose] === 'function') await value[Symbol.dispose](); }
export class OrderPreconditionError extends Error {
  constructor(message) { super(message); this.name = 'OrderPreconditionError'; this.code = 'ORDER_PRECONDITION'; }
}
export const requireApi = (ok, message) => { if (!ok) throw new OrderPreconditionError(message); };

function newState() { return { events: [], disposals: {}, created: {}, slots: new Map(), borrowed: new Map(), gates: new Map(), jobs: new Set(), errors: [] }; }
function gateFor(state, name) {
  let gate = state.gates.get(name);
  if (!gate) {
    let release; const promise = new Promise(resolve => { release = resolve; });
    gate = { promise, release, open: false }; state.gates.set(name, gate);
  }
  return gate;
}
function releaseGate(state, name) { const g = gateFor(state, name); if (!g.open) { g.open = true; g.release(); } }
function record(state, value) { check(state.events.length < 100, 'fixture event bound'); state.events.push(value); }
class Endpoint extends cf.RpcTarget {
  constructor(state, label) { super(); this.state = state; this.label = label; state.created[label] = (state.created[label] ?? 0) + 1; }
  ping() { return this.label; }
  mark(value) { record(this.state, this.label + ':mark:' + value); return value; }
  fail(value) { record(this.state, this.label + ':fail:' + value); throw new Error('planned:' + value); }
  get bad() { record(this.state, this.label + ':getter'); throw new Error('planned:getter'); }
  async wait(gate, value, fail = false) {
    record(this.state, this.label + ':enter:' + value);
    await gateFor(this.state, gate).promise;
    record(this.state, this.label + ':exit:' + value);
    if (fail) throw new Error('planned:' + value);
    return value;
  }
  async call(callback, value) { record(this.state, this.label + ':call:' + value); return await callback.visit(value); }
  rejectParameter(_callback) { record(this.state, this.label + ':reject-parameter'); throw new Error('planned:parameter'); }
  async holdBorrow(callback, gate, value, fail = false) {
    record(this.state, this.label + ':borrow:' + value);
    await gateFor(this.state, gate).promise;
    if (fail) throw new Error('planned:' + value);
    return await callback.visit(value);
  }
  async reenter(callback) {
    record(this.state, this.label + ':outer:start');
    const value = await callback.action();
    record(this.state, this.label + ':outer:end');
    return value;
  }
  child(label) { record(this.state, this.label + ':child:' + label); return new Endpoint(this.state, label); }
  async laterChild(gate, label) {
    record(this.state, this.label + ':prepare:' + label);
    await gateFor(this.state, gate).promise;
    record(this.state, this.label + ':publish:' + label);
    return new Endpoint(this.state, label);
  }
  async callbackChild(callback) { record(this.state, this.label + ':callback-child'); return await callback.child(); }
  async forward(destination, callback) {
    record(this.state, this.label + ':forward:start');
    const value = await destination.call(callback, 'forwarded');
    record(this.state, this.label + ':forward:end');
    return value;
  }
  [Symbol.dispose]() { this.state.disposals[this.label] = (this.state.disposals[this.label] ?? 0) + 1; }
}
export class LocalCallback extends cf.RpcTarget {
  constructor(state, label, hooks = {}) { super(); this.state = state; this.label = label; this.hooks = hooks; }
  async visit(value) {
    this.state.events.push(this.label + ':' + value);
    if (this.hooks.visit) return await this.hooks.visit(value);
    return this.label + ':' + value;
  }
  async action() { this.state.events.push(this.label + ':action'); return await this.hooks.action(); }
  child() { this.state.events.push(this.label + ':child'); return this.hooks.child(); }
  [Symbol.dispose]() { this.state.disposals++; }
}
export class RootBase extends cf.DurableObject {
  constructor(ctx, env) { super(ctx, env); this.orderStates = new Map(); }
  inspect() { return { isolate: INSTANCE, root: String(this.ctx.id) }; }
  profile() { return { rpc_params_dup_stubs: globalThis.Cloudflare?.compatibilityFlags?.rpc_params_dup_stubs === true, rpcStub: typeof cf.RpcStub === 'function', rpcPromise: typeof cf.RpcPromise === 'function', rpcProperty: typeof cf.RpcProperty === 'function', symbolDispose: typeof Symbol.dispose === 'symbol' }; }
  state(tag) { let state = this.orderStates.get(tag); if (!state) { state = newState(); this.orderStates.set(tag, state); } return state; }
  open(tag, label) { return new Endpoint(this.state(tag), label); }
  tree(tag) { const state = this.state(tag); return { left: new Endpoint(state, 'left'), right: new Endpoint(state, 'right') }; }
  aliases(tag) { const handle = new cf.RpcStub(new Endpoint(this.state(tag), 'alias')); return { first: handle, second: handle }; }
  stats(tag) { const s = this.state(tag); return { events: [...s.events], disposals: { ...s.disposals }, slots: [...s.slots.keys()].sort(), errors: [...s.errors] }; }
  release(tag, gate) { releaseGate(this.state(tag), gate); return 'released'; }
  async retain(tag, slot, callback, fail = false) {
    const s = this.state(tag), prior = s.slots.get(slot);
    s.slots.set(slot, callback.dup());
    await drop(prior);
    record(s, 'retain:' + slot);
    if (fail) throw new Error('planned:retain');
    return 'retained';
  }
  async remove(tag, slot) {
    const s = this.state(tag), value = s.slots.get(slot); s.slots.delete(slot);
    await drop(value); record(s, 'remove:' + slot); return value ? 'removed' : 'absent';
  }
  async emit(tag, slot, value) {
    const s = this.state(tag), callback = s.slots.get(slot);
    record(s, 'emit:' + slot + ':' + value);
    return callback ? await callback.visit(value) : 'absent';
  }
  notify(tag, slot, value) {
    const s = this.state(tag), callback = s.slots.get(slot); check(callback, 'missing notification slot');
    record(s, 'notify:' + slot + ':' + value);
    const task = Promise.resolve(callback.visit(value)).then(
      () => record(s, 'notified:' + value),
      error => { s.errors.push(String(error)); record(s, 'notification-failed:' + value); }
    );
    s.jobs.add(task); task.finally(() => s.jobs.delete(task));
    return 'queued';
  }
  take(tag, slot) { const s = this.state(tag), callback = s.slots.get(slot); check(callback, 'missing transfer slot'); s.slots.delete(slot); record(s, 'take:' + slot); return callback; }
  async aliasParameters(tag, one, two) {
    const s = this.state(tag); record(s, 'alias-params');
    // Do not impose JavaScript reference identity on native parameter aliases.
    return [await one.visit('one'), await two.visit('two')];
  }
  borrowWithoutDup(tag, callback) { this.state(tag).borrowed.set('expired', callback); record(this.state(tag), 'borrow-no-dup'); return 'borrowed'; }
  async callBorrowed(tag) { record(this.state(tag), 'call-expired'); return await this.state(tag).borrowed.get('expired').visit('expired'); }
  async cleanup(tag) {
    const s = this.orderStates.get(tag); if (!s) return { status: 'ok', empty: true };
    const failures = [];
    for (const [name, gate] of s.gates) { try { gate.release(); } catch (error) { failures.push('gate ' + name + ': ' + String(error)); } }
    const slots = [...s.slots.entries()]; s.slots.clear();
    for (const [name, value] of slots) { try { await drop(value); } catch (error) { failures.push('slot ' + name + ': ' + String(error)); } }
    const borrowed = [...s.borrowed.entries()]; s.borrowed.clear();
    for (const [name, value] of borrowed) { try { await drop(value); } catch (error) { failures.push('borrowed ' + name + ': ' + String(error)); } }
    const jobs = await Promise.allSettled([...s.jobs]);
    for (const job of jobs) if (job.status === 'rejected') failures.push('notification cleanup: ' + String(job.reason));
    return { status: failures.length ? 'FAIL' : 'ok', failures, slots: s.slots.size, jobs: s.jobs.size, gates: s.gates.size };
  }
  async settleCleanup(tag) {
    const state = this.state(tag);
    await poll(async () => state, s => Object.entries(s.created).every(([label, count]) => s.disposals[label] === count), 'all endpoint cohorts disposed during cleanup');
    const result = { status: 'ok', created: { ...state.created }, disposed: { ...state.disposals }, slots: state.slots.size, jobs: state.jobs.size };
    check(result.slots === 0 && result.jobs === 0, 'cleanup still owns callbacks or notifications');
    this.orderStates.delete(tag); return result;
  }
}

export class Session {
  constructor(peer, tag) { this.peer = peer; this.tag = tag; this.handles = []; this.pending = []; this.localReleases = []; this.callbacks = []; }
  own(value) { this.handles.push(value); return value; }
  async target(label = 'main') { return this.own(await this.peer.open(this.tag, label)); }
  callback(label, hooks = {}) {
    const state = { events: [], disposals: 0 };
    const target = new LocalCallback(state, label, hooks);
    const callback = { state, target, expectedDisposals: 1, stub: this.own(new cf.RpcStub(target)) }; this.callbacks.push(callback); return callback;
  }
  localGate() { let release; const promise = new Promise(resolve => { release = resolve; }); this.localReleases.push(release); return { promise, release }; }
  watch(value) { const pending = Promise.resolve(value); pending.catch(() => {}); this.pending.push(pending); return pending; }
  async stats() { return await this.peer.stats(this.tag); }
  async events(expected) { const s = await this.stats(); equal(s.events, expected, 'ordered provider events'); return s; }
  async entered(event) { return await poll(() => this.stats(), s => s.events.includes(event), 'explicit provider barrier ' + event); }
  async disposed(label, count = 1) { return await poll(() => this.stats(), s => s.disposals[label] === count, 'remote disposal ' + label); }
  async callbackDisposed(callback, count = 1) { return await poll(async () => callback.state, s => s.disposals === count, 'local callback disposal'); }
  async alive(target) { equal(await target.ping(), 'main', 'target liveness'); }
  async cleanup() {
    const failures = [];
    const attempt = async (label, operation) => {
      try { return await operation(); } catch (error) { failures.push(label + ': ' + String(error)); }
    };
    for (const [index, release] of this.localReleases.entries()) await attempt('local gate ' + index, release);
    // Try every independent cleanup even after an ordinary error. The external
    // supervisor remains responsible for a hung operation's outer deadline.
    const remote = await attempt('provider release', () => this.peer.cleanup(this.tag));
    if (remote?.status === 'FAIL') failures.push('provider release: ' + JSON.stringify(remote.failures));
    await attempt('pending settlement', () => Promise.allSettled(this.pending));
    for (const [index, value] of [...this.handles].reverse().entries()) await attempt('owned handle ' + index, () => drop(value));
    for (const [index, callback] of this.callbacks.entries()) await attempt('callback cohort ' + index, () => this.callbackDisposed(callback, callback.expectedDisposals));
    const final = await attempt('provider cohort verification', () => this.peer.settleCleanup(this.tag));
    if (failures.length) throw new Error('CLEANUP_FAILURE: ' + JSON.stringify(failures));
    return final;
  }
}
