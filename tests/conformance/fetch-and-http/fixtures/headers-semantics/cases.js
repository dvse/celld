// Hand-authored finite cases. These exports execute inside direct celld only.
// Every expected value below is a fixed oracle, not computed by the API under test.
export function V201(t) {
  const trace = [];
  const record = Object.create({ 'X-Inherited': 'excluded' });
  Object.defineProperty(record, 'X-Hidden', { value: 'excluded', enumerable: false });
  Object.defineProperty(record, 'X-Public', { get() { trace.push('getter'); return ' public '; }, enumerable: true });
  const proxy = new Proxy(record, {
    ownKeys(target) { trace.push('keys'); return Reflect.ownKeys(target); },
    getOwnPropertyDescriptor(target, key) { trace.push('descriptor:' + key); return Reflect.getOwnPropertyDescriptor(target, key); },
    get(target, key, receiver) { if (typeof key === 'string') trace.push('get:' + key); return Reflect.get(target, key, receiver); },
  });
  const h = new Headers(proxy);
  t.eq(trace, ['keys', 'descriptor:X-Hidden', 'descriptor:X-Public', 'get:X-Public', 'getter'], 'record access order');
  t.eq([...h], [['x-public', 'public']], 'only own enumerable field retained and trimmed');
}

export function V202(t) {
  const trace = [];
  const input = {
    'X-Record': 'must-not-be-used',
    *[Symbol.iterator]() {
      trace.push('begin'); yield ['X-Mode', 'iterable'];
      trace.push('second'); yield ['X-Count', 'two']; trace.push('end');
    },
  };
  const h = new Headers(input);
  t.eq(trace, ['begin', 'second', 'end'], 'custom iterable exhausted once');
  t.eq([...h], [['x-count', 'two'], ['x-mode', 'iterable']], 'iterable takes priority over record fields');
  t.eq(h.has('X-Record'), false, 'record-only field absent');
}

export function V203(t) {
  const original = new Headers({ 'X-Origin': 'one' });
  let calls = 0;
  original[Symbol.iterator] = function* () { calls++; yield ['X-View', 'projected']; };
  const copy = new Headers(original);
  t.eq(calls, 1, 'Headers input uses its overridden iterator');
  t.eq([...copy], [['x-view', 'projected']], 'custom public iteration determines copy');
  t.eq(original.get('x-origin'), 'one', 'copy did not mutate source list');
}

export function V204(t) {
  const trace = [];
  const name = { toString() { trace.push('name'); return 'X-Coerced'; } };
  const value = { toString() { trace.push('value'); return '\t accepted value \t'; } };
  const h = new Headers(); h.append(name, value);
  t.eq(trace, ['name', 'value'], 'append coerces name before value exactly once');
  t.eq(h.get('x-coerced'), 'accepted value', 'valid value conversion precedes edge whitespace removal');
  h.append('X-Coerced', 42);
  t.eq([...h], [['x-coerced', 'accepted value, 42']], 'number value is converted without changing field identity');
}

export function V205(t) {
  const h = new Headers([['X-B', 'left'], ['X-A', 'old'], ['x-a', 'older'], ['X-C', 'right']]);
  t.eq([...h], [['x-a', 'old, older'], ['x-b', 'left'], ['x-c', 'right']], 'prime sorted pair memo');
  h.set('X-A', 'replacement'); h.append('x-a', 'tail');
  t.eq([...h], [['x-a', 'replacement, tail'], ['x-b', 'left'], ['x-c', 'right']], 'set compacts repeats and invalidates memo');
  t.eq(h.get('x-c'), 'right', 'parallel name/value arrays remain aligned');
}

