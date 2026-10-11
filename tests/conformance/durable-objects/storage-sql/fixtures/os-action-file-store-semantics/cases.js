import { ActionFileStore } from './vendor/cloudflare-os/packages/gatekeeper-kit/src/action-files.ts';

// Test-only observation/oracles. All mutations go through the original module.
// Storage is the real migrated DO storage object, never a substitute or proxy.
const FILE = 'files/', ALLOC = 'alloc/', TOTAL = 'alloc/totalBytes';
const EMPTY_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
const FOUR_SHA = '9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a';
const THREE_SHA = '6e9fa019228fe1a9d342d4a0085ab80270c9726bd08cd5a35d7626a700b34e2f';
function store(storage, maxFileBytes, maxTotalBytes) {
  return new ActionFileStore(storage, { filePrefix: FILE, allocationPrefix: ALLOC, maxFileBytes, maxTotalBytes });
}
function allocation(storage, reference) { return storage.kv.get(ALLOC + reference.handle); }
function fileKeys(reference, suffixes) { return suffixes.map(suffix => FILE + reference.handle + suffix); }
function keys(storage, t) { return t.rows(storage.kv.list()).map(([key]) => key).sort(); }
function expectedKeys(references) {
  // Suffixes are supplied as literal case expectations, never derived from a
  // stored size/chunk-count or from the production chunk-size constant.
  return [TOTAL, ...references.flatMap(([ref, suffixes]) => [ALLOC + ref.handle, ...fileKeys(ref, suffixes)])].sort();
}
function retained(storage, t, reference, size, digest, chunks, before, after, label) {
  t.eq(Object.keys(reference).sort(), ['digest', 'handle', 'size'], label + ': bounded reference fields');
  t.ok(typeof reference.handle === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(reference.handle), label + ': genuine capture returned UUID');
  t.eq([reference.size, reference.digest], [size, digest], label + ': literal byte size and independent SHA256');
  t.eq(storage.kv.get(FILE + reference.handle + ':manifest'), { ...reference, version: 1, chunks }, label + ': complete manifest');
  const row = allocation(storage, reference);
  t.ok(row !== undefined && Number.isSafeInteger(row.createdAt) && row.createdAt >= before && row.createdAt <= after, label + ': allocation timestamp bracketed by genuine capture');
  t.eq(row, { version: 1, size, chunks, createdAt: row.createdAt }, label + ': exact allocation fields');
  return row.createdAt;
}
function absent(storage, t, reference, label) {
  t.same(allocation(storage, reference), undefined, label + ': allocation removed');
  t.eq(t.rows(storage.kv.list({ prefix: FILE + reference.handle + ':' })), [], label + ': manifest and every chunk removed');
}
function smallBytes(t, actual, literal, label) {
  t.ok(actual instanceof Uint8Array, label + ': native byte view');
  t.eq([...actual], literal, label + ': exact bytes');
}

export async function F201(storage, t) {
  const files = store(storage, 32, 32);
  const backing = new Uint8Array([201, 202, 10, 20, 30, 40, 50, 203]);
  const view = new Uint8Array(backing.buffer, 2, 5), before = Date.now();
  const pending = files.capture(view);
  // No await, timer, crypto mock, or storage interception occurs before mutation.
  backing.fill(99);
  const reference = await pending, after = Date.now();
  retained(storage, t, reference, 5, '6ef53a6408ec4429791fa808e4fbe7843f936316950a20ba5fbbbdd01cd29899', 1, before, after, 'captured window');
  smallBytes(t, view, [99, 99, 99, 99, 99], 'caller actually changed input');
  smallBytes(t, storage.kv.get(FILE + reference.handle + ':chunk:0000'), [10, 20, 30, 40, 50], 'stored snapshot before first await');
  smallBytes(t, await files.read(reference), [10, 20, 30, 40, 50], 'digest and read agree with original window');
  t.eq(keys(storage, t), expectedKeys([[reference, [':manifest', ':chunk:0000']]]), 'one genuine capture owns exactly four keys');
  t.same(storage.kv.get(TOTAL), 5, 'snapshot charges only the five-byte view');
}

