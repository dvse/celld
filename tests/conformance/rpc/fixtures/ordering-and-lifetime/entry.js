import * as cf from 'cloudflare:workers';
import { RootBase, Session, requireApi, drop } from './fixture.js';
import { orderCases, promiseDisposalCases } from './cases.js';
export const PROFILE = 'capability-order-modern-2026-09-04';
export class Root extends RootBase {
  async run(id, peerName, requestId) {
    const tag = id + ':' + crypto.randomUUID(), origin = this.inspect();
    let peer, owner, session, probeSession, result, setupOperationsEntered = false, traceEntered = false;
    try {
      requireApi(Object.hasOwn(orderCases, id), 'unknown handcrafted case ID');
      requireApi(typeof peerName === 'string' && peerName.length > 0, 'peer name required');
      peer = this.env.ROOT.getByName(peerName); owner = await peer.inspect();
      requireApi(origin.root !== owner.root && origin.isolate !== owner.isolate, 'distinct remote caller and peer recipients required');
      for (const p of [this.profile(), await peer.profile()]) {
        requireApi(p.rpc_params_dup_stubs, 'explicit modern rpc_params_dup_stubs profile required');
        requireApi(p.rpcStub && p.rpcPromise && p.symbolDispose, 'native RpcStub, RpcPromise and Symbol.dispose required');
      }
      if (id === 'O003') requireApi(typeof cf.RpcProperty === 'function', 'RpcProperty constructor required');
      setupOperationsEntered = true;
      probeSession = new Session(peer, tag + ':precondition');
      const probe = await probeSession.target('api-probe');
      requireApi(typeof probe.dup === 'function' && typeof probe[Symbol.dispose] === 'function', 'native returned stub ownership API required');
      if (id === 'O003') requireApi(probe.bad instanceof cf.RpcProperty, 'returned target getter must produce branded RpcProperty');
      const pending = probe.ping();
      requireApi(pending instanceof cf.RpcPromise, 'returned RpcTarget method must produce branded RpcPromise');
      const hasPromiseDisposal = typeof pending[Symbol.dispose] === 'function';
      await pending; if (hasPromiseDisposal) await drop(pending);
      if (promiseDisposalCases.has(id)) requireApi(hasPromiseDisposal, 'native RpcPromise Symbol.dispose is unavailable; no cancellation/lifecycle trace was entered');
      const setupCleanup = await probeSession.cleanup(); probeSession = null;
      session = new Session(peer, tag);
      traceEntered = true;
      const evidence = await orderCases[id](session);
      result = { id, requestId, tag, status: 'PASS', phase: 'complete', traceEntered, setupOperationsEntered, origin, owner, evidence, profile: PROFILE, setupCleanup };
    } catch (error) {
      const blocked = !traceEntered;
      result = { id, requestId, tag, status: blocked ? 'BLOCKED' : 'FAIL', phase: blocked ? 'precondition' : 'trace', traceEntered, setupOperationsEntered, origin, owner, profile: PROFILE, error: String(error), errorName: error?.name, errorCode: error?.code };
    }
    const cleanup = [];
    for (const current of [probeSession, session]) {
      if (!current) continue;
      try { cleanup.push(await current.cleanup()); }
      catch (error) { cleanup.push({ status: 'FAIL', error: String(error) }); }
    }
    result.cleanup = { status: cleanup.some(x => x.status === 'FAIL') ? 'FAIL' : 'ok', details: cleanup };
    if (result.cleanup.status === 'FAIL') {
      result.teardownRequired = true;
      if (result.status === 'PASS') { result.status = 'FAIL'; result.phase = 'cleanup'; }
    }
    return result;
  }
}
export default {
  async fetch(request, env) {
    let input;
    try {
      const path = new URL(request.url).pathname;
      if (path === '/health') return Response.json({ profile: PROFILE, caseIds: Object.keys(orderCases), compatibilityDate: '2026-09-04', rpcParamsDupStubs: globalThis.Cloudflare?.compatibilityFlags?.rpc_params_dup_stubs === true });
      input = await request.json();
      if (typeof input.root !== 'string' || !input.root) throw new Error('root name required');
      const root = env.ROOT.getByName(input.root);
      if (path === '/identity') return Response.json(await root.inspect());
      if (path !== '/run') throw new Error('unknown endpoint');
      if (typeof input.requestId !== 'string' || !/^[a-zA-Z0-9-]{16,80}$/.test(input.requestId)) throw new Error('dispatch correlation token required');
      return Response.json(await root.run(input.id, input.peer, input.requestId));
    } catch (error) {
      return Response.json({ id: input?.id, requestId: input?.requestId ?? null, status: 'BLOCKED', phase: 'dispatch', traceEntered: false, error: String(error), cleanup: { status: 'UNKNOWN' } }, { status: 503 });
    }
  }
};
