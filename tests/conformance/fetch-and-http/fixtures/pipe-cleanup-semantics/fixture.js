import { cases } from './cases.js';
const PROFILE = 'direct-celld-pipe-cleanup-semantics-v1';

function context() {
  const assertions = []; const gates = []; const observations = []; const pipes = [];
  const sources = []; const sinks = []; const owners = []; let timers = 0;
  function describe(value) {
    if (value === undefined) return { type: 'undefined' };
    if (value instanceof Error) return { type: 'Error', name: value.name, message: value.message };
    return value;
  }
  function record(actual, expected, label, passed) {
    assertions.push({ label, actual: describe(actual), expected: describe(expected), passed });
    if (!passed) { const error = new Error(label); error.assertionFailure = true; throw error; }
  }
  function observe(promise, label) {
    const state = { label, status: 'pending' };
    state.promise = Promise.resolve(promise).then(
      value => { state.status = 'fulfilled'; return { status: 'fulfilled', value }; },
      reason => { state.status = 'rejected'; return { status: 'rejected', reason }; },
    );
    observations.push(state); return state;
  }
  function callback(fn, label) {
    return (...args) => {
      try {
        const result = fn ? fn(...args) : undefined;
        const promise = Promise.resolve(result); observe(promise, label); return promise;
      } catch (error) {
        observe(Promise.reject(error), label); throw error;
      }
    };
  }
  async function join(promise, label) {
    const result = await observe(promise, label).promise;
    if (result.status === 'rejected') throw result.reason;
    return result.value;
  }
  function acquire(stream, kind) {
    const value = kind === 'reader' ? stream.getReader() : stream.getWriter();
    // Releasing an owner may reject these even when callers never inspect them.
    value.closed.catch(() => {});
    if (kind === 'writer') value.ready.catch(() => {});
    const owner = { value, kind, released: false }; owners.push(owner); return owner;
  }
  function release(owner) { if (!owner.released) { owner.value.releaseLock(); owner.released = true; } }
  const t = {
    assertions,
    equal(actual, expected, label) { record(actual, expected, label, Object.is(actual, expected)); },
    same(actual, expected, label) { record(Object.is(actual, expected), true, label, Object.is(actual, expected)); },
    deep(actual, expected, label) { record(actual, expected, label, JSON.stringify(actual) === JSON.stringify(expected)); },
    before(events, first, second, label) { const a = events.indexOf(first); const b = events.indexOf(second); record(a >= 0 && b > a, true, label, a >= 0 && b > a); },
    unlocked(source, sink, label) { t.deep([source.stream.locked, sink.stream.locked], [false, false], label); },
    locked(source, sink, label) { t.deep([source.stream.locked, sink.stream.locked], [true, true], label); },
    gate(label) {
      let resolve; const gate = { label, opened: false, promise: new Promise(r => { resolve = r; }) };
      gate.open = () => { if (!gate.opened) { gate.opened = true; resolve(); } };
      gates.push(gate); return gate;
    },
    checkpoint() {
      // One finite event-loop checkpoint, not a timing/latency pass oracle.
      // Gates, not elapsed milliseconds, prevent the operation from completing.
      timers++;
      return new Promise(resolve => setTimeout(() => { timers--; resolve(); }, 0));
    },
    source(chunks, end, cancel) {
      if (chunks.length > 2) throw new Error('fixture source budget exceeded');
      const source = { stream: null, controller: null };
      source.stream = new ReadableStream({
        start(controller) { source.controller = controller; for (const value of chunks) controller.enqueue(value); if (end) controller.close(); },
        cancel: callback(cancel, 'underlying-source-cancel'),
      });
      sources.push(source); return source;
    },
    enqueue(source, value) { source.controller.enqueue(value); },
    closeSource(source) { source.controller.close(); },
    failSource(source, reason) { source.controller.error(reason); },
    sink(callbacks) {
      const sink = { stream: new WritableStream({ write: callback(callbacks.write, 'underlying-sink-write'), close: callback(callbacks.close, 'underlying-sink-close'), abort: callback(callbacks.abort, 'underlying-sink-abort') }) };
      sinks.push(sink); return sink;
    },
    pipe(source, sink, options = {}, controller = new AbortController()) {
      // The automatic signal is only used for emergency cleanup after a failed
      // assertion. Successful ordinary traces never abort that extra signal.
      const state = observe(source.stream.pipeTo(sink.stream, { ...options, signal: options.signal || controller.signal }), 'pipeTo');
      state.controller = controller; pipes.push(state); return state;
    },
    async writeAndClose(sink, value) {
      const owner = acquire(sink.stream, 'writer');
      try {
        await join(owner.value.write(value), 'reuse-write');
        await join(owner.value.close(), 'reuse-close');
        await join(owner.value.closed, 'reuse-writer-closed');
      } finally { release(owner); }
    },
    async drain(source) {
      const owner = acquire(source.stream, 'reader'); const values = [];
      try {
        for (let i = 0; i < 4; i++) {
          const result = await join(owner.value.read(), 'manual-read');
          if (result.done) { await join(owner.value.closed, 'manual-reader-closed'); return values; }
          values.push(result.value);
        }
        throw new Error('fixture read budget exceeded');
      } finally { release(owner); }
    },
    async cleanup() {
      const failures = []; const terminalProofs = [];
      // Release every gate independently even if the assertion failed early.
      for (const gate of gates) gate.open();
      for (const pipe of pipes) if (pipe.status === 'pending') pipe.controller.abort(new Error('fixture-cleanup'));
      await Promise.all(pipes.map(pipe => pipe.promise));
      for (const owner of owners) {
        try { release(owner); } catch (error) { failures.push('owner release: ' + String(error)); }
      }
      // Track callbacks separately: a defective pipe can settle before them.
      await Promise.all(observations.map(state => state.promise));
      for (const [kind, resources] of [['reader', sources], ['writer', sinks]]) {
        for (let i = 0; i < resources.length; i++) {
          const stream = resources[i].stream;
          if (stream.locked) { failures.push(kind + '-' + i + ' retains a lock'); continue; }
          let owner;
          try {
            owner = acquire(stream, kind);
            const closed = observe(owner.value.closed, 'cleanup-' + kind + '-closed');
            await t.checkpoint();
            if (closed.status === 'pending') {
              const stop = kind === 'reader' ? owner.value.cancel('fixture-cleanup') : owner.value.abort('fixture-cleanup');
              const stopped = await observe(stop, 'cleanup-' + kind + '-stop').promise;
              if (stopped.status === 'rejected') failures.push(kind + ' cleanup action rejected: ' + String(stopped.reason));
            }
            const outcome = await closed.promise;
            terminalProofs.push({ kind, index: i, closedPromise: outcome.status });
          } catch (error) { failures.push(kind + ' cleanup: ' + String(error)); }
          finally { if (owner) { try { release(owner); } catch (error) { failures.push('terminal owner release: ' + String(error)); } } }
        }
      }
      await Promise.all(observations.map(state => state.promise));
      const publicLocks = sources.concat(sinks).filter(resource => resource.stream.locked).length;
      const pending = observations.filter(state => state.status === 'pending').map(state => state.label);
      if (publicLocks || pending.length || timers || gates.some(gate => !gate.opened)) failures.push('residual local work');
      return { status: failures.length ? 'INCOMPLETE' : 'COMPLETE', scope: 'local-stream-settlement', failures, terminalProofs, publicLocks, pending, timers, gates: gates.map(gate => ({ label: gate.label, opened: gate.opened })), observedPromises: observations.length, outgoingRequests: 0, persistentWrites: 0, retainedCapabilities: 0, externalOwnedTeardown: 'REQUIRED_FOR_ACCEPTANCE' };
    },
  };
  return t;
}

export default {
  async fetch(request) {
    const match = /^https?:\/\/[^/]+\/case\/(S20[1-9])$/.exec(request.url);
    const id = match && match[1];
    if (request.method !== 'GET' || !id || !Object.prototype.hasOwnProperty.call(cases, id)) return Response.json({ profile: PROFILE, status: 'NOT_A_CASE' }, { status: 404 });
    const test = context(); let status = 'PASS'; let error = null;
    try { await cases[id](test); if (!test.assertions.length) throw new Error('empty assertion trace'); }
    catch (cause) { status = 'FAIL'; error = { kind: cause && cause.assertionFailure ? 'ASSERTION' : 'UNEXPECTED_EXCEPTION', message: String(cause && cause.message || cause) }; }
    const cleanup = await test.cleanup();
    if (cleanup.status !== 'COMPLETE') status = 'FAIL';
    return Response.json({ profile: PROFILE, id, status, traceEntered: true, assertions: test.assertions, error, cleanup, runtimeWitness: 'External exact direct-celld build, deployment, process limits, deadline and teardown evidence required.' }, { status: status === 'PASS' ? 200 : 500 });
  },
};
