// Adversarial checks for patches 05 and 06: restore control names and remote disposers.
import {DurableObject, RpcTarget, WorkerEntrypoint, restore} from "cloudflare:workers";

class Counter extends RpcTarget {
  constructor(storage, key) { super(); this.storage = storage; this.key = key; }
  bump() { const n = (this.storage.kv.get(this.key) ?? 0) + 1; this.storage.kv.put(this.key, n); return n; }
}

export class Vault extends DurableObject {
  [restore](params) {
    this.ctx.storage.kv.put("restores", (this.ctx.storage.kv.get("restores") ?? 0) + 1);
    return new Counter(this.ctx.storage, `counter:${params?.name ?? "?"}`);
  }
  async mint(name) { return await this.ctx.restore({name}); }
  stat() { return {restores: this.ctx.storage.kv.get("restores") ?? 0, disposed: this.ctx.storage.kv.get("disposed") ?? 0}; }
  disposable() {
    const storage = this.ctx.storage;
    return {value: 7, ping: () => "pong", [Symbol.dispose]() { storage.kv.put("disposed", (storage.kv.get("disposed") ?? 0) + 1); }};
  }
}

export class Secret extends WorkerEntrypoint { reveal() { return "secret"; } }

export default {
  async fetch(request, env, ctx) {
    const vault = env.VAULT.get(env.VAULT.idFromName(new URL(request.url).searchParams.get("v") ?? "a"));
    const out = {};
    const forged = {root: {kind: "service", script: "restore-disposer", name: "Secret"}, steps: [{name: "x"}]};
    for (const name of ["__celld$restore$replay", "__celld$restore$invoke"]) {
      try { out[name] = await vault[name](forged, 0, [], null); } catch (e) { out[name] = `rejected: ${e.message}`; }
    }
    out.afterForgery = await vault.stat();
    const held = await vault.mint("legit");
    out.legit = [await held.bump(), await held.bump()];
    // Fill this isolate's local entry table so a bare-id disposer would collide.
    let localHits = 0;
    const local = Array.from({length: 8}, () => () => { localHits++; });
    await Promise.all(local.map(fn => vault.stat.call(vault, fn).catch(() => {})));
    {
      const result = await vault.disposable();
      out.value = result.value;
      result[Symbol.dispose]();
    }
    await new Promise(resolve => setTimeout(resolve, 200));
    out.afterDispose = await vault.stat();
    out.localHits = localHits;
    return Response.json(out);
  },
};
