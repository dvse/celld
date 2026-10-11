import { CASES } from './cases.js';
const WAVE = 'ordinary-r2-semantics-v1';
function equal(a, b, depth = 0) {
  if (Object.is(a, b)) return true;
  if (depth > 8 || a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const ak = Object.keys(a).sort(), bk = Object.keys(b).sort();
  return ak.length === bk.length && ak.every((key, i) => key === bk[i] && equal(a[key], b[key], depth + 1));
}
class Lab {
  constructor(env, id) {
    this.env = env; this.id = id; this.prefix = WAVE + '/' + id + '/' + crypto.randomUUID() + '/';
    this.assertions = []; this.calls = 0; this.keys = { A: new Set(), B: new Set() };
    this.bodies = new Map(); this.inputs = []; this.uploads = new Map();
  }
  ok(value, label) { const satisfied = value === true; this.assertions.push({ label, satisfied }); if (!satisfied) throw new Error('Assertion failed: ' + label); }
  eq(a, b, label) { this.ok(equal(a, b), label); }
  same(a, b, label) { this.ok(Object.is(a, b), label); }
  key(suffix) { return this.prefix + suffix; }
  touch(suffix, bucket = 'A') { const key = this.key(suffix); this.keys[bucket].add(key); return key; }
  async call(fn) { if (++this.calls > 80) throw new Error('Owned API call envelope exceeded'); return await fn(); }
  put(name, value, options = {}, bucket = 'A') { const key = this.touch(name, bucket); return this.call(() => this.env[bucket].put(key, value, options)); }
  head(name, bucket = 'A') { const key = this.touch(name, bucket); return this.call(() => this.env[bucket].head(key)); }
  async get(name, options = {}, bucket = 'A') { const key = this.touch(name, bucket); const object = await this.call(() => this.env[bucket].get(key, options)); if (object?.body) this.bodies.set(object, false); return object; }
  list(options, bucket = 'A') { if (!options.prefix?.startsWith(this.prefix)) throw new Error('List must remain in owned prefix'); return this.call(() => this.env[bucket].list(options)); }
  remove(names, bucket = 'A') { const keys = names.map(name => this.touch(name, bucket)); return this.call(() => this.env[bucket].delete(keys)); }
  async read(object, method) { if (!object?.body || !['text', 'arrayBuffer'].includes(method)) throw new Error('Expected readable owned R2 object'); const value = await this.call(() => object[method]()); this.markBodyClosed(object); return value; }
  markBodyClosed(object) { if (!this.bodies.has(object)) throw new Error('Unknown owned response body'); this.bodies.set(object, true); }
  trackInput(stream, closed) { this.inputs.push({ stream, closed }); }
  hex(buffer) { return [...new Uint8Array(buffer)].map(value => value.toString(16).padStart(2, '0')).join(''); }
  async multipart(name, options = {}) { const key = this.touch(name); const upload = await this.call(() => this.env.A.createMultipartUpload(key, options)); this.uploads.set(upload.uploadId, { upload, closed: false }); return upload; }
  resume(name, uploadId) { if (++this.calls > 80) throw new Error('Owned API call envelope exceeded'); const key = this.touch(name); const upload = this.env.A.resumeMultipartUpload(key, uploadId); if (!this.uploads.has(uploadId)) throw new Error('Resume must use this active request’s owned upload'); this.uploads.get(uploadId).upload = upload; return upload; }
  upload(upload, number, value) { return this.call(() => upload.uploadPart(number, value)); }
  async complete(upload, parts) { const object = await this.call(() => upload.complete(parts)); this.markUploadComplete(upload); return object; }
  markUploadComplete(upload) { const entry = this.uploads.get(upload.uploadId); if (!entry) throw new Error('Unknown owned multipart upload'); entry.closed = true; }
  async abort(upload) { await this.call(() => upload.abort()); this.markUploadComplete(upload); }
  async cleanup() {
    for (const [object, finished] of this.bodies) {
      if (finished) continue;
      if (object.body.locked) throw new Error('Unfinished body locked by native reader; external reap required');
      await object.body.cancel('owned case cleanup'); this.bodies.set(object, true);
    }
    for (const { stream, closed } of this.inputs) {
      if (closed()) continue;
      if (stream.locked) throw new Error('Input producer has no closure witness');
      await stream.cancel('owned case cleanup');
    }
    for (const entry of this.uploads.values()) if (!entry.closed) await this.abort(entry.upload);
    for (const bucket of ['A', 'B']) {
      const keys = [...this.keys[bucket]];
      if (keys.length) await this.call(() => this.env[bucket].delete(keys));
      const page = await this.list({ prefix: this.prefix, limit: 20 }, bucket);
      if (page.objects.length || page.delimitedPrefixes.length || page.truncated) throw new Error('Owned R2 prefix still contains objects');
    }
    return { status: 'COMPLETE', ownedPrefixesEmpty: true, responseBodiesFinished: this.bodies.size, uploadsClosed: [...this.uploads.values()].every(x => x.closed) };
  }
}
async function bounded(work, ms) {
  let timer;
  try { return await Promise.race([work, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('finite fixture deadline exceeded')), ms); })]); }
  finally { clearTimeout(timer); }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/manifest') return Response.json({ wave: WAVE, ids: Object.keys(CASES), sourceOnlyStatus: 'NOT_RUN', requires: 'direct celld with fresh owned fleet bucket and two private R2 bindings' });
    const match = /^\/case\/(I2\d\d)$/.exec(path);
    if (request.method !== 'GET' || !match || !Object.hasOwn(CASES, match[1])) return new Response('Use exact GET /case/<manifest-id>.', { status: 404 });
    const t = new Lab(env, match[1]), started = Date.now();
    const result = { wave: WAVE, id: match[1], prefix: t.prefix, fixtureStatus: 'BLOCKED_PRECONDITION', assertions: t.assertions, runtimeQualification: 'requires external direct-celld build, bucket, process and teardown evidence' };
    let traceSettled = false;
    try {
      if (typeof env.A?.put !== 'function' || typeof env.B?.put !== 'function') throw new Error('Two R2 binding prerequisites missing');
      await bounded((async () => { for (const b of ['A', 'B']) { const page = await t.list({ prefix: t.prefix, limit: 1 }, b); if (page.objects.length || page.truncated) throw new Error('Owned prefix is not fresh'); } })(), 2000);
      result.fixtureStatus = 'TRACE_ENTERED';
      const work = Promise.resolve().then(() => CASES[t.id](t)).then(() => { traceSettled = true; }, error => { traceSettled = true; throw error; });
      await bounded(work, 8000);
      if (!t.assertions.length) throw new Error('No assertions executed');
      result.fixtureStatus = 'ASSERTIONS_SATISFIED';
    } catch (error) {
      if (result.fixtureStatus === 'TRACE_ENTERED') result.fixtureStatus = traceSettled ? 'ASSERTION_OR_API_FAILURE' : 'BLOCKED_UNSETTLED_TRACE';
      result.error = String(error);
    }
    if (traceSettled) {
      try { result.cleanup = await bounded(t.cleanup(), 3000); }
      catch (error) { result.fixtureStatus = 'BLOCKED_CLEANUP'; result.cleanupError = String(error); }
    } else { result.cleanup = { status: 'EXTERNAL_REAP_REQUIRED', reason: 'Cleanup must not race unjoined trace or precondition work.' }; }
    result.traceSettled = traceSettled; result.apiCalls = t.calls; result.wallMs = Date.now() - started;
    return Response.json(result, { status: result.fixtureStatus === 'ASSERTIONS_SATISFIED' ? 200 : 500 });
  },
};
