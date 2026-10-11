import { CASES } from './cases.js';
const WAVE = 'pinned-os-action-files-v1';
const MODULE_SHA256 = 'e735cdd41333be3297a6e8d7114553483772b33f310edfb0844296650c855da0';
function canonical(value) {
  if (value instanceof Uint8Array) return { byteType: "Uint8Array", data: [...value] };
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}
class Assertions {
  constructor() { this.assertions = []; this.observations = []; }
  witness(value, label) { if (value !== true) { const error = new Error(label); error.name = "BlockedWitness"; throw error; } }
  ok(value, label) { const satisfied = value === true; this.assertions.push({ label, satisfied }); if (!satisfied) throw new Error('Assertion failed: ' + label); }
  eq(actual, expected, label) { this.ok(JSON.stringify(canonical(actual)) === JSON.stringify(canonical(expected)), label); }
  same(actual, expected, label) { this.ok(Object.is(actual, expected), label); }
  rows(iterable) {
    const iterator = iterable[Symbol.iterator](), result = [];
    try {
      for (let i = 0; i <= 64; i++) {
        const step = iterator.next();
        if (step.done) return result;
        if (i === 64) throw new Error('Read exceeds the fixed 64-row envelope');
        result.push(step.value);
      }
    } finally { if (typeof iterator.return === 'function') iterator.return(); }
    throw new Error('Unreachable bounded iterator state');
  }
}
async function bounded(work, ms) {
  let timer;
  try { return await Promise.race([work, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('Finite fixture deadline exceeded')), ms); })]); }
  finally { clearTimeout(timer); }
}
export class ActionFileCase {
  constructor(state) { this.state = state; this.used = false; this.activation = crypto.randomUUID(); }
  async fetch(request) {
    const id = new URL(request.url).pathname.split('/').pop();
    if (this.used || !Object.hasOwn(CASES, id)) return Response.json({ fixtureStatus: 'BLOCKED_PRECONDITION', reason: 'One exact case per fresh object activation is required.' }, { status: 409 });
    this.used = true;
    const t = new Assertions(), started = Date.now(), storage = this.state.storage;
    const result = { wave: WAVE, id, importedModuleSha256: MODULE_SHA256, objectId: this.state.id.toString(), activation: this.activation, assertions: t.assertions, observations: t.observations, fixtureStatus: 'BLOCKED_PRECONDITION', runtimeQualification: 'requires independent direct-celld executable, OS-module/bundle identity, fresh-root and owned teardown witnesses' };
    let traceSettled = false;
    try {
      if (typeof storage.kv?.list !== 'function' || typeof storage.transactionSync !== 'function' || typeof crypto.subtle?.digest !== 'function' || typeof crypto.randomUUID !== 'function') throw new Error('Required native synchronous storage APIs absent');
      if ((await bounded(storage.list({ limit: 1 }), 1000)).size !== 0) throw new Error('Fresh case object has preexisting KV');
      // Pass the genuine runtime storage object directly, without a storage
      // implementation, mocked collection, altered module, or interception layer.
      const work = Promise.resolve().then(() => CASES[id](storage, t)).then(() => { traceSettled = true; }, error => { traceSettled = true; throw error; });
      result.fixtureStatus = 'TRACE_ENTERED';
      await bounded(work, 5000);
      if (t.assertions.length === 0) throw new Error('No assertions ran');
      result.fixtureStatus = 'ASSERTIONS_SATISFIED';
    } catch (error) {
      if (result.fixtureStatus === 'TRACE_ENTERED') result.fixtureStatus = traceSettled ? (error?.name === 'BlockedWitness' ? 'BLOCKED_WITNESS' : 'ASSERTION_OR_API_FAILURE') : 'BLOCKED_UNSETTLED_TRACE';
      result.error = String(error);
    }
    if (traceSettled) {
      try {
        result.cleanup = await bounded((async () => {
          // Opening one new public KV iterator closes any prior native sync-list
          // cursor for this storage scope (pinned storage.rs:3853-3862). Fully
          // consume it before deleteAll; do not call next again after done.
          const ownedRows = t.rows(storage.kv.list());
          await storage.deleteAll();
          if ((await storage.list({ limit: 1 })).size !== 0) throw new Error('Owned KV not empty after cleanup');
          return { status: 'COMPLETE', ownedRowsBeforeDelete: ownedRows.length, ownedKvEmpty: true };
        })(), 2000);
      } catch (error) { result.fixtureStatus = 'BLOCKED_CLEANUP'; result.cleanupError = String(error); }
    } else { result.cleanup = { status: 'EXTERNAL_REAP_REQUIRED', reason: 'No teardown may race an unsettled or unentered trace.' }; }
    result.traceSettled = traceSettled; result.wallMs = Date.now() - started;
    // Receipts carry booleans/labels and at most one small timestamp record.
    // Never echo captured bytes, complete native rows, or large expected values.
    const text = JSON.stringify(result);
    if (new TextEncoder().encode(text).byteLength > 32768) return Response.json({ fixtureStatus: 'BLOCKED_RECEIPT_LIMIT', id }, { status: 500 });
    return new Response(text, { status: result.fixtureStatus === 'ASSERTIONS_SATISFIED' ? 200 : 500, headers: { 'content-type': 'application/json' } });
  }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/manifest') return Response.json({ wave: WAVE, ids: Object.keys(CASES), sourceOnlyStatus: 'NOT_RUN', importedModuleSha256: MODULE_SHA256 });
    const match = /^\/case\/(F20[1-6])$/.exec(path);
    if (request.method !== 'GET' || !match || !Object.hasOwn(CASES, match[1])) return new Response('Use exact GET /case/<manifest-id>.', { status: 404 });
    const rootName = WAVE + ':' + match[1] + ':' + crypto.randomUUID();
    const id = env.CASE.idFromName(rootName), stub = env.CASE.get(id);
    const response = await stub.fetch(new Request('https://owned.fixture.invalid/case/' + match[1]));
    const body = await response.json(); body.rootName = rootName; body.expectedObjectId = id.toString();
    if (body.objectId !== id.toString()) return Response.json({ fixtureStatus: 'BLOCKED_IDENTITY', body }, { status: 500 });
    const receipt = JSON.stringify(body);
    if (new TextEncoder().encode(receipt).byteLength > 32768) return Response.json({ fixtureStatus: 'BLOCKED_RECEIPT_LIMIT', id: match[1] }, { status: 500 });
    return new Response(receipt, { status: response.status, headers: { 'content-type': 'application/json' } });
  },
};
