import { cases } from './cases.js';

const PROFILE = 'direct-celld-url-semantics-v1';

function recorder() {
  const assertions = [];
  function record(label, actual, expected, passed) {
    const entry = { label, actual, expected, passed };
    // JSON has no undefined value; preserve that distinction in receipts.
    if (actual === undefined) entry.actual = { type: 'undefined' };
    if (expected === undefined) entry.expected = { type: 'undefined' };
    assertions.push(entry);
    if (!passed) {
      const error = new Error(label);
      error.assertionFailure = true;
      throw error;
    }
  }
  return {
    assertions,
    equal(actual, expected, label) { record(label, actual, expected, Object.is(actual, expected)); },
    deep(actual, expected, label) { record(label, actual, expected, JSON.stringify(actual) === JSON.stringify(expected)); },
  };
}

export default {
  fetch(request) {
    // Route without the URL API under test. No parameterized trace or alternate entrypoint.
    const match = /^https?:\/\/[^/]+\/case\/(U2[0-9]{2})$/.exec(request.url);
    const id = match && match[1];
    if (request.method !== 'GET' || !id || !Object.prototype.hasOwnProperty.call(cases, id)) {
      return Response.json({ profile: PROFILE, status: 'NOT_A_CASE' }, { status: 404 });
    }
    const test = recorder();
    let status = 'PASS';
    let error = null;
    try {
      cases[id](test);
      if (!test.assertions.length) throw new Error('empty assertion trace');
    } catch (cause) {
      status = 'FAIL';
      error = { kind: cause.assertionFailure ? 'ASSERTION' : 'UNEXPECTED_EXCEPTION', message: String(cause.message || cause) };
    }
    return Response.json({
      profile: PROFILE,
      id,
      status,
      traceEntered: true,
      assertions: test.assertions,
      error,
      cleanup: { status: 'COMPLETE', persistentWrites: 0, outgoingRequests: 0, timers: 0, retainedHandles: 0 },
      runtimeWitness: 'External supervisor must attest direct celld, source/build/deployment pins and owned resource bounds.',
    }, { status: status === 'PASS' ? 200 : 500 });
  },
};
