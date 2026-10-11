import { DurableObject } from 'cloudflare:workers';

const CHILD = `import { DurableObject } from 'cloudflare:workers';
export class Child extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.storage.sql.exec('CREATE TABLE IF NOT EXISTS items(id INTEGER PRIMARY KEY, v TEXT NOT NULL)');
  }
  write(v) { this.ctx.storage.sql.exec('INSERT INTO items(v) VALUES (?)', v); }
  read() { return this.ctx.storage.sql.exec('SELECT v FROM items ORDER BY id').toArray().map(r => r.v); }
}`;

export class Root extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    ctx.storage.sql.exec('CREATE TABLE IF NOT EXISTS log(id INTEGER PRIMARY KEY, v TEXT NOT NULL)');
  }
  child() {
    const worker = this.env.LOADER.load({
      compatibilityDate: '2026-09-16',
      mainModule: 'child.js',
      modules: { 'child.js': { js: CHILD } },
    });
    return this.ctx.facets.get('child', () => ({ class: worker.getDurableObjectClass('Child') }));
  }
  async write(v) {
    this.ctx.storage.sql.exec('INSERT INTO log(v) VALUES (?)', v);
    await this.child().write(v);
  }
  async read() {
    return {
      root: this.ctx.storage.sql.exec('SELECT v FROM log ORDER BY id').toArray().map(r => r.v),
      facet: await this.child().read(),
    };
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const stub = env.ROOT.get(env.ROOT.idFromName('probe'));
    if (url.pathname === '/write') { await stub.write(url.searchParams.get('v')); return new Response('ok'); }
    if (url.pathname === '/read') return Response.json(await stub.read());
    return new Response('not found', { status: 404 });
  },
};
