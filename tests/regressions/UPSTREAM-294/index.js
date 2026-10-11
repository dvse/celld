import { DurableObject } from 'cloudflare:workers'

// Work that the first request starts and every later request shares: the usual
// lazily initialised resource, here a timer or an outbound fetch.
export class Lazy extends DurableObject {
  async fetch(request) {
    const url = new URL(request.url)
    if (url.pathname === '/timer') this.ready ??= new Promise((resolve) => setTimeout(() => resolve('timer fired'), 500))
    if (url.pathname === '/fetch') this.ready ??= fetch(url.searchParams.get('origin')).then((r) => r.text())
    if (url.pathname === '/wait-until') {
      this.ready ??= new Promise((resolve) => setTimeout(() => resolve('timer fired'), 500))
      this.ctx.waitUntil(this.ready)
    }
    return new Response(await this.ready)
  }
}

export default {
  fetch(request, env) {
    const url = new URL(request.url)
    return env.LAZY.get(env.LAZY.idFromName(url.searchParams.get('object'))).fetch(request)
  },
}
