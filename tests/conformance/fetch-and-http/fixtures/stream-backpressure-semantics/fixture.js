import { cases } from './cases.js';
const PROFILE = 'direct-celld-stream-backpressure-semantics-v1';

function context() {
  const assertions = []; const observations = []; const gates = []; const owners = [];
  let timers = 0; let checkpoints = 0; let callbackCalls = 0;
  function describe(value) {
    if (value === undefined) return { type: 'undefined' };
    if (value instanceof Error) return { type: 'Error', name: value.name, message: value.message };
    if (Array.isArray(value)) return value.map(describe);
    if (value !== null && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, describe(value[key])]));
    return value;
  }
  function record(actual, expected, label, passed) {
    assertions.push({ label, actual: describe(actual), expected: describe(expected), passed });
    if (!passed) { const error = new Error(label); error.assertionFailure = true; throw error; }
  }
  function observe(promise, label) {
    if (observations.length >= 192) throw new Error('fixture promise budget exceeded');
    const state = { label, status: 'pending', original: promise };
    state.promise = Promise.resolve(promise).then(
      value => { state.status = 'fulfilled'; return { status: 'fulfilled', value }; },
      reason => { state.status = 'rejected'; return { status: 'rejected', reason }; },
    );
    observations.push(state); return state;
  }
  async function value(state) {
    const outcome = await state.promise;
    if (outcome.status === 'rejected') throw outcome.reason;
    return outcome.value;
  }
  function acquire(stream, kind) {
    if (owners.length >= 2) throw new Error('fixture owner budget exceeded');
    const owner = { stream, kind, value: kind === 'reader' ? stream.getReader() : stream.getWriter(), released: false };
    owners.push(owner);
    owner.closed = observe(owner.value.closed, kind + '-closed');
    if (kind === 'writer') observe(owner.value.ready, 'initial-writer-ready');
    return owner;
  }
  function release(owner) {
    if (owner.released) return;
    owner.value.releaseLock(); owner.released = true;
    // Public getters after release can expose fresh rejected promises.
    observe(owner.value.closed, 'released-' + owner.kind + '-closed');
    if (owner.kind === 'writer') observe(owner.value.ready, 'released-writer-ready');
  }
  const t = {
    assertions,
    equal(actual, expected, label) { record(actual, expected, label, Object.is(actual, expected)); },
    same(actual, expected, label) { record(Object.is(actual, expected), true, label, Object.is(actual, expected)); },
    deep(actual, expected, label) { record(actual, expected, label, JSON.stringify(describe(actual)) === JSON.stringify(describe(expected))); },
    observe, value, release,
    writer(stream) { return acquire(stream, 'writer'); },
    reader(stream) { return acquire(stream, 'reader'); },
    write(owner, chunk, label) {
      const state = observe(owner.value.write(chunk), label);
      observe(owner.value.ready, label + '-ready');
      return state;
    },
    close(owner, label) {
      const state = observe(owner.value.close(), label);
      observe(owner.value.ready, label + '-ready');
      return state;
    },
    read(owner, label) { return observe(owner.value.read(), label); },
    callback(label, fn) {
      // Wrap only fixture-owned callbacks to record their real returned promise.
      // The return value is unchanged; no stream algorithm or global is replaced.
      return function (...args) {
        if (++callbackCalls > 16) throw new Error('fixture callback budget exceeded');
        try {
          const result = fn.apply(this, args);
          observe(Promise.resolve(result), label);
          return result;
        } catch (error) {
          observe(Promise.reject(error), label);
          throw error;
        }
      };
    },
    gate(label) {
      if (gates.length >= 16) throw new Error('fixture gate budget exceeded');
      let resolve;
      const gate = { label, opened: false, promise: new Promise(r => { resolve = r; }) };
      gate.open = () => { if (!gate.opened) { gate.opened = true; resolve(); } };
      observe(gate.promise, label + '-gate'); gates.push(gate); return gate;
    },
    checkpoint() {
      if (++checkpoints > 12) throw new Error('fixture checkpoint budget exceeded');
      // One task fence lets already-enabled promise jobs settle. Pending-state
      // claims also require explicit closed callback gates or missing demand.
      timers++;
      const promise = new Promise(resolve => setTimeout(() => { timers--; resolve(); }, 0));
      return value(observe(promise, 'task-fence-' + checkpoints));
    },
    async cleanup() {
      const failures = []; const stops = [];
      // Milestone gates are also opened only for cleanup, never as trace evidence.
      for (const gate of gates) gate.open();
      // Initiate both sides before joining anything. Readable cancellation
      // unblocks HWM0 transform writes even when an assertion precedes read().
      for (const kind of ['reader', 'writer']) {
        for (const owner of owners.filter(entry => entry.kind === kind)) {
          if (owner.released || owner.closed.status !== 'pending') continue;
          try {
            const promise = kind === 'reader' ? owner.value.cancel('fixture-cleanup') : owner.value.abort('fixture-cleanup');
            stops.push(observe(promise, 'cleanup-' + kind + '-stop'));
            if (kind === 'writer') observe(owner.value.ready, 'cleanup-writer-ready');
          } catch (error) { failures.push('stop ' + kind + ': ' + String(error)); }
        }
      }
      await Promise.all(stops.map(state => state.promise));
      // Callback observations can be added while the original operations settle.
      // The observation/callback budgets bound this dynamic join.
      let joined = 0;
      while (joined < observations.length) {
        const batch = observations.slice(joined); joined = observations.length;
        await Promise.all(batch.map(state => state.promise));
      }
      const terminalProofs = owners.map(owner => ({ kind: owner.kind, closed: owner.closed.status }));
      for (const owner of owners) {
        if (owner.closed.status === 'pending') failures.push('unterminated ' + owner.kind);
        try { release(owner); } catch (error) { failures.push('release ' + owner.kind + ': ' + String(error)); }
      }
      await Promise.all(observations.map(state => state.promise));
      const publicLocks = owners.filter(owner => owner.stream.locked).length;
      const pending = observations.filter(state => state.status === 'pending').map(state => state.label);
      if (publicLocks || pending.length || timers || gates.some(gate => !gate.opened)) failures.push('residual local work');
      return {
        status: failures.length ? 'INCOMPLETE' : 'COMPLETE', scope: 'local-stream-settlement', failures,
        terminalProofs, publicLocks, pending, timers, checkpoints, callbackCalls,
        gates: gates.map(gate => ({ label: gate.label, opened: gate.opened })),
        observations: observations.map(state => ({ label: state.label, status: state.status })),
        outgoingRequests: 0, persistentWrites: 0, retainedCapabilities: 0,
        externalOwnedTeardown: 'REQUIRED_FOR_ACCEPTANCE',
      };
    },
  };
  return t;
}

export default {
  async fetch(request) {
    const match = /^https?:\/\/[^/]+\/case\/(S30[1-6])$/.exec(request.url);
    const id = match && match[1];
    if (request.method !== 'GET' || !id || !Object.prototype.hasOwnProperty.call(cases, id)) {
      return Response.json({ profile: PROFILE, status: 'NOT_A_CASE' }, { status: 404 });
    }
    const test = context(); let status = 'PASS'; let error = null;
    try { await cases[id](test); if (!test.assertions.length) throw new Error('empty assertion trace'); }
    catch (cause) { status = 'FAIL'; error = { kind: cause.assertionFailure ? 'ASSERTION' : 'UNEXPECTED_EXCEPTION', message: String(cause.message || cause) }; }
    const cleanup = await test.cleanup();
    if (cleanup.status !== 'COMPLETE') status = 'FAIL';
    return Response.json({ profile: PROFILE, id, status, traceEntered: true, assertions: test.assertions, error, cleanup, runtimeWitness: 'External exact-source direct-celld build/deployment and bounded-process witnesses required.' }, { status: status === 'PASS' ? 200 : 500 });
  },
};
