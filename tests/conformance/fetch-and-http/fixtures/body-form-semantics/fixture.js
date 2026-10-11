import { cases } from './cases.js';

const PROFILE = 'direct-celld-body-form-semantics-v1';

function context() {
  const assertions = [];
  const streams = new Map();
  const bodies = new Set();
  const readers = new Set();
  function trackStream(stream) {
    if (stream !== null && !streams.has(stream)) {
      streams.set(stream, { id: 'stream-' + (streams.size + 1), stream, consumers: [], children: [], cancelled: false });
    }
    return stream;
  }
  function trackBody(owner) {
    bodies.add(owner);
    trackStream(owner.body);
    return owner;
  }
  function record(actual, expected, label, passed) {
    assertions.push({ label, actual, expected, passed });
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
    body: trackBody,
    stream: trackStream,
    reader(value) { readers.add(value); return value; },
    clone(owner) {
      trackBody(owner);
      const before = owner.body;
      const copy = owner.clone(); // Call the real public runtime API once.
      trackBody(owner);
      trackBody(copy);
      if (before !== null && before !== owner.body) {
        streams.get(before).children = [owner.body, copy.body].map(stream => streams.get(stream));
      }
      return copy;
    },
    requestFrom(owner, init) {
      trackBody(owner);
      const before = owner.body;
      const request = new Request(owner, init); // Real constructor; no emulation.
      trackBody(request);
      if (before !== null && (!init || !Object.prototype.hasOwnProperty.call(init, 'body')) && before !== request.body) {
        streams.get(before).children = [streams.get(request.body)];
      }
      return request;
    },
    async consume(owner, method) {
      if (!['text', 'formData', 'arrayBuffer', 'blob'].includes(method)) throw new Error('unknown fixture consumer');
      trackBody(owner);
      const state = { method, outcome: 'pending' };
      if (owner.body !== null) streams.get(owner.body).consumers.push(state);
      try {
        const value = await owner[method](); // The subject's method, never a shim.
        state.outcome = 'fulfilled';
        return value;
      } catch (error) {
        state.outcome = 'rejected';
        throw error;
      }
    },
    boundary(contentType) {
      const match = /^multipart\/form-data;\s*boundary=(?:"([^\"]+)"|([^;\s]+))$/i.exec(contentType || '');
      if (!match) throw new Error('multipart media type must contain one boundary');
      const boundary = match[1] || match[2];
      if (boundary.length > 200) throw new Error('fixture boundary budget exceeded');
      return boundary;
    },
    multipartTextParts(wire, boundary) {
      // An independent, deliberately tiny oracle for these ASCII field names.
      // RFC 2046 allows the closing delimiter with or without final CRLF;
      // header name casing is not a serialization requirement either.
      if (wire.length > 16384) throw new Error('fixture multipart oracle budget exceeded');
      const start = '--' + boundary + '\r\n';
      const end = '\r\n--' + boundary + '--';
      const text = wire.endsWith('\r\n') ? wire.slice(0, -2) : wire;
      if (!text.startsWith(start) || !text.endsWith(end)) throw new Error('multipart opening and closing framing mismatch');
      const parts = text.slice(start.length, -end.length).split('\r\n--' + boundary + '\r\n');
      if (parts.length > 8) throw new Error('fixture multipart part-count budget exceeded');
      return parts.map(part => {
        const split = part.indexOf('\r\n\r\n');
        if (split < 0) throw new Error('multipart header/body separator missing');
        const headers = part.slice(0, split).split('\r\n');
        const dispositions = headers.filter(line => /^content-disposition:/i.test(line));
        if (dispositions.length !== 1 || headers.some(line => /^content-type:/i.test(line))) throw new Error('ordinary text form part header mismatch');
        const name = /^content-disposition:[ \t]*form-data[ \t]*;[ \t]*name="([A-Za-z]+)"[ \t]*$/i.exec(dispositions[0]);
        if (!name) throw new Error('fixture form field name framing mismatch');
        return [name[1], part.slice(split + 4)];
      });
    },
    async readAll(reader, prefix) {
      const bytes = prefix ? [...prefix] : [];
      for (let i = 0; i < 16; i++) {
        const next = await reader.read();
        if (next.done) return bytes;
        for (const byte of next.value) bytes.push(byte);
        if (bytes.length > 16384) throw new Error('fixture byte budget exceeded');
      }
      throw new Error('fixture read-count budget exceeded');
    },
    async cleanup() {
      const failures = [];
      let releasedReaders = 0;
      let cancelledUnlockedStreams = 0;
      for (const body of bodies) trackStream(body.body);
      for (const reader of readers) {
        try { await reader.cancel('fixture-cleanup'); } catch (error) { failures.push(String(error)); }
        try { reader.releaseLock(); releasedReaders++; } catch (error) { failures.push(String(error)); }
      }
      const streamCancellations = [];
      for (const state of streams.values()) {
        const stream = state.stream;
        // Buffered body sources can be lazy. Cancel every unlocked source.
        // Locked runtime readers are classified below using witnessed consumer
        // outcomes and explicit clone/proxy branch lineage, never bodyUsed alone.
        if (!stream.locked) {
          // Initiate all cancellations before joining: tee cancellation can wait
          // for its sibling, so sequential awaits could deadlock cleanup.
          streamCancellations.push(Promise.resolve().then(() => stream.cancel('fixture-cleanup')).then(
            () => { cancelledUnlockedStreams++; state.cancelled = true; },
            error => { failures.push(String(error)); },
          ));
        }
      }
      await Promise.all(streamCancellations);
      function terminalProof(state, seen = new Set()) {
        if (state.cancelled) return 'awaited-stream-cancellation';
        if (state.consumers.some(consumer => consumer.outcome === 'fulfilled')) return 'awaited-full-body-consumer';
        if (seen.has(state)) return null;
        seen.add(state);
        if (state.children.length && state.children.every(child => terminalProof(child, new Set(seen)))) return 'all-clone-or-proxy-descendants-settled';
        return null;
      }
      const retainedRuntimeLocks = [];
      for (const state of streams.values()) {
        if (state.stream.locked) {
          const proof = terminalProof(state);
          retainedRuntimeLocks.push({ id: state.id, proof, consumers: state.consumers, descendants: state.children.map(child => child.id) });
          if (proof === null) failures.push('Unverified locked stream: ' + state.id);
        }
      }
      return { status: failures.length ? 'INCOMPLETE' : 'COMPLETE', scope: 'local-resource-settlement', releasedReaders, cancelledUnlockedStreams, retainedRuntimeLocks, externalOwnedTeardown: 'REQUIRED_FOR_ACCEPTANCE', failures, outgoingRequests: 0, timers: 0, persistentWrites: 0, retainedCapabilities: 0 };
    },
  };
}

export default {
  async fetch(request) {
    const match = /^https?:\/\/[^/]+\/case\/(Y2[0-9]{2})$/.exec(request.url);
    const id = match && match[1];
    if (request.method !== 'GET' || !id || !Object.prototype.hasOwnProperty.call(cases, id)) {
      return Response.json({ profile: PROFILE, status: 'NOT_A_CASE' }, { status: 404 });
    }
    const test = context();
    let status = 'PASS';
    let error = null;
    try {
      await cases[id](test);
      if (!test.assertions.length) throw new Error('empty assertion trace');
    } catch (cause) {
      status = 'FAIL';
      error = { kind: cause.assertionFailure ? 'ASSERTION' : 'UNEXPECTED_EXCEPTION', message: String(cause.message || cause) };
    }
    const cleanup = await test.cleanup();
    if (cleanup.status !== 'COMPLETE') status = 'FAIL';
    return Response.json({ profile: PROFILE, id, status, traceEntered: true, assertions: test.assertions, error, cleanup, runtimeWitness: 'External direct-celld source/build/deployment and bounded-process witnesses required.' }, { status: status === 'PASS' ? 200 : 500 });
  },
};
