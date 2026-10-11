// Hand-authored direct Workers RPC codec traces. No transport mocks or raw envelopes.
import { RpcTarget, RpcPromise, RpcProperty } from 'cloudflare:workers';

const check = (value, message) => { if (!value) throw new Error(message); };
const equal = (actual, expected, message) => check(JSON.stringify(actual) === JSON.stringify(expected), message);
const dispose = async value => { if (value != null && typeof value[Symbol.dispose] === 'function') await value[Symbol.dispose](); };
const pause = () => new Promise(resolve => setTimeout(resolve, 10));
class CodecPreconditionError extends Error {
  constructor(message) { super('PRECONDITION: ' + message); this.name = 'CodecPreconditionError'; this.code = 'CODEC_PRECONDITION'; }
}
const requireApi = (value, message) => { if (!value) throw new CodecPreconditionError(message); };
async function rejected(call, message) {
  try { await call(); } catch (error) { return error; }
  throw new Error('Expected rejection: ' + message);
}
function cloneError(error) { check(error?.name === 'DataCloneError', 'expected DataCloneError, got ' + String(error)); }
async function poll(read, accept, label) {
  for (let n = 0; n < 100; n++) { const result = await read(); if (accept(result)) return result; await pause(); }
  throw new Error('bounded settlement failed: ' + label);
}
async function stillHealthy(peer, tag) { equal(await peer.codecControl(tag), 'codec-alive', 'failure poisoned later RPC'); }
async function noDispatch(peer, tag) { equal((await peer.codecStats(tag)).accepted, 0, 'rejected argument reached receiver'); }
function localReadable(state) { return new ReadableStream({ cancel() { state.cancelled++; } }, { highWaterMark: 0 }); }

class CodecToken extends RpcTarget {
  constructor(state, label) { super(); this.state = state; this.label = label; }
  identify() { this.state.calls++; return this.label; }
  [Symbol.dispose]() { this.state.disposed++; }
}
class UnsupportedMapKey { constructor() { this.value = 'unsupported-map-key'; } }