export async function F202(storage, t) {
  const files = store(storage, 2097169, 2097169);
  const input = new Uint8Array(2097169);
  input.fill(17, 0, 1048576); input.fill(34, 1048576, 2097152);
  input.set([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], 2097152);
  const before = Date.now(), reference = await files.capture(input), after = Date.now();
  retained(storage, t, reference, 2097169, '669a63cbe23fd19a58eea8d71ca68ce9d5a24a74ed34171d5cd17ebb262d2277', 3, before, after, 'three-chunk publication');
  const chunks = t.rows(storage.kv.list({ prefix: FILE + reference.handle + ':chunk:' }));
  t.eq(chunks.map(([key, value]) => [key, value.byteLength]), [
    [FILE + reference.handle + ':chunk:0000', 1048576],
    [FILE + reference.handle + ':chunk:0001', 1048576],
    [FILE + reference.handle + ':chunk:0002', 17],
  ], 'exact full/full/tail chunk keys and lengths');
  t.ok(chunks[0][1] instanceof Uint8Array && chunks[0][1].every(byte => byte === 17), 'every first-chunk byte equals literal 17');
  t.ok(chunks[1][1] instanceof Uint8Array && chunks[1][1].every(byte => byte === 34), 'every second-chunk byte equals literal 34');
  smallBytes(t, chunks[2][1], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16], 'tail bytes at physical third chunk');
  const output = await files.read(reference);
  t.ok(output instanceof Uint8Array && output.byteLength === 2097169, 'public read has exact full length and byte brand');
  let exact = true;
  for (let i = 0; i < 2097169; i++) {
    const expected = i < 1048576 ? 17 : i < 2097152 ? 34 : i - 2097152;
    if (output[i] !== expected) { exact = false; break; }
  }
  t.ok(exact, 'every reassembled byte follows the independent literal three-region oracle');
  t.eq(keys(storage, t), expectedKeys([[reference, [':manifest', ':chunk:0000', ':chunk:0001', ':chunk:0002']]]), 'publication exposes exactly manifest allocation three chunks and counter');
  t.same(storage.kv.get(TOTAL), 2097169, 'one aggregate charge spans all physical chunks');
}

export async function F203(storage, t) {
  const files = store(storage, 8, 8), before = Date.now();
  const reference = await files.capture(new Uint8Array(0)), after = Date.now();
  retained(storage, t, reference, 0, EMPTY_SHA, 0, before, after, 'empty captured file');
  t.eq(keys(storage, t), expectedKeys([[reference, [':manifest']]]), 'empty file still owns allocation and manifest but no placeholder chunk');
  t.same(storage.kv.get(TOTAL), 0, 'empty allocation contributes exactly zero bytes');
  smallBytes(t, await files.read(reference), [], 'zero-chunk read still validates empty digest');
  files.delete(reference);
  absent(storage, t, reference, 'empty deletion');
  t.eq(t.rows(storage.kv.list()), [[TOTAL, 0]], 'empty allocation is removed even though aggregate charge was already zero');
}

export async function F204(storage, t) {
  const files = store(storage, 7, 7), before = Date.now();
  const removed = await files.capture(new Uint8Array([1, 2, 3, 4]));
  const peer = await files.capture(new Uint8Array([8, 9, 10])), after = Date.now();
  retained(storage, t, removed, 4, FOUR_SHA, 1, before, after, 'to be deleted');
  retained(storage, t, peer, 3, THREE_SHA, 1, before, after, 'unselected peer');
  t.ok(removed.handle !== peer.handle, 'two genuine captures have distinct handles');
  t.same(storage.kv.get(TOTAL), 7, 'both allocations contribute before deletion');
  const peerAllocation = allocation(storage, peer), peerManifest = storage.kv.get(FILE + peer.handle + ':manifest');
  files.delete(removed);
  absent(storage, t, removed, 'first deletion');
  t.same(storage.kv.get(TOTAL), 3, 'first deletion releases four bytes');
  files.delete(removed);
  t.same(storage.kv.get(TOTAL), 3, 'repeated valid deletion releases no additional bytes');
  t.eq([allocation(storage, peer), storage.kv.get(FILE + peer.handle + ':manifest')], [peerAllocation, peerManifest], 'peer allocation and manifest unchanged after both deletions');
  smallBytes(t, await files.read(peer), [8, 9, 10], 'peer payload after repeated deletion');
  t.eq(keys(storage, t), expectedKeys([[peer, [':manifest', ':chunk:0000']]]), 'only the complete peer and counter remain');
}

