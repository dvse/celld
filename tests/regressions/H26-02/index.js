import { DurableObject, RpcTarget, WorkerEntrypoint } from 'cloudflare:workers'

class Target extends RpcTarget {
  ping() { return 'pong' }
}

export class Obj extends DurableObject {
  target() { return new Target() }
}

export class Echo extends WorkerEntrypoint {
  ping() { return 'pong' }
}

const NAMES = ['dup', 'ping', 'anything', 'then', 'catch', 'constructor', 'fetch', 'toString']

// `name in value` for each probed name, and Symbol.dispose.
function presence(value) {
  const out = {}
  for (const name of NAMES) out[name] = name in value
  out['Symbol.dispose'] = Symbol.dispose in value
  return out
}

// The Publication Gatekeeper's lease (hyperbob packages/publication-gatekeeper/src/contracts.ts
// ActivePublicationLease.resolveForAction): each resolution owns a dup of the retained identity
// when the identity is a stub, so disposing one resolution leaves the lease's own identity alive.
function resolveFrom(lease) {
  return 'dup' in lease.identity ? lease.identity.dup() : lease.identity
}

export default {
  async fetch(request, env, ctx) {
    const object = env.OBJ.getByName('a')
    const pending = object.target()
    const property = pending.ping
    const received = await pending
    const duped = received.dup()
    const result = {
      durableObjectStub: presence(object),
      exportsEntrypoint: presence(ctx.exports.Echo),
      rpcPromise: presence(pending),
      rpcProperty: presence(property),
      receivedStub: presence(received),
      dupedStub: presence(duped),
    }
    const lease = { identity: received }
    const first = resolveFrom(lease)
    result.firstResolution = await first.ping()
    first[Symbol.dispose]()
    try {
      result.secondResolution = await resolveFrom(lease).ping()
    } catch (error) {
      result.secondResolution = 'ERROR ' + error.message
    }
    duped[Symbol.dispose]()
    received[Symbol.dispose]()
    return Response.json(result)
  },
}
