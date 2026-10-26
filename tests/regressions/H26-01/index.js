import { DurableObject } from 'cloudflare:workers'

// One isolated computation per call, as Hyperbob's Workshop runs them
// (cloudflare-os workshop-backend isolated-module.ts): a fresh unnamed
// Dynamic Worker, one RPC, and the stub dropped without dispose().
const CODE = {
  compatibilityDate: '2026-01-01',
  mainModule: 'main.js',
  modules: {
    'main.js':
      "import { WorkerEntrypoint } from 'cloudflare:workers'\n" +
      'export default class extends WorkerEntrypoint { invoke(x) { return x + 1 } }\n',
  },
  env: {},
  globalOutbound: null,
}

async function loadMany(loader, count) {
  let done = 0
  try {
    for (let i = 0; i < count; i++) {
      const result = await loader.load(CODE).getEntrypoint().invoke(i)
      if (result !== i + 1) throw new Error(`wrong result ${result} for ${i}`)
      done++
    }
    return { done }
  } catch (error) {
    return { done, error: String(error?.message ?? error) }
  }
}

function count(request) {
  return Number(new URL(request.url).searchParams.get('n') ?? '0')
}

export class Holder extends DurableObject {
  async fetch(request) {
    return Response.json(await loadMany(this.env.LOADER, count(request)))
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url)
    if (url.pathname === '/object') {
      return env.HOLDER.get(env.HOLDER.idFromName(url.searchParams.get('name') ?? 'a')).fetch(request)
    }
    return Response.json(await loadMany(env.LOADER, count(request)))
  },
}
