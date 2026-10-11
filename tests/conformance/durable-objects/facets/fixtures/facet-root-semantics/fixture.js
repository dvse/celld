import { DurableObject } from 'cloudflare:workers';
import { CASES } from './cases.js';
import { localModuleToken } from './facets.js';
import { LOADED_SOURCE } from './sources.js';
export { Facet, Leaf } from './facets.js';
const WAVE = 'ordinary-facet-root-v1';
class Assertions {
  constructor() { this.records = []; }
  ok(condition, label) { const satisfied = condition === true; this.records.push({ label, satisfied }); if (!satisfied) throw new Error('Assertion failed: ' + label); }
  same(actual, expected, label) { this.ok(Object.is(actual, expected), label); }
  deep(actual, expected, label) { this.ok(JSON.stringify(actual) === JSON.stringify(expected), label); }
}
async function bounded(work, milliseconds) {
  let timer;
  try { return await Promise.race([work, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('finite fixture deadline exceeded')), milliseconds); })]); }
  finally { clearTimeout(timer); }
}
export class CleanupProbe extends DurableObject {
  async empty() {
    const entries = await this.ctx.storage.list({ limit: 1 });
    const tables = this.ctx.storage.sql.exec("SELECT name FROM sqlite_schema WHERE type='table' AND name='shared'").toArray();
    return { kvEmpty: entries.size === 0, applicationTableAbsent: tables.length === 0 };
  }
}
export class Root extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.used = false; this.activation = crypto.randomUUID(); }
  async fetch(request) {
    const id = new URL(request.url).pathname.split('/').pop();
    if (this.used || !Object.hasOwn(CASES, id)) return Response.json({ fixtureStatus: 'BLOCKED_PRECONDITION', error: 'One exact case per fresh root activation is required.' }, { status: 409 });
    this.used = true;
    const t = new Assertions(), names = new Set(), workers = [];
    const started = Date.now();
    const scope = {
      ctx: this.ctx, env: this.env, localToken: localModuleToken(),
      custom: (name, start) => { names.add(name); return this.ctx.facets.get(name, start); },
      local: (name, props = {}, visibleId) => {
        names.add(name);
        return this.ctx.facets.get(name, () => ({ class: this.ctx.exports.Facet({ props }), ...(visibleId === undefined ? {} : { id: visibleId }) }));
      },
      loaded: (name, className, props) => {
        const worker = this.env.LOADER.load({ compatibilityDate: '2026-09-04', compatibilityFlags: ['js_rpc'], mainModule: 'loaded.js', modules: { 'loaded.js': LOADED_SOURCE }, env: { ORIGIN: 'loaded-origin' }, globalOutbound: null });
        workers.push(worker);
        const cls = worker.getDurableObjectClass(className, { props });
        names.add(name);
        return this.ctx.facets.get(name, () => ({ class: cls }));
      },
    };
    const result = { wave: WAVE, id, objectId: String(this.ctx.id), objectName: this.ctx.id.name, activation: this.activation, assertions: t.records, fixtureStatus: 'BLOCKED_PRECONDITION', runtimeQualification: 'direct-celld component only; independent process, source, ownership, fresh-store and teardown witnesses required; actual OS unverified' };
    let traceSettled = false;
    try {
      if (typeof this.ctx.facets?.get !== 'function' || typeof this.ctx.storage.kv?.put !== 'function' || typeof this.env.LOADER?.load !== 'function') throw new Error('Required public facet/storage/loader APIs absent');
      if ((await bounded(this.ctx.storage.list({ limit: 1 }), 1000)).size !== 0) throw new Error('Preexisting root storage');
      result.fixtureStatus = 'TRACE_ENTERED';
      const trace = Promise.resolve().then(() => CASES[id](scope, t)).then(() => { traceSettled = true; }, error => { traceSettled = true; throw error; });
      await bounded(trace, 6000);
      if (!t.records.length) throw new Error('No fixed assertions ran');
      result.fixtureStatus = 'ASSERTIONS_SATISFIED';
    } catch (error) {
      if (result.fixtureStatus === 'TRACE_ENTERED') result.fixtureStatus = traceSettled ? 'ASSERTION_OR_API_FAILURE' : 'BLOCKED_UNSETTLED_TRACE';
      result.error = String(error);
    }
    if (traceSettled) {
      try {
        result.cleanup = await bounded((async () => {
          for (const name of names) {
            // Public delete has no completion result. A fresh same-name call
            // crosses its public startup barrier before cleanup is witnessed.
            this.ctx.facets.delete(name);
            const probe = this.ctx.facets.get(name, () => ({ class: this.ctx.exports.CleanupProbe }));
            const empty = await probe.empty();
            if (!empty.kvEmpty || !empty.applicationTableAbsent) throw new Error('Owned facet data remains after public deletion: ' + name);
          }
          for (const worker of workers) worker.dispose();
          await this.ctx.storage.deleteAll();
          if ((await this.ctx.storage.list({ limit: 1 })).size !== 0) throw new Error('Owned root KV remains after cleanup');
          if (this.ctx.storage.sql.exec("SELECT name FROM sqlite_schema WHERE type='table' AND name='shared'").toArray().length !== 0) throw new Error('Owned root application table remains after cleanup');
          return { status: 'COMPLETE', rootKvEmpty: true, rootApplicationTableAbsent: true, deletedTopLevelSubtrees: names.size, releasedLoadedWorkers: workers.length, residualEmptyProbeFacets: names.size, externalOwnedProcessAndStoreTeardownRequired: true };
        })(), 3000);
      } catch (error) { result.fixtureStatus = 'BLOCKED_CLEANUP'; result.cleanupError = String(error); result.cleanup = { status: 'EXTERNAL_REAP_REQUIRED' }; }
    } else { result.cleanup = { status: 'EXTERNAL_REAP_REQUIRED', reason: 'Never race cleanup against an unentered or unsettled trace.' }; }
    result.traceSettled = traceSettled;
    result.wallMs = Date.now() - started;
    return Response.json(result, { status: result.fixtureStatus === 'ASSERTIONS_SATISFIED' ? 200 : 500 });
  }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/manifest') return Response.json({ wave: WAVE, ids: Object.keys(CASES), sourceOnlyStatus: 'UNRUN' });
    const match = /^\/case\/(Z2\d\d)$/.exec(path);
    if (request.method !== 'GET' || !match || !Object.hasOwn(CASES, match[1])) return new Response('Use exact GET /case/<manifest-id>.', { status: 404 });
    const rootName = WAVE + ':' + match[1] + ':' + crypto.randomUUID();
    const id = env.ROOT.idFromName(rootName);
    const response = await env.ROOT.get(id).fetch('https://owned.fixture.invalid/case/' + match[1]);
    const body = await response.json();
    body.rootName = rootName; body.expectedObjectId = String(id);
    if (body.objectId !== String(id) || body.objectName !== rootName) return Response.json({ fixtureStatus: 'BLOCKED_IDENTITY', body }, { status: 500 });
    return Response.json(body, { status: response.status });
  },
};