export function V206(t) {
  const h = new Headers([['X-A', 'remove-one'], ['X-B', ''], ['x-a', 'remove-two'], ['X-C', 'keep']]);
  h.delete('X-A');
  t.eq([...h], [['x-b', ''], ['x-c', 'keep']], 'delete compacts all matching fields');
  t.eq([h.has('x-a'), h.get('x-a'), h.has('x-b'), h.get('x-b')], [false, null, true, ''], 'empty value differs from absent field');
  h.append('x-a', 'new'); h.delete('x-missing');
  t.eq([...h], [['x-a', 'new'], ['x-b', ''], ['x-c', 'keep']], 'reinsertion and no-op deletion preserve survivors');
}

export function V207(t) {
  const h = new Headers([['Z-Tail', 'last'], ['Set-Cookie', 'a=1; Path=/'], ['X-List', 'alpha'], ['set-cookie', 'b=2; Path=/'], ['x-list', 'beta']]);
  const expected = [['set-cookie', 'a=1; Path=/'], ['set-cookie', 'b=2; Path=/'], ['x-list', 'alpha, beta'], ['z-tail', 'last']];
  t.eq([...h.entries()], expected, 'sort ordinary names while retaining separate ordered cookie fields');
  t.eq([...h.keys()], ['set-cookie', 'set-cookie', 'x-list', 'z-tail'], 'keys retain multiplicity of cookie fields');
  t.eq([...h.values()], ['a=1; Path=/', 'b=2; Path=/', 'alpha, beta', 'last'], 'values align with sorted entries');
}

export function V208(t) {
  const h = new Headers([['X-A', 'one'], ['X-C', 'three']]);
  const it = h.entries();
  t.eq(it.next(), { value: ['x-a', 'one'], done: false }, 'first iterator step');
  h.append('X-B', 'two');
  t.eq(it.next(), { value: ['x-b', 'two'], done: false }, 'live iterator includes insertion after cursor');
  t.eq(it.next(), { value: ['x-c', 'three'], done: false }, 'existing suffix remains reachable');
  t.done(it.next(), 'bounded iterator exhausts after three entries');
}

export function V209(t) {
  const h = new Headers([['X-A', 'one'], ['X-B', 'two'], ['X-C', 'three']]);
  const it = h.entries();
  t.eq(it.next().value, ['x-a', 'one'], 'advance cursor once');
  h.delete('x-a');
  t.eq(it.next().value, ['x-c', 'three'], 'deleting before live numeric cursor shifts later entries');
  t.done(it.next(), 'iterator has no stale duplicate');
  t.eq([...h], [['x-b', 'two'], ['x-c', 'three']], 'fresh iterator sees complete remaining list');
}

export function V210(t) {
  const h = new Headers([['X-A', 'one'], ['X-B', 'old']]);
  const it = h.entries();
  t.eq(it.next().value, ['x-a', 'one'], 'prime iterator and memo');
  h.set('x-b', 'new'); h.append('X-B', 'tail');
  t.eq(it.next().value, ['x-b', 'new, tail'], 'unvisited value reflects both mutations');
  t.done(it.next(), 'mutating value did not create extra logical name');
}

export function V211(t) {
  const h = new Headers([['X-A', 'one'], ['X-C', 'three']]);
  const receiver = { marker: 'receiver' }, calls = [];
  h.forEach(function (value, key, owner) {
    t.same(this, receiver, 'forEach thisArg identity');
    t.same(owner, h, 'forEach third argument identity');
    calls.push([key, value]);
    if (key === 'x-a') owner.append('X-B', 'two');
  }, receiver);
  t.eq(calls, [['x-a', 'one'], ['x-b', 'two'], ['x-c', 'three']], 'forEach observes one finite live insertion');
}

export function V212(t) {
  const h = new Headers([['X-A', 'untouched'], ['Set-Cookie', 'a=1'], ['Set-Cookie', 'b=2']]);
  const pair = h.entries().next().value, cookies = h.getSetCookie();
  pair[0] = 'changed'; pair[1] = 'changed'; cookies[0] = 'changed'; cookies.push('changed');
  t.eq([...h], [['set-cookie', 'a=1'], ['set-cookie', 'b=2'], ['x-a', 'untouched']], 'returned pair mutation does not corrupt memo');
  t.eq(h.getSetCookie(), ['a=1', 'b=2'], 'returned cookie array detached from list');
  h.set('X-A', 'later');
  t.eq(pair, ['changed', 'changed'], 'previous returned entry remains independent');
}

