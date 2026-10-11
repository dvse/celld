import { CASES } from './cases.js';

const WAVE = 'headers-cache-semantics-v1';
const TRACE_MS = 2000;
const CLEANUP_MS = 1000;
class Assertions {
  constructor() { this.assertions = []; this.bodies = []; }
  record(ok, label) {
    this.assertions.push({ label, satisfied: ok });
    if (!ok) throw new Error('Assertion failed: ' + label);
  }
  eq(actual, expected, label) { this.record(JSON.stringify(actual) === JSON.stringify(expected), label); }
  same(actual, expected, label) { this.record(Object.is(actual, expected), label); }
  done(result, label) { this.record(result.done === true && result.value === undefined, label); }
  trackBody(response, closed = null) { this.bodies.push({ response, closed }); }
  async cleanup() {
    const out = [];
    for (const { response, closed } of this.bodies) {
      if (!response.body) { out.push('bodyless'); continue; }
      if (!response.body.locked) {
        await response.body.cancel('owned finite case cleanup');
        out.push('unlocked-body-cancelled');
      } else if (closed && closed()) {
        out.push('finite-source-closed-reader-owned-by-runtime');
      } else {
        throw new Error('A tracked body remains locked without a finite-source closure witness');
      }
    }
    return out;
  }
}
async function bounded(work, ms) {
  let timer;
  try {
    return await Promise.race([work, new Promise((_, reject) => {
      timer = setTimeout(() => reject(new Error('finite fixture deadline exceeded')), ms);
    })]);
  } finally { clearTimeout(timer); }
}
export default {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === '/manifest') return Response.json({ wave: WAVE, ids: Object.keys(CASES), sourceOnlyStatus: 'NOT_RUN', transport: 'direct-celld-worker' });
    const match = /^\/case\/(V2\d\d)$/.exec(path);
    if (request.method !== 'GET' || !match || !Object.hasOwn(CASES, match[1])) return new Response('Use an exact GET /case/<manifest-id>.', { status: 404 });
    const id = match[1], t = new Assertions(), started = Date.now();
    const result = { wave: WAVE, id, fixtureStatus: 'BLOCKED', assertions: t.assertions, runtimeQualification: 'requires independent direct-celld source, process and teardown witnesses' };
    if (typeof Headers !== 'function' || typeof Response !== 'function' || typeof ReadableStream !== 'function' || typeof globalThis.caches?.default?.put !== 'function') {
      result.error = 'Required direct runtime API is absent'; return Response.json(result, { status: 503 });
    }
    let traceSettled = false;
    const work = Promise.resolve().then(() => CASES[id](t)).then(() => { traceSettled = true; }, error => { traceSettled = true; throw error; });
    try {
      await bounded(work, TRACE_MS);
      if (t.assertions.length === 0) throw new Error('Case executed no assertions');
      result.fixtureStatus = 'ASSERTIONS_SATISFIED';
    } catch (error) {
      result.fixtureStatus = traceSettled ? 'ASSERTION_OR_API_FAILURE' : 'BLOCKED_UNSETTLED_TRACE';
      result.error = String(error);
    }
    try { result.cleanup = await bounded(t.cleanup(), CLEANUP_MS); }
    catch (error) { result.fixtureStatus = 'BLOCKED_CLEANUP'; result.cleanupError = String(error); }
    result.traceSettled = traceSettled;
    result.wallMs = Date.now() - started;
    return Response.json(result, { status: result.fixtureStatus === 'ASSERTIONS_SATISFIED' ? 200 : 500 });
  },
};