export const extendCodecRoot = Base => class extends Base {
  constructor(ctx, env) { super(ctx, env); this.codecStates = new Map(); this.codecResources = new Map(); }
  codecStateFor(tag) {
    let state = this.codecStates.get(tag);
    if (!state) { state = { accepted: 0, calls: 0, disposed: 0, getters: 0, throws: 0, cancelled: 0, aborted: 0 }; this.codecStates.set(tag, state); }
    return state;
  }
  codecStats(tag) { return { ...this.codecStateFor(tag) }; }
  codecControl(tag) { this.codecStateFor(tag); return 'codec-alive'; }
  codecAccept(tag, _value) { this.codecStateFor(tag).accepted++; return 'accepted'; }
  codecEcho(tag, value) { this.codecStateFor(tag).accepted++; return value; }
  codecMixedGraph(tag) {
    const state = this.codecStateFor(tag), leaf = { label: 'shared' };
    const graph = { leaf, list: [leaf], map: new Map(), set: new Set(), token: new CodecToken(state, 'mixed') };
    graph.self = graph; leaf.root = graph; graph.map.set(leaf, graph.list); graph.map.set(graph, leaf); graph.set.add(leaf); graph.set.add(graph.map);
    return graph;
  }
  codecSparse(tag) { const list = new Array(8); list[2] = 'middle'; list[4] = new CodecToken(this.codecStateFor(tag), 'sparse'); return list; }
  codecProtoData(tag) {
    const out = { token: new CodecToken(this.codecStateFor(tag), 'proto-data') };
    Object.defineProperty(out, '__proto__', { value: { ordinary: 'data' }, enumerable: true, configurable: true, writable: true });
    return out;
  }
  async codecReadGetter(tag, value) { this.codecStateFor(tag).accepted++; return { a: value.a, b: value.b, callback: await value.callback('getter') }; }
  codecFailAfterToken(tag) { const state = this.codecStateFor(tag); return { token: new CodecToken(state, 'unpublished'), invalid: Symbol('ordinary-uncloneable') }; }
  codecFailAfterWritable(tag) {
    const state = this.codecStateFor(tag);
    const stream = new WritableStream({ abort() { state.aborted++; } });
    this.codecResources.set(tag, { writable: stream });
    return { stream, invalid: Symbol('uncloneable-after-writable') };
  }
  codecLocks(tag) {
    const resources = this.codecResources.get(tag);
    return { writable: resources?.writable?.locked ?? false };
  }
  codecHeaders(tag) {
    const headers = new Headers([['X-List', 'first'], ['x-list', 'second'], ['Set-Cookie', 'a=1'], ['Set-Cookie', 'b=2']]);
    this.codecResources.set(tag, { headers }); return { headers };
  }
  codecMutateHeaders(tag) { this.codecResources.get(tag).headers.set('x-list', 'changed'); }
  codecFile(tag) { requireApi(typeof File === 'function', 'provider File constructor available'); this.codecStateFor(tag); return { file: new File([Uint8Array.of(0, 128, 255)], 'résumé.bin', { type: 'APPLICATION/X-CODEC', lastModified: 0 }) }; }
  async codecReadRequest(tag, request) {
    this.codecStateFor(tag).accepted++;
    return { isRequest: request instanceof Request, url: request.url, method: request.method, header: request.headers.get('x-codec'), redirect: request.redirect, bytes: Array.from(new Uint8Array(await request.arrayBuffer())), used: request.bodyUsed };
  }
  codecNullResponse(tag) { this.codecStateFor(tag); return new Response(null, { status: 204, statusText: 'No Payload', headers: { 'x-codec': 'null-body' } }); }
  codecErrorResponse(tag) { this.codecStateFor(tag); return Response.error(); }
  codecHostAliases(tag) { this.codecStateFor(tag); const h = new Headers({ 'x-shared': 'v1' }); return { headers: h, list: [h], map: new Map([[h, h]]) }; }
  codecViewGraph(tag) {
    const buffer = Uint8Array.of(250, 1, 2, 3, 4, 251).buffer;
    return { buffer, bytes: new Uint8Array(buffer, 1, 4), data: new DataView(buffer, 2, 2), token: new CodecToken(this.codecStateFor(tag), 'views') };
  }
  codecChangeBytes(tag, bytes) { this.codecStateFor(tag).accepted++; bytes[1] = 77; return bytes; }
  codecNumbers(tag) { return { values: [undefined, -0, NaN, Infinity, -Infinity, 9007199254740993n, -9007199254740997n], token: new CodecToken(this.codecStateFor(tag), 'numbers') }; }
  codecNativeLeaves(tag) { const pattern = /codec/gi; pattern.lastIndex = 7; return { valid: new Date(-123456789), invalid: new Date(NaN), pattern, token: new CodecToken(this.codecStateFor(tag), 'native') }; }
  codecThrowRich(tag) {
    this.codecStateFor(tag).throws++;
    const error = new TypeError('typed-failure', { cause: new RangeError('inner-range') });
    error.code = 'E_CODEC'; error.details = { stage: 'provider' }; error.details.self = error.details;
    throw error;
  }
  codecThrowUncloneable(tag) {
    const state = this.codecStateFor(tag); state.throws++;
    const error = new Error('fallback-failure'); error.name = 'FixtureFallbackError'; error.callback = () => { state.calls++; };
    throw error;
  }
  codecThrowObject(tag) { this.codecStateFor(tag).throws++; const error = { reason: 'plain-object' }; error.self = error; throw error; }
  codecThrowUndefined(tag) { this.codecStateFor(tag).throws++; throw undefined; }
  async codecRejectAfterCallback(tag, callback) { const s = this.codecStateFor(tag); s.accepted++; await callback('before-reject'); s.throws++; throw new Error('after-callback'); }
  codecErrorValue(tag) { this.codecStateFor(tag); return { error: new RangeError('value-error', { cause: new Error('value-cause') }), value: 42 }; }
  codecThrowDom(tag) { this.codecStateFor(tag).throws++; throw new DOMException('dom-codec-failure', 'DataCloneError'); }
  async codecRelayFailure(tag, callback) { this.codecStateFor(tag).accepted++; return await callback(); }
  codecThrowCustomName(tag) { this.codecStateFor(tag).throws++; const error = new Error('named-failure'); Object.defineProperty(error, 'name', { value: 'FixtureNamedError', enumerable: false }); error.code = 'E_NAME'; throw error; }
  codecGetterResult(tag) {
    const state = this.codecStateFor(tag), out = { token: new CodecToken(state, 'getter-result') };
    Object.defineProperty(out, 'sequence', { enumerable: true, get() { return ++state.getters; } });
    return out;
  }
  codecHiddenMembers(tag) {
    const state = this.codecStateFor(tag), out = { value: 'visible', token: new CodecToken(state, 'hidden-members') };
    Object.defineProperty(out, 'hidden', { get() { state.getters++; throw new Error('hidden-getter-ran'); } });
    out[Symbol('ignored')] = new UnsupportedMapKey();
    return out;
  }
  codecProxyData(tag) {
    const state = this.codecStateFor(tag), target = { field: 'proxy-field', token: new CodecToken(state, 'proxy-data') };
    return new Proxy(target, { get(object, property, receiver) { if (property === 'field') state.getters++; return Reflect.get(object, property, receiver); } });
  }
  codecArrayProperty(tag) { const out = [13]; out.extra = { token: new CodecToken(this.codecStateFor(tag), 'array-extra') }; return out; }
  async codecCleanup(tag) {
    const r = this.codecResources.get(tag);
    // Never use hidden runtime tables to repair a leak under test.
    if (r?.writable) {
      check(!r.writable.locked, 'CLEANUP_BLOCKED: leaked writable lock requires owned fixture teardown');
      await r.writable.abort('fixture-cleanup');
    }
    this.codecResources.delete(tag); this.codecStates.delete(tag);
  }
};

