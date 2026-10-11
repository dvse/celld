import { CASES } from './cases.js';
const WAVE = 'pinned-os-git-codec-v1';
const MODULE_SHA256 = '56814f3f0608c88e6e83ba08e43f5af87ed4fabf972554e696c390809e9e1538';
let used = false;
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
class Assertions {
  constructor() { this.assertions = []; this.resources = []; this.operations = 0; this.cleanupNeedsExternal = false; }
  operation() { if (++this.operations > 64) throw new Error('64-operation envelope exceeded'); }
  ok(value, label) {
    if (this.assertions.length >= 64) throw new Error('64-assertion envelope exceeded');
    const satisfied = value === true; this.assertions.push({ label, satisfied });
    if (!satisfied) throw new Error('Assertion failed: ' + label);
  }
  same(actual, expected, label) { this.ok(Object.is(actual, expected), label); }
  eq(actual, expected, label) { this.ok(JSON.stringify(canonical(actual)) === JSON.stringify(canonical(expected)), label); }
  bytes(actual, expected, label) {
    let equal = actual instanceof Uint8Array && expected instanceof Uint8Array && actual.byteLength === expected.byteLength && actual.byteLength <= 70000;
    if (equal) for (let i = 0; i < expected.byteLength; i++) if (actual[i] !== expected[i]) { equal = false; break; }
    this.ok(equal, label);
  }
}
async function bounded(work, ms) {
  let timer;
  try { return await Promise.race([work, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Finite fixture deadline exceeded')), ms); })]); }
  finally { clearTimeout(timer); }
}
export default {
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === '/manifest') return Response.json({ wave: WAVE, ids: Object.keys(CASES), sourceOnlyStatus: 'NOT_RUN', importedModuleSha256: MODULE_SHA256 });
    const match = /^\/case\/(X20[1-6])$/.exec(path);
    if (request.method !== 'GET' || !match) return new Response('Use exact GET /case/<manifest-id>.', { status: 404 });
    if (used) return Response.json({ fixtureStatus: 'BLOCKED_PRECONDITION', reason: 'One case per fresh owned deployment/process is required.' }, { status: 409 });
    used = true;
    const t = new Assertions(), started = Date.now(); let settled = false;
    const result = { wave: WAVE, id: match[1], importedModuleSha256: MODULE_SHA256, assertions: t.assertions, fixtureStatus: 'BLOCKED_PRECONDITION', runtimeQualification: 'Requires separate exact direct-celld runtime/bundle/dependency identity and full owned teardown evidence.' };
    try {
      if (typeof crypto.subtle?.digest !== 'function' || typeof crypto.DigestStream !== 'function' || typeof Symbol.dispose !== 'symbol' || typeof ''.isWellFormed !== 'function') throw new Error('Required genuine runtime globals missing');
      const work = Promise.resolve().then(() => CASES[match[1]](t)).then(() => { settled = true; }, error => { settled = true; throw error; });
      result.fixtureStatus = 'TRACE_ENTERED';
      await bounded(work, 5000);
      if (!t.assertions.length) throw new Error('No assertions ran');
      result.fixtureStatus = 'ASSERTIONS_SATISFIED';
    } catch (error) {
      if (result.fixtureStatus === 'TRACE_ENTERED') result.fixtureStatus = settled ? 'ASSERTION_OR_API_FAILURE' : 'BLOCKED_UNSETTLED_TRACE';
      result.error = String(error).slice(0, 1024);
    }
    result.traceSettled = settled; result.operations = t.operations; result.sources = t.resources; result.wallMs = Date.now() - started;
    result.cleanup = { observedSourcesTerminal: settled && t.resources.every(r => r.completed), externalOwnedProcessReapRequired: true,
      note: 'Production PackReader privately owns the BYOB reader/digest. Generator return invokes its dispose/cancel. Lock/native reclamation and timeout cleanup require external proven-owned process teardown; no successful response proves cleanup.' };
    if (t.cleanupNeedsExternal && result.fixtureStatus === 'ASSERTIONS_SATISFIED') result.fixtureStatus = 'BLOCKED_CLEANUP';
    const text = JSON.stringify(result);
    if (new TextEncoder().encode(text).byteLength > 16384) return new Response('Fixture response envelope exceeded', { status: 500 });
    return new Response(text, { status: result.fixtureStatus === 'ASSERTIONS_SATISFIED' ? 200 : 500, headers: { 'content-type': 'application/json' } });
  },
};
