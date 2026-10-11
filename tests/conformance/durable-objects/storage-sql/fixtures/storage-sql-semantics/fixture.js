import { CASES } from './cases.js';
const WAVE = 'ordinary-do-storage-sql-v1';
class Assertions {
  constructor() { this.assertions = []; this.cursors = []; }
  ok(value, label) { const satisfied = value === true; this.assertions.push({ label, satisfied }); if (!satisfied) throw new Error('Assertion failed: ' + label); }
  eq(actual, expected, label) { this.ok(JSON.stringify(actual) === JSON.stringify(expected), label); }
  same(actual, expected, label) { this.ok(Object.is(actual, expected), label); }
  cursor(value) { this.cursors.push(value); return value; }
}
function instrument(storage, t) {
  // Only records native cursor handles for cleanup; every operation delegates to
  // the actual public runtime object. No replacement implementation or oracle.
  const native = storage.sql;
  const sql = {
    exec(...args) { return t.cursor(native.exec(...args)); },
    prepare(query) { const statement = native.prepare(query); return (...binds) => t.cursor(statement(...binds)); },
    ingest(input) { return native.ingest(input); },
  };
  return {
    sql, kv: storage.kv,
    get: storage.get.bind(storage), put: storage.put.bind(storage),
    delete: storage.delete.bind(storage), list: storage.list.bind(storage),
    deleteAll: storage.deleteAll.bind(storage), transactionSync: storage.transactionSync.bind(storage),
  };
}
async function bounded(work, ms) {
  let timer;
  try { return await Promise.race([work, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('finite fixture deadline exceeded')), ms); })]); }
  finally { clearTimeout(timer); }
}
export class StorageCase {
  constructor(state) { this.state = state; this.used = false; this.activation = crypto.randomUUID(); }
  async fetch(request) {
    const id = new URL(request.url).pathname.split('/').pop();
    if (this.used || !Object.hasOwn(CASES, id)) return Response.json({ fixtureStatus: 'BLOCKED_PRECONDITION', reason: 'One valid case per fresh object activation is required.' }, { status: 409 });
    this.used = true;
    const t = new Assertions(), started = Date.now(), storage = this.state.storage;
    const result = { wave: WAVE, id, objectId: this.state.id.toString(), activation: this.activation, assertions: t.assertions, fixtureStatus: 'BLOCKED_PRECONDITION', runtimeQualification: 'requires independent direct-celld executable, source, fresh-root and owned teardown witnesses' };
    let traceSettled = false;
    try {
      if (typeof storage.kv?.get !== 'function' || typeof storage.sql?.ingest !== 'function') throw new Error('Required public storage APIs absent');
      if ((await bounded(storage.list({ limit: 1 }), 1000)).size !== 0) throw new Error('Fresh case object has preexisting KV');
      const owned = instrument(storage, t);
      const work = Promise.resolve().then(() => CASES[id](owned, t)).then(() => { traceSettled = true; }, error => { traceSettled = true; throw error; });
      result.fixtureStatus = 'TRACE_ENTERED';
      await bounded(work, 5000);
      if (t.assertions.length === 0) throw new Error('No assertions ran');
      result.fixtureStatus = 'ASSERTIONS_SATISFIED';
    } catch (error) {
      if (result.fixtureStatus === 'TRACE_ENTERED') result.fixtureStatus = traceSettled ? 'ASSERTION_OR_API_FAILURE' : 'BLOCKED_UNSETTLED_TRACE';
      result.error = String(error);
    }
    if (traceSettled) {
      try {
        result.cleanup = await bounded((async () => {
          let drained = 0;
          for (const cursor of t.cursors) {
            let done = false;
            for (let step = 0; step < 65; step++) { if (cursor.next().done) { done = true; break; } drained++; }
            if (!done) throw new Error('A cursor exceeded the 64-row cleanup envelope');
          }
          await storage.deleteAll();
          if ((await storage.list({ limit: 1 })).size !== 0) throw new Error('Owned KV not empty after cleanup');
          return { status: 'COMPLETE', trackedCursors: t.cursors.length, remainingRowsDrained: drained, ownedKvEmpty: true };
        })(), 2000);
      } catch (error) { result.fixtureStatus = 'BLOCKED_CLEANUP'; result.cleanupError = String(error); }
    } else { result.cleanup = { status: 'EXTERNAL_REAP_REQUIRED', reason: 'No teardown may race an unsettled or unentered trace.' }; }
    result.traceSettled = traceSettled; result.wallMs = Date.now() - started;
    return Response.json(result, { status: result.fixtureStatus === 'ASSERTIONS_SATISFIED' ? 200 : 500 });
  }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/manifest') return Response.json({ wave: WAVE, ids: Object.keys(CASES), sourceOnlyStatus: 'NOT_RUN' });
    const match = /^\/case\/(D2\d\d)$/.exec(path);
    if (request.method !== 'GET' || !match || !Object.hasOwn(CASES, match[1])) return new Response('Use exact GET /case/<manifest-id>.', { status: 404 });
    const rootName = WAVE + ':' + match[1] + ':' + crypto.randomUUID();
    const id = env.CASE.idFromName(rootName), stub = env.CASE.get(id);
    // This is one ordinary same-deployment DO.fetch, not a public internet fetch.
    const response = await stub.fetch(new Request('https://owned.fixture.invalid/case/' + match[1]));
    const body = await response.json(); body.rootName = rootName; body.expectedObjectId = id.toString();
    if (body.objectId !== id.toString()) return Response.json({ fixtureStatus: 'BLOCKED_IDENTITY', body }, { status: 500 });
    return Response.json(body, { status: response.status });
  },
};