const traces = {
  async C001({ peer, tag }) {
    const node = { value: 5 }, value = { node, list: [node], map: new Map(), set: new Set() };
    value.self = value; node.parent = value; value.map.set(node, value.list); value.set.add(value); value.set.add(node);
    const result = await peer.codecEcho(tag, value);
    check(result !== value && result.node !== node, 'clone leaked sender identity');
    check(result.self === result && result.node.parent === result, 'ordinary cycle broken');
    check(result.node === result.list[0] && result.map.get(result.node) === result.list, 'ordinary aliases or Map key changed');
    check(result.set.has(result) && result.set.has(result.node), 'Set identities broken');
    result.node.value = 9; equal(node.value, 5, 'return mutation reached caller source');
    return { cycles: true, aliases: true, detached: true };
  },
  async C002({ peer, tag }) {
    const result = await peer.codecMixedGraph(tag);
    try {
      check(result.self === result && result.leaf.root === result, 'lifted graph cycles broken');
      check(result.leaf === result.list[0] && result.map.get(result.leaf) === result.list && result.map.get(result) === result.leaf, 'lifted aliases or map identity broken');
      check(result.set.has(result.leaf) && result.set.has(result.map), 'lifted Set identities broken');
      equal(await result.token.identify(), 'mixed', 'capability not revived in cyclic graph');
      return { topology: 'object-array-map-set-cycle', capability: 'mixed' };
    } finally { await dispose(result); }
  },
  async C003({ peer, tag }) {
    const result = await peer.codecSparse(tag);
    try {
      equal(result.length, 8, 'lift lost sparse trailing length');
      equal(Object.keys(result), ['2', '4'], 'revival materialized holes');
      check(!Object.hasOwn(result, 0) && !Object.hasOwn(result, 7), 'holes became undefined slots');
      equal(result[2], 'middle', 'sparse data shifted'); equal(await result[4].identify(), 'sparse', 'sparse capability index changed');
      return { length: result.length, keys: Object.keys(result) };
    } finally { await dispose(result); }
  },
  async C004({ peer, tag }) {
    const result = await peer.codecProtoData(tag);
    try {
      check(Object.hasOwn(result, '__proto__'), 'ordinary own __proto__ data was erased');
      equal(result.__proto__, { ordinary: 'data' }, 'ordinary __proto__ payload changed');
      check(Object.getPrototypeOf(result) === Object.prototype, 'data property altered result prototype');
      equal(await result.token.identify(), 'proto-data', 'sibling capability missing');
      return { ownProtoData: true, ordinaryPrototype: true };
    } finally { await dispose(result); }
  },
  async C005({ peer, tag }) {
    const reads = [], value = { get a() { reads.push('a'); return 7; }, get b() { reads.push('b'); return 8; }, callback: label => label + '-callback' };
    const result = await peer.codecReadGetter(tag, value);
    equal(reads, ['a', 'b'], 'argument getters evaluated again after clone fallback');
    equal(result, { a: 7, b: 8, callback: 'getter-callback' }, 'snapshot/callback data wrong');
    equal((await peer.codecStats(tag)).accepted, 1, 'argument dispatch count');
    return { reads, result };
  },
  async C006({ peer, tag }) {
    let reads = 0, later = 0;
    const value = { get first() { reads++; throw new Error('argument-getter-stop'); }, get later() { later++; return 1; } };
    const error = await rejected(() => peer.codecAccept(tag, value), 'throwing argument getter');
    check(String(error).includes('argument-getter-stop'), 'argument getter reason lost');
    equal([reads, later], [1, 0], 'getter traversal continued or repeated'); await noDispatch(peer, tag); await stillHealthy(peer, tag);
    return { error: String(error), reads, later };
  },
  async C007({ peer, tag }) {
    const invalid = Object.create(null); invalid.value = 'not-an-ordinary-prototype';
    const error = await rejected(() => peer.codecAccept(tag, { nested: [invalid] }), 'nested null prototype');
    cloneError(error); await noDispatch(peer, tag); await stillHealthy(peer, tag);
    return { name: error.name, rejectedBeforeDispatch: true };
  },
  async C008({ peer, tag }) {
    const graph = new Map([[{ okay: 1 }, 'first'], [new UnsupportedMapKey(), 'second']]);
    const error = await rejected(() => peer.codecAccept(tag, graph), 'custom class used only as a Map key');
    cloneError(error); await noDispatch(peer, tag); await stillHealthy(peer, tag);
    return { name: error.name, mapKeyValidated: true };
  },
  async C009({ peer, tag }) {
    const graph = new Set(); graph.add(graph); graph.add(Symbol('uncloneable-set-value'));
    const error = await rejected(() => peer.codecAccept(tag, graph), 'uncloneable member after Set self-cycle');
    cloneError(error); await noDispatch(peer, tag); await stillHealthy(peer, tag);
    return { name: error.name, setRejectedAtomically: true };
  },
  async C010({ peer, tag }) {
    const error = await rejected(() => peer.codecFailAfterToken(tag), 'result encode after capability allocation');
    cloneError(error);
    const state = await poll(() => peer.codecStats(tag), s => s.disposed === 1, 'rollback unpublished result capability');
    equal(state.calls, 0, 'unpublished target unexpectedly called'); await stillHealthy(peer, tag);
    return { name: error.name, disposed: state.disposed, calls: state.calls };
  },
  async C011({ peer, tag }) {
    const state = { cancelled: 0 }, first = localReadable(state), second = localReadable({ cancelled: 0 }), held = second.getReader();
    let failure;
    try {
      const error = await rejected(() => peer.codecAccept(tag, { first, second }), 'second stream locked after first lifted');
      check(error instanceof Error && String(error).includes('locked'), 'locked stream refusal lost');
      await noDispatch(peer, tag);
      await poll(async () => ({ locked: first.locked, cancelled: state.cancelled }), s => !s.locked && s.cancelled === 1, 'rollback first readable argument');
      await stillHealthy(peer, tag); return { firstUnlocked: true, cancelled: state.cancelled };
    } catch (error) { failure = error; throw error; }
    finally {
      await held.cancel('fixture-cleanup'); held.releaseLock();
      if (!first.locked) await first.cancel('fixture-cleanup');
      else throw new Error((failure ? String(failure) + '; ' : '') + 'CLEANUP_BLOCKED: unpublished readable bridge remains locked; owned fixture teardown required');
    }
  },
  async C012({ peer, tag }) {
    const error = await rejected(() => peer.codecFailAfterWritable(tag), 'result final encode after writable bridge allocation');
    cloneError(error);
    const state = await poll(async () => ({ ...(await peer.codecStats(tag)), ...(await peer.codecLocks(tag)) }), s => !s.writable && s.aborted === 1, 'rollback unpublished writable result');
    await stillHealthy(peer, tag); return { aborted: state.aborted, locked: state.writable };
  },
  async C013({ peer, tag }) {
    const target = await peer.mint(); let pending;
    try {
      pending = target.method();
      requireApi(pending instanceof RpcPromise, 'RpcTarget method produces branded RpcPromise');
      const error = await rejected(() => peer.codecAccept(tag, { pending }), 'nested RpcPromise argument'); cloneError(error);
      const settled = await pending; equal(settled.value, 'private-value', 'serialization rejection corrupted original promise');
      equal(settled.root, (await peer.inspect()).root, 'original promise recipient changed');
      await noDispatch(peer, tag); return { name: error.name, originalValue: settled.value, brandedRpcPromise: true };
    } finally { if (pending) { await Promise.resolve(pending).catch(() => {}); await dispose(pending); } await dispose(target); }
  },
  async C014({ peer, tag }) {
    const target = await peer.mint();
    try {
      const before = await peer.effectCount('getter');
      const property = target.exposed;
      requireApi(property instanceof RpcProperty, 'RpcTarget property produces branded RpcProperty');
      const error = await rejected(() => peer.codecAccept(tag, { property }), 'nested RpcProperty argument'); cloneError(error);
      equal(await peer.effectCount('getter'), before, 'failed property serialization eagerly fetched the property');
      equal(await property, 'instance-only', 'rejected serialization consumed the property handle');
      equal(await peer.effectCount('getter'), before + 1, 'explicit property await did not evaluate exactly once');
      await noDispatch(peer, tag); return { name: error.name, brandedRpcProperty: true, getterDeltaAfterRejection: 0, getterDeltaAfterAwait: 1 };
    } finally { await dispose(target); }
  },
  async C015({ peer, tag }) {
    const { headers } = await peer.codecHeaders(tag);
    requireApi(typeof headers.getSetCookie === 'function', 'Headers.getSetCookie available');
    check(headers instanceof Headers, 'Headers lost brand'); equal(headers.get('x-list'), 'first, second', 'Header list merge changed');
    equal(headers.getSetCookie(), ['a=1', 'b=2'], 'Set-Cookie list collapsed');
    await peer.codecMutateHeaders(tag); equal(headers.get('x-list'), 'first, second', 'Headers not a by-value snapshot');
    return { list: headers.get('x-list'), cookies: headers.getSetCookie() };
  },
  async C016({ peer, tag }) {
    const backing = Uint8Array.of(99, 0, 128, 255, 88), blob = new Blob([backing.subarray(1, 4)], { type: 'APPLICATION/X-CODEC' });
    backing.fill(77); const result = await peer.codecEcho(tag, { payload: [blob] });
    check(result.payload[0] instanceof Blob, 'Blob lost brand'); equal(result.payload[0].type, 'application/x-codec', 'Blob MIME wrong');
    equal(Array.from(new Uint8Array(await result.payload[0].arrayBuffer())), [0, 128, 255], 'Blob included out-of-view or mutated bytes');
    return { size: result.payload[0].size, type: result.payload[0].type };
  },
  async C017({ peer, tag }) {
    requireApi(typeof File === 'function', 'File constructor available');
    const { file } = await peer.codecFile(tag);
    check(file instanceof File && file instanceof Blob, 'File revived as Blob or plain object');
    equal([file.name, file.lastModified, file.type, file.size], ['résumé.bin', 0, 'application/x-codec', 3], 'File metadata lost or timestamp zero defaulted');
    equal(Array.from(new Uint8Array(await file.arrayBuffer())), [0, 128, 255], 'File bytes wrong');
    return { name: file.name, lastModified: file.lastModified, size: file.size };
  },
  async C018({ peer, tag }) {
    const request = new Request('https://codec.invalid/local-only?q=%E2%9C%93', { method: 'POST', headers: { 'x-codec': 'buffered' }, body: Uint8Array.of(0, 13, 255), redirect: 'manual' });
    const result = await peer.codecReadRequest(tag, request);
    equal(result, { isRequest: true, url: 'https://codec.invalid/local-only?q=%E2%9C%93', method: 'POST', header: 'buffered', redirect: 'manual', bytes: [0, 13, 255], used: true }, 'Request envelope or body changed');
    // This URL is data only; no fetch or other network operation occurs.
    return result;
  },
  async C019({ peer, tag }) {
    const response = await peer.codecNullResponse(tag);
    check(response instanceof Response, 'Response brand lost'); check(response.body === null, 'null response body became an empty stream');
    equal([response.status, response.statusText, response.headers.get('x-codec')], [204, 'No Payload', 'null-body'], 'Response metadata wrong');
    equal(await response.text(), '', 'null body not empty on read'); return { status: response.status, bodyWasNull: true };
  },
  async C020({ peer, tag }) {
    const response = await peer.codecErrorResponse(tag);
    check(response instanceof Response, 'Response.error brand lost'); equal([response.type, response.status, response.body], ['error', 0, null], 'network-error response cannot revive through ordinary status constructor');
    await stillHealthy(peer, tag); return { type: response.type, status: response.status };
  },
  async C021({ peer, tag }) {
    const result = await peer.codecHostAliases(tag);
    check(result.headers === result.list[0], 'same host marker revived into distinct objects');
    check(result.map.has(result.headers) && result.map.get(result.headers) === result.headers, 'host alias lost as Map key/value');
    result.headers.set('x-shared', 'v2'); equal(result.list[0].get('x-shared'), 'v2', 'host alias mutation not shared');
    return { hostIdentityPreserved: true, mapIdentityPreserved: true };
  },
  async C022({ peer, tag }) {
    const result = await peer.codecViewGraph(tag);
    try {
      check(result.bytes.buffer === result.buffer && result.data.buffer === result.buffer, 'view backing buffer aliases split in lifted graph');
      equal([result.bytes.byteOffset, result.bytes.byteLength, result.data.byteOffset, result.data.byteLength], [1, 4, 2, 2], 'view offset or length changed');
      equal(Array.from(result.bytes), [1, 2, 3, 4], 'view leaked sentinels'); result.bytes[1] = 61;
      equal(result.data.getUint8(0), 61, 'overlapping views no longer alias'); equal(await result.token.identify(), 'views', 'mixed capability lost');
      return { offsets: [1, 2], overlappingByte: 61 };
    } finally { await dispose(result); }
  },
  async C023({ peer, tag }) {
    const bytes = Uint8Array.of(1, 2, 3), result = await peer.codecChangeBytes(tag, bytes);
    equal(bytes.byteLength, 3, 'ordinary RPC unexpectedly detached sender buffer'); equal(Array.from(bytes), [1, 2, 3], 'callee mutation reached sender');
    equal(Array.from(result), [1, 77, 3], 'callee mutation absent from result'); result[0] = 99; equal(bytes[0], 1, 'return shares caller buffer');
    return { sender: Array.from(bytes), result: Array.from(result) };
  },
  async C024({ peer, tag }) {
    const result = await peer.codecNumbers(tag);
    try {
      const v = result.values; check(Object.hasOwn(v, 0) && v[0] === undefined, 'undefined element changed');
      check(Object.is(v[1], -0) && Number.isNaN(v[2]) && v[3] === Infinity && v[4] === -Infinity, 'non-JSON numeric values damaged');
      check(v[5] === 9007199254740993n && v[6] === -9007199254740997n, 'bigints lost precision or sign');
      equal(await result.token.identify(), 'numbers', 'number graph capability missing'); return { specialNumbersPreserved: true, bigints: v.slice(5).map(String) };
    } finally { await dispose(result); }
  },
  async C025({ peer, tag }) {
    const result = await peer.codecNativeLeaves(tag);
    try {
      check(result.valid instanceof Date && result.invalid instanceof Date && result.pattern instanceof RegExp, 'native leaf brands lost on lift');
      equal(result.valid.getTime(), -123456789, 'negative date changed'); check(Number.isNaN(result.invalid.getTime()), 'invalid Date normalized');
      equal([result.pattern.source, result.pattern.flags, result.pattern.lastIndex], ['codec', 'gi', 0], 'RegExp clone state wrong');
      equal(await result.token.identify(), 'native', 'native graph capability missing'); return { date: result.valid.getTime(), regex: String(result.pattern), lastIndex: result.pattern.lastIndex };
    } finally { await dispose(result); }
  },
  async C026({ peer, tag }) {
    const error = await rejected(() => peer.codecThrowRich(tag), 'rich exception');
    check(error instanceof Error, 'exception did not reconstruct an Error');
    equal([error.name, error.message, error.code], ['TypeError', 'typed-failure', 'E_CODEC'], 'exception fields lost');
    equal([error.cause?.name, error.cause?.message], ['RangeError', 'inner-range'], 'non-enumerable cause lost');
    check(error.details.self === error.details && error.details.stage === 'provider', 'cyclic exception details broken');
    equal((await peer.codecStats(tag)).throws, 1, 'provider retried throw'); await stillHealthy(peer, tag);
    return { name: error.name, code: error.code, cause: error.cause.message, cyclicDetails: true };
  },
  async C027({ peer, tag }) {
    const error = await rejected(() => peer.codecThrowUncloneable(tag), 'uncloneable exception property');
    equal([error.name, error.message], ['FixtureFallbackError', 'fallback-failure'], 'fallback lost exception name/message');
    check(error.callback === undefined, 'uncloneable property was granted as a callback');
    equal((await peer.codecStats(tag)).calls, 0, 'fallback invoked uncloneable error property'); await stillHealthy(peer, tag);
    return { name: error.name, message: error.message, noCallback: true };
  },
  async C028({ peer, tag }) {
    const error = await rejected(() => peer.codecThrowObject(tag), 'non-Error thrown object');
    check(!(error instanceof Error) && error.reason === 'plain-object' && error.self === error, 'non-Error rejection topology or kind changed');
    await stillHealthy(peer, tag); return { kind: 'plain-object', selfCycle: true };
  },
  async C029({ peer, tag }) {
    let caught = false, reason = 'not-caught';
    try { await peer.codecThrowUndefined(tag); } catch (error) { caught = true; reason = error; }
    check(caught && reason === undefined, 'throw undefined converted to fulfillment or Error');
    equal((await peer.codecStats(tag)).throws, 1, 'undefined throw not reached exactly once'); await stillHealthy(peer, tag);
    return { caught: true, reasonWasUndefined: true };
  },
  async C030({ peer, tag }) {
    const seen = [];
    const error = await rejected(() => peer.codecRejectAfterCallback(tag, value => { seen.push(value); return 'callback-done'; }), 'async rejection after callback');
    equal(seen, ['before-reject'], 'callback skipped or repeated'); check(String(error).includes('after-callback'), 'async exception reason lost');
    const stats = await peer.codecStats(tag); equal([stats.accepted, stats.throws], [1, 1], 'async invocation repeated'); await stillHealthy(peer, tag);
    return { seen, error: String(error), invocations: stats.accepted };
  },
  async C031({ peer, tag }) {
    const result = await peer.codecErrorValue(tag);
    equal(result.value, 42, 'successful error-valued result rejected or lost sibling');
    check(result.error instanceof Error, 'Error value brand lost'); equal([result.error.name, result.error.message, result.error.cause?.message], ['RangeError', 'value-error', 'value-cause'], 'Error data fields lost');
    check(result.error.remote !== true, 'ordinary Error data incorrectly tagged as thrown remote exception');
    return { name: result.error.name, message: result.error.message, value: result.value };
  },
  async C032({ peer, tag }) {
    const error = await rejected(() => peer.codecThrowDom(tag), 'DOMException envelope');
    equal([error.name, error.message], ['DataCloneError', 'dom-codec-failure'], 'DOMException name degraded to Error');
    await stillHealthy(peer, tag); return { name: error.name, message: error.message };
  },
  async C033({ peer, tag }) {
    const results = await Promise.allSettled([peer.codecEcho(tag, { position: 'left', data: [1, 2] }), peer.codecThrowDom(tag), peer.codecEcho(tag, { position: 'right', data: new Map([['n', 3]]) })]);
    equal(results.map(r => r.status), ['fulfilled', 'rejected', 'fulfilled'], 'one response error contaminated sibling calls');
    equal(results[0].value, { position: 'left', data: [1, 2] }, 'first reply misassociated');
    equal([results[1].reason.name, results[1].reason.message], ['DataCloneError', 'dom-codec-failure'], 'middle exception misassociated');
    equal(results[2].value.position, 'right', 'last reply misassociated'); equal(results[2].value.data.get('n'), 3, 'last Map damaged');
    const stats = await peer.codecStats(tag); equal([stats.accepted, stats.throws], [2, 1], 'bounded fanout lost or repeated calls');
    return { statuses: results.map(r => r.status), accepted: stats.accepted, throws: stats.throws };
  },
  async C034({ peer, tag }) {
    let calls = 0;
    const error = await rejected(() => peer.codecRelayFailure(tag, () => { calls++; const e = new Error('callback-origin', { cause: new Error('callback-cause') }); e.code = 'E_CALLBACK'; throw e; }), 'exception through reverse callback and relay');
    equal(calls, 1, 'reverse call retried'); equal([error.message, error.code, error.cause?.message], ['callback-origin', 'E_CALLBACK', 'callback-cause'], 'second exception envelope stripped callback details');
    await stillHealthy(peer, tag); return { calls, message: error.message, code: error.code };
  },
  async C035({ peer, tag }) {
    const error = await rejected(() => peer.codecThrowCustomName(tag), 'non-enumerable effective name');
    equal([error.name, error.message, error.code], ['FixtureNamedError', 'named-failure', 'E_NAME'], 'effective custom name lost outside enumerable props');
    check(error instanceof Error, 'custom name prevented Error reconstruction'); await stillHealthy(peer, tag);
    return { name: error.name, code: error.code };
  },
  async C036({ peer, tag }) {
    const first = await peer.codecGetterResult(tag); let second;
    try {
      second = await peer.codecGetterResult(tag);
      equal([first.sequence, second.sequence], [1, 2], 'provider enumerable getter evaluated twice per result');
      equal((await peer.codecStats(tag)).getters, 2, 'provider result projection repeated getter');
      equal(await first.token.identify(), 'getter-result', 'first result capability invalidated by second result');
      equal(await second.token.identify(), 'getter-result', 'second result capability invalid');
      return { sequences: [first.sequence, second.sequence], evaluations: 2 };
    } finally { await dispose(second); await dispose(first); }
  },
  async C037({ peer, tag }) {
    const result = await peer.codecHiddenMembers(tag);
    try {
      equal(result.value, 'visible', 'visible field lost'); check(!Object.hasOwn(result, 'hidden'), 'non-enumerable property copied');
      equal(Object.getOwnPropertySymbols(result).filter(s => s !== Symbol.dispose).length, 0, 'symbol-keyed field copied');
      equal((await peer.codecStats(tag)).getters, 0, 'non-enumerable getter executed'); equal(await result.token.identify(), 'hidden-members', 'visible capability lost');
      return { hiddenGetterCalls: 0, omittedSymbols: true };
    } finally { await dispose(result); }
  },
  async C038({ peer, tag }) {
    const result = await peer.codecProxyData(tag);
    try {
      equal(result.field, 'proxy-field', 'plain-emulating Proxy data lost'); equal(await result.token.identify(), 'proxy-data', 'Proxy nested capability lost');
      equal((await peer.codecStats(tag)).getters, 1, 'Proxy value get repeated by fallback');
      check(Object.getPrototypeOf(result) === Object.prototype, 'Proxy leaked custom result prototype');
      return { field: result.field, fieldReads: 1 };
    } finally { await dispose(result); }
  },
  async C039({ peer, tag }) {
    const result = await peer.codecArrayProperty(tag);
    try {
      equal(result.length, 1, 'non-index property altered array length'); equal(result[0], 13, 'array indexed data lost');
      check(Object.hasOwn(result, 'extra'), 'enumerable non-index array property dropped'); equal(await result.extra.token.identify(), 'array-extra', 'non-index capability not revived');
      return { length: result.length, nonIndexCapability: 'array-extra' };
    } finally { await dispose(result); }
  },
  async C040({ peer, tag }) {
    const settled = Promise.resolve({ ordinary: 'promise-value' });
    const error = await rejected(() => peer.codecAccept(tag, { nested: [settled] }), 'native Promise as nested data');
    cloneError(error); await noDispatch(peer, tag); equal(await settled, { ordinary: 'promise-value' }, 'rejection corrupted native Promise'); await stillHealthy(peer, tag);
    return { name: error.name, nestedPromiseRejected: true };
  }
};

// This wrapper only supplies shared cleanup; every trace above is individually authored.
export const codecCases = Object.fromEntries(Object.entries(traces).map(([id, run]) => [id, async context => {
  let failure;
  try { return await run(context); }
  catch (error) { failure = error; throw error; }
  finally {
    try { await context.peer.codecCleanup(context.tag); }
    catch (cleanup) { throw new Error((failure ? String(failure) + '; ' : '') + 'codec cleanup: ' + String(cleanup)); }
  }
}]));
