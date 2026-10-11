// Release 2026-10-08: io/io-context.h:257,1771; io/io-context.c++:548,650.
import {DurableObject, WorkerEntrypoint} from 'cloudflare:workers';
let releaseActor, releaseDead;
let deadResult = 'pending';
export class Entry extends WorkerEntrypoint {
  park() {
    deadResult = 'pending';
    void (async () => {
      await new Promise(resolve => { releaseDead = resolve; });
      try { await this.env.OBJ.getByName('unused').ping(); deadResult = 'borrowed'; }
      catch (error) { deadResult = error.message.includes('no longer running') ? 'dead-rejected' : error.message; }
    })();
    return 'parked';
  }
}
export class Obj extends DurableObject {
  ping() { return 'pong'; }
  async fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === '/park') {
      this.result = 'pending';
      void (async () => {
        await new Promise(resolve => { releaseActor = resolve; });
        try {
          await this.ctx.storage.sync();
          await this.ctx.blockConcurrencyWhile(async () => {
            await new Promise(resolve => setTimeout(resolve, 10));
            this.ctx.storage.kv.put('result', 'origin-ok');
          });
          this.result = this.ctx.storage.kv.get('result');
        } catch (error) { this.result = error.message; }
      })();
      return new Response('parked');
    }
    if (path === '/release') { releaseActor(); return new Response('released'); }
    return new Response(this.result);
  }
}
export default {
  async fetch(request, env) {
    const path = new URL(request.url).pathname;
    if (path === '/dead-in-turn') {
      await env.API.park();
      releaseDead();
      await new Promise(resolve => setTimeout(resolve, 100));
      return new Response(deadResult);
    }
    if (path === '/dead-park') return new Response(await env.API.park());
    if (path === '/dead-release') {
      releaseDead();
      await new Promise(resolve => setTimeout(resolve, 100));
      return new Response(deadResult);
    }
    return env.OBJ.getByName(path === '/release' ? 'b' : 'a').fetch(request);
  }
};