export async function F205(storage, t) {
  const files = store(storage, 9, 9), before = Date.now();
  const protectedRef = await files.capture(new Uint8Array([11, 12]));
  const orphan = await files.capture(new Uint8Array([21, 22, 23])), firstAfter = Date.now();
  const protectedAt = retained(storage, t, protectedRef, 2, '1b47e3acf9cd496936430df42e017269c3bb14f54dda91b41a90fd265960f124', 1, before, firstAfter, 'old protected capture');
  const cutoff = retained(storage, t, orphan, 3, '95cee872c44c906ec46f0fad618cd7c8c601651be78e6f9d7d2ffe745e910ef9', 1, before, firstAfter, 'old orphan at inclusive boundary');
  t.witness(protectedAt <= cutoff, 'old protected capture is eligible by genuine timestamp');
  // At most 32 ordinary 5ms waits. No clock replacement or stored timestamp edit.
  let waits = 0;
  while (Date.now() <= cutoff && waits < 32) { await new Promise(resolve => setTimeout(resolve, 5)); waits++; }
  t.witness(Date.now() > cutoff, 'clock advanced past genuine older allocation within bounded waits');
  const youngBefore = Date.now(), young = await files.capture(new Uint8Array([31, 32, 33, 34])), youngAfter = Date.now();
  const youngAt = retained(storage, t, young, 4, '06b0a21bf142b7dc9b1360ec9cef21dc20d8afe62d09448a7e0d7b09ca3c5789', 1, youngBefore, youngAfter, 'younger orphan');
  t.witness(youngAt > cutoff && new Set([protectedRef.handle, orphan.handle, young.handle]).size === 3, 'three distinct genuine captures span both sides of cutoff');
  t.observations.push({ label: 'prune timestamp witnesses', protectedAt, cutoff, youngAt, waits });
  t.same(storage.kv.get(TOTAL), 9, 'all three captures charged before pruning');
  const protectedAllocation = allocation(storage, protectedRef), youngAllocation = allocation(storage, young);
  files.pruneUnreferenced(new Set([protectedRef.handle]), cutoff);
  absent(storage, t, orphan, 'inclusive-boundary orphan pruning');
  t.same(storage.kv.get(TOTAL), 6, 'only three old-unreferenced bytes released');
  t.eq([allocation(storage, protectedRef), allocation(storage, young)], [protectedAllocation, youngAllocation], 'referenced old and unreferenced young allocations preserved');
  smallBytes(t, await files.read(protectedRef), [11, 12], 'referenced old bytes remain readable');
  smallBytes(t, await files.read(young), [31, 32, 33, 34], 'young unreferenced bytes remain readable');
  t.eq(keys(storage, t), expectedKeys([[protectedRef, [':manifest', ':chunk:0000']], [young, [':manifest', ':chunk:0000']]]), 'first pruning preserves precisely the two eligible survivors');
  files.pruneUnreferenced(new Set(), cutoff);
  absent(storage, t, protectedRef, 'old capture after consumer releases reference');
  t.same(storage.kv.get(TOTAL), 4, 'reference release allows old two-byte allocation to be reclaimed');
  smallBytes(t, await files.read(young), [31, 32, 33, 34], 'same cutoff still preserves young bytes');
  t.eq(keys(storage, t), expectedKeys([[young, [':manifest', ':chunk:0000']]]), 'only genuinely younger allocation survives second prune');
  files.pruneUnreferenced(new Set(), youngAt);
  t.eq(t.rows(storage.kv.list()), [[TOTAL, 0]], 'advancing the inclusive cutoff reclaims the final allocation and exact charge');
}

export async function F206(storage, t) {
  const files = store(storage, 8, 8), before = Date.now();
  const first = await files.capture(new Uint8Array([1, 2, 3, 4]));
  const second = await files.capture(new Uint8Array([8, 9, 10])), after = Date.now();
  retained(storage, t, first, 4, FOUR_SHA, 1, before, after, 'first admitted capture');
  retained(storage, t, second, 3, THREE_SHA, 1, before, after, 'second admitted capture');
  t.ok(first.handle !== second.handle, 'first two captures use distinct genuine handles');
  t.same(storage.kv.get(TOTAL), 7, 'two valid captures leave exactly one byte capacity');
  t.eq(keys(storage, t), expectedKeys([[first, [':manifest', ':chunk:0000']], [second, [':manifest', ':chunk:0000']]]), 'before refusal exactly two complete captures and counter exist');
  const original = t.rows(storage.kv.list());
  let refusal;
  try { await files.capture(new Uint8Array([41, 42, 43, 44, 45])); }
  catch (error) { refusal = error; }
  t.ok(refusal instanceof Error, 'valid third capture is refused at ordinary aggregate limit');
  t.same(refusal.message, 'Queued-action files exceed the safe aggregate storage limit. Resolve existing actions before adding another.', 'specific normal aggregate-limit refusal');
  t.eq(t.rows(storage.kv.list()), original, 'refusal leaves every previous native key and value unchanged with no orphan publication');
  smallBytes(t, await files.read(first), [1, 2, 3, 4], 'first payload survives refusal');
  smallBytes(t, await files.read(second), [8, 9, 10], 'second payload survives refusal');
  files.delete(first);
  const retryBefore = Date.now(), retry = await files.capture(new Uint8Array([41, 42, 43, 44, 45])), retryAfter = Date.now();
  retained(storage, t, retry, 5, '7bdeb14b9ae8423d9cfd11fe32235450cccff5ee3cdce8b58c79bb6099f1ecc5', 1, retryBefore, retryAfter, 'same valid payload after capacity release');
  t.ok(retry.handle !== second.handle, 'new capture does not replace surviving peer');
  absent(storage, t, first, 'released first capture');
  smallBytes(t, await files.read(retry), [41, 42, 43, 44, 45], 'recovery payload exact');
  smallBytes(t, await files.read(second), [8, 9, 10], 'second capture still intact at full capacity');
  t.eq(keys(storage, t), expectedKeys([[second, [':manifest', ':chunk:0000']], [retry, [':manifest', ':chunk:0000']]]), 'successful recovery publishes exactly two complete captures');
  t.same(storage.kv.get(TOTAL), 8, 'successful recovery reaches the literal aggregate limit exactly');
}

export const CASES = { F201, F202, F203, F204, F205, F206 };
