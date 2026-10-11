import { cases } from './cases.js';

const PROFILE = 'direct-celld-response-clone-chunk-semantics-v1';
const EXPECTED_ASSERTIONS = 11;

function context() {
  const assertions = [];
  const streams = new Map();
  const readers = new Map();
  const startedReads = [];
  function track(stream) {
    if (!stream) throw new Error('fixture requires a non-null local stream');
    if (!streams.has(stream)) {
      if (streams.size >= 3) throw new Error('fixture stream budget exceeded');
      streams.set(stream, { id: 'stream-' + (streams.size + 1), stream, children: [], cancelled: false, reader: null });
    }
    return streams.get(stream);
  }
  function record(actual, expected, label, passed) {
    // Only booleans, strings and arrays of primitive bytes/statuses enter here.
    assertions.push({ label, actual: JSON.parse(JSON.stringify(actual)), expected: JSON.parse(JSON.stringify(expected)), passed });
    if (!passed) {
      const error = new Error(label);
      error.assertionFailure = true;
      throw error;
    }
  }
  return {
    assertions,
    equal(actual, expected, label) { record(actual, expected, label, Object.is(actual, expected)); },
    deep(actual, expected, label) { record(actual, expected, label, JSON.stringify(actual) === JSON.stringify(expected)); },
    stream(stream) { track(stream); return stream; },
    clone(owner) {
      const prior = track(owner.body);
      let copy;
      try {
        copy = owner.clone(); // The real public API; no tee, drain or copy shim.
        return copy;
      } finally {
        const current = track(owner.body);
        if (copy) {
          const cloned = track(copy.body);
          if (current !== prior) prior.children = [current, cloned];
        }
      }
    },
    reader(stream) {
      const state = track(stream);
      if (readers.size >= 2) throw new Error('fixture reader budget exceeded');
      const reader = stream.getReader();
      const entry = { reader, stream: state, reads: [], cancelled: false, released: false };
      state.reader = entry;
      readers.set(reader, entry);
      return reader;
    },
    read(reader) {
      const entry = readers.get(reader);
      if (!entry || entry.reads.length >= 2) throw new Error('fixture read budget exceeded');
      const outcome = { status: 'pending', done: null };
      entry.reads.push(outcome);
      // Deferring only starts the subject read in a microtask. Both sibling
      // operations are registered before their allSettled join is awaited.
      const pending = Promise.resolve().then(() => reader.read()).then(
        result => { outcome.status = 'fulfilled'; outcome.done = result.done === true; return result; },
        error => { outcome.status = 'rejected'; throw error; },
      );
      startedReads.push(pending);
      return pending;
    },
    async cleanup() {
      const failures = [];
      // Never race cleanup against a subject read. If any started read remains
      // pending, the external deadline ends the owned run with UNKNOWN plus
      // incomplete cleanup. There is no in-fixture timeout that declares PASS.
      await Promise.allSettled(startedReads);
      const cancellations = [];
      let cancelledReaders = 0;
      let cancelledUnlockedStreams = 0;
      for (const entry of readers.values()) {
        cancellations.push(Promise.resolve().then(() => entry.reader.cancel('Y301-cleanup')).then(
          () => { entry.cancelled = true; cancelledReaders++; },
          error => { failures.push('reader cancel: ' + String(error).slice(0, 1000)); },
        ));
      }
      for (const state of streams.values()) {
        if (!state.stream.locked) {
          cancellations.push(Promise.resolve().then(() => state.stream.cancel('Y301-cleanup')).then(
            () => { state.cancelled = true; cancelledUnlockedStreams++; },
            error => { failures.push('stream cancel: ' + String(error).slice(0, 1000)); },
          ));
        }
      }
      // All held-reader and unlocked-sibling cancellations start before any
      // await, so a tee cancellation waiting on its sibling cannot deadlock.
      await Promise.allSettled(cancellations);
      let releasedReaders = 0;
      for (const entry of readers.values()) {
        try { entry.reader.releaseLock(); entry.released = true; releasedReaders++; }
        catch (error) { failures.push('reader release: ' + String(error).slice(0, 1000)); }
        if (entry.stream.stream.locked) failures.push('explicit branch reader remains locked');
      }
      function terminalProof(state, seen = new Set()) {
        if (state.cancelled) return 'awaited-stream-cancellation';
        if (state.reader && state.reader.released) {
          if (state.reader.reads.some(read => read.status === 'fulfilled' && read.done)) return 'awaited-EOF-and-released-reader';
          if (state.reader.cancelled) return 'awaited-reader-cancellation-and-release';
        }
        if (seen.has(state)) return null;
        seen.add(state);
        if (state.children.length === 2 && state.children.every(child => terminalProof(child, new Set(seen)))) {
          return 'both-local-clone-descendants-settled';
        }
        return null;
      }
      const streamReceipts = [];
      const retainedRuntimeLocks = [];
      for (const state of streams.values()) {
        const proof = terminalProof(state);
        const receipt = { id: state.id, locked: state.stream.locked, proof, descendants: state.children.map(child => child.id) };
        streamReceipts.push(receipt);
        if (!proof) failures.push('unverified terminal stream: ' + state.id);
        if (state.stream.locked) retainedRuntimeLocks.push(receipt);
      }
      const readerReceipts = [...readers.values()].map(entry => ({ stream: entry.stream.id, reads: entry.reads, cancelled: entry.cancelled, released: entry.released }));
      return {
        status: failures.length ? 'INCOMPLETE' : 'COMPLETE', scope: 'finite-local-stream-settlement',
        joinedReads: startedReads.length, joinedCancellations: cancellations.length,
        cancelledReaders, cancelledUnlockedStreams, releasedReaders, readerReceipts,
        streamReceipts, retainedRuntimeLocks, failures,
        externalOwnedTeardown: 'REQUIRED_FOR_ACCEPTANCE',
        outgoingRequests: 0, timers: 0, persistentWrites: 0, retainedCapabilities: 0,
      };
    },
  };
}

export default {
  async fetch(request) {
    const match = /^https?:\/\/[^/]+\/case\/(Y301)$/.exec(request.url);
    const id = match && match[1];
    if (request.method !== 'GET' || !id) {
      return Response.json({ profile: PROFILE, status: 'NOT_A_CASE' }, { status: 404 });
    }
    const test = context();
    let status = 'PASS';
    let error = null;
    try {
      await cases[id](test);
      if (test.assertions.length !== EXPECTED_ASSERTIONS) throw new Error('incomplete assertion trace');
    } catch (cause) {
      status = 'FAIL';
      error = { kind: cause.assertionFailure ? 'ASSERTION' : 'UNEXPECTED_EXCEPTION', message: String(cause.message || cause).slice(0, 1000) };
    }
    const cleanup = await test.cleanup();
    if (cleanup.status !== 'COMPLETE') status = 'FAIL';
    return Response.json({ profile: PROFILE, id, status, traceEntered: true, assertions: test.assertions, error, cleanup, runtimeWitness: 'Exact reviewed direct-celld source/build/deployment and external owned teardown required.' }, { status: status === 'PASS' ? 200 : 500 });
  },
};
