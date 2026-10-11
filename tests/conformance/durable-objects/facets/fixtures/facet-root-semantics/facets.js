import { DurableObject } from 'cloudflare:workers';
const MODULE_TOKEN = crypto.randomUUID();
function identity(ctx) {
  return { kind: typeof ctx.id === 'string' ? 'string' : 'DurableObjectId', value: String(ctx.id), name: typeof ctx.id === 'string' ? null : (ctx.id.name ?? null) };
}
function typedSummary(p) {
  if (!p || !p.date) return null;
  const key = [...p.map.keys()][0];
  return { date: p.date.toISOString(), dateBrand: p.date instanceof Date, bigint: String(p.bigint), bytes: [...p.bytes], bytesBrand: p.bytes instanceof Uint16Array, mapBrand: p.map instanceof Map, setBrand: p.set instanceof Set, alias: key === p.shared && p.set.has(p.shared), cycle: p.self === p, score: p.map.get(key) };
}
export class Facet extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.heap = 0;
    this.birth = crypto.randomUUID();
    this.initialTyped = typedSummary(ctx.props);
    this.initialLabel = ctx.props?.label ?? null;
  }
  identity() { return identity(this.ctx); }
  moduleInfo() { return { token: MODULE_TOKEN, origin: this.env.ORIGIN, birth: this.birth }; }
  put(key, value) { this.ctx.storage.kv.put(key, value); return this.ctx.storage.kv.get(key); }
  read(key) { return this.ctx.storage.kv.get(key) ?? null; }
  state() { return { heap: this.heap, count: this.ctx.storage.kv.get('count') ?? 0, birth: this.birth }; }
  step(label) {
    this.heap++;
    const count = (this.ctx.storage.kv.get('count') ?? 0) + 1;
    this.ctx.storage.kv.put('count', count);
    return { label, heap: this.heap, count, birth: this.birth };
  }
  propsState() { return { label: this.ctx.props.label, visits: this.ctx.props.visits ?? 0, initialLabel: this.initialLabel }; }
  mutateProps() { this.ctx.props.visits = (this.ctx.props.visits ?? 0) + 1; return this.propsState(); }
  typedAtConstruction() { return this.initialTyped; }
  async schema(kind) {
    if (kind === 'text') {
      this.ctx.storage.sql.exec('CREATE TABLE shared (label TEXT NOT NULL)').toArray();
      this.ctx.storage.sql.exec('INSERT INTO shared VALUES (?)', 'facet-row').toArray();
    } else if (kind === 'blob') {
      this.ctx.storage.sql.exec('CREATE TABLE shared (payload BLOB NOT NULL)').toArray();
      this.ctx.storage.sql.exec("INSERT INTO shared VALUES (X'0102')").toArray();
    }
    return this.schemaState();
  }
  schemaState() {
    return { columns: this.ctx.storage.sql.exec('PRAGMA table_info(shared)').toArray().map(x => x.name), rows: this.ctx.storage.sql.exec('SELECT * FROM shared').toArray().map(x => Object.fromEntries(Object.entries(x).map(([k,v]) => [k, v instanceof ArrayBuffer ? [...new Uint8Array(v)] : v]))) };
  }
  child(name, options = {}) {
    return this.ctx.facets.get(name, () => ({ class: this.ctx.exports.Facet({ props: options.props ?? {} }), ...(options.id === undefined ? {} : { id: options.id }) }));
  }
  async descendantIdentity(name, id) { return this.child(name, id === undefined ? {} : { id }).identity(); }
  async childPut(name, key, value) { return this.child(name).put(key, value); }
  async childRead(name, key) { return this.child(name).read(key); }
  async childSchema(name, kind) { return this.child(name).schema(kind); }
  async childSchemaState(name) { return this.child(name).schemaState(); }
  async chain(names, values) {
    this.ctx.storage.kv.put('level', values[0]);
    const tail = names.length ? await this.child(names[0]).chain(names.slice(1), values.slice(1)) : [];
    return [this.ctx.storage.kv.get('level'), ...tail];
  }
  async chainRead(names) {
    const tail = names.length ? await this.child(names[0]).chainRead(names.slice(1)) : [];
    return [this.ctx.storage.kv.get('level') ?? null, ...tail];
  }
  async readChildProps(name, props) { return this.child(name, { props }).propsState(); }
  async rollbackOwn() {
    const value = await this.ctx.storage.transaction(async tx => {
      await tx.put('child', 'tentative-child');
      tx.rollback();
      return 'declined';
    });
    return { outcome: value, child: this.ctx.storage.kv.get('child') ?? null };
  }
  async commitWithDeclinedChild() {
    return this.ctx.storage.transaction(async tx => {
      await tx.put('parent', 'committed-parent');
      const child = await this.child('leaf').rollbackOwn();
      await tx.put('decision', child.outcome);
      return child;
    });
  }
  async clearOwn() { await this.ctx.storage.deleteAll(); return { own: [...await this.ctx.storage.list()] }; }
  async deleteChildAndRead(name) {
    this.ctx.facets.delete(name);
    return this.child(name).read('value');
  }
  async nestedModule() {
    const leaf = this.ctx.facets.get('module-leaf', () => ({ class: this.ctx.exports.Leaf }));
    return { parent: this.env.ORIGIN, child: await leaf.origin() };
  }
  async fetch(request) {
    const url = new URL(request.url);
    if (url.pathname.startsWith('/relay/')) {
      const child = this.child(url.pathname.slice('/relay/'.length));
      const next = new Request('https://owned.fixture.invalid/echo?tag=' + url.searchParams.get('tag'), request);
      const response = await child.fetch(next);
      const headers = new Headers(response.headers);
      headers.set('x-parent-scope', this.initialLabel ?? 'relay');
      return new Response(response.body, { status: response.status, headers });
    }
    if (url.pathname === '/echo') {
      const body = await request.text();
      this.ctx.storage.kv.put('echo', body);
      return Response.json({ method: request.method, tag: url.searchParams.get('tag'), route: request.headers.get('x-route'), body }, { status: 202, headers: { 'x-child-scope': 'leaf' } });
    }
    return Response.json(this.step('fetch:' + url.pathname));
  }
}
export class Leaf extends DurableObject {
  origin() { return this.env.ORIGIN + ':leaf'; }
}
export class Plain {
  constructor(ctx, env) { this.ctx = ctx; this.env = env; this.calls = 0; this.label = ctx.props.label; }
  increment() { this.calls++; this.ctx.storage.kv.put('plain', this.calls); return { calls: this.calls, stored: this.ctx.storage.kv.get('plain'), label: this.label, origin: this.env.ORIGIN }; }
  fetch() { return Response.json(this.increment()); }
}
export function localModuleToken() { return MODULE_TOKEN; }