export function V213(t) {
  const pair = ['X-A', 'one'];
  const source = { *[Symbol.iterator]() {
    yield pair;
    pair[0] = 'X-B'; pair[1] = 'two'; yield pair;
  } };
  const h = new Headers(source);
  pair[0] = 'X-C'; pair[1] = 'after';
  t.eq([...h], [['x-a', 'one'], ['x-b', 'two']], 'iterable tuple is consumed at each yield rather than retained by reference');
  t.eq(h.has('x-c'), false, 'later source tuple reuse cannot rewrite constructed list');
}

export async function V214(t) {
  let pull = 0, closed = false;
  const chunks = [new Uint8Array([65, 66]), new Uint8Array([67]), new Uint8Array([68, 69])];
  const body = new ReadableStream({ pull(controller) {
    if (pull < 3) controller.enqueue(chunks[pull++]);
    else { closed = true; controller.close(); }
  } });
  const response = new Response(body);
  t.trackBody(response, () => closed);
  await caches.default.put('https://cache.fixture.invalid/producer', response);
  t.eq([pull, closed, response.bodyUsed], [3, true, true], 'put drains finite producer through close before resolving');
}

export async function V215(t) {
  const original = new Response('cache-copy-\u03bb');
  const copy = original.clone(); t.trackBody(original); t.trackBody(copy);
  await caches.default.put(new Request('https://cache.fixture.invalid/clone'), copy);
  t.eq([copy.bodyUsed, original.bodyUsed], [true, false], 'cache owns only submitted clone branch');
  t.eq(await original.text(), 'cache-copy-\u03bb', 'unsubmitted branch remains complete');
}

export async function V216(t) {
  const key = 'https://cache.fixture.invalid/source-contract';
  const response = new Response('accepted-but-not-retained'); t.trackBody(response);
  await caches.default.put(key, response);
  t.eq(response.bodyUsed, true, 'successful put consumes body');
  t.same(await caches.default.match(key), undefined, 'pinned celld cache always misses after put');
  t.eq(await caches.default.delete(key), false, 'pinned no-store cache deletion reports false');
  t.same(await caches.default.match(key), undefined, 'delete leaves explicit miss');
}

export async function V217(t) {
  const response = new Response(null, { status: 204, headers: { 'X-Empty': 'yes' } });
  await caches.default.put('https://cache.fixture.invalid/empty', response);
  t.eq([response.status, response.body, response.bodyUsed], [204, null, false], 'bodyless put neither fabricates nor disturbs a body');
  response.headers.set('X-Empty', 'still-mutable');
  t.eq(response.headers.get('x-empty'), 'still-mutable', 'put leaves supplied header object mutable');
}

export async function V218(t) {
  const closed = [];
  const left = new Response(new ReadableStream({ start(c) { c.enqueue(new Uint8Array([76])); c.close(); closed.push('left'); } }));
  const right = new Response(new ReadableStream({ start(c) { c.enqueue(new Uint8Array([82, 82])); c.close(); closed.push('right'); } }));
  t.trackBody(left, () => closed.includes('left')); t.trackBody(right, () => closed.includes('right'));
  const named = await caches.open('finite-pair');
  await Promise.all([named.put('https://cache.fixture.invalid/left', left), caches.default.put('https://cache.fixture.invalid/right', right)]);
  t.eq(closed, ['left', 'right'], 'both finite producers completed once');
  t.eq([left.bodyUsed, right.bodyUsed], [true, true], 'independent named/default puts both consume submitted bodies');
}

export const CASES = { V201, V202, V203, V204, V205, V206, V207, V208, V209, V210, V211, V212, V213, V214, V215, V216, V217, V218 };
