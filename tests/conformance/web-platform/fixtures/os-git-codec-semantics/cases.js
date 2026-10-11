import { gitObjectOid, encodeLooseObject, decodeLooseObject, encodeGitTree, parseGitTree, scanGitTree, treeEntryObjectType, encodeGitCommit, parseGitCommitRefs, readGitCommitHeader, applyGitDelta, buildPackBytes, decodePackStream } from './vendor/cloudflare-os/packages/workshop-backend/src/git-codec.ts';
import { inflateSync } from 'node:zlib';
import { V } from './vectors.js';

export function unhex(text) {
  if (text.length > 140000 || text.length % 2 !== 0) throw new Error('Fixture hex envelope exceeded');
  const bytes = new Uint8Array(text.length / 2);
  for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(text.slice(i * 2, i * 2 + 2), 16);
  return bytes;
}
function hex(bytes) { return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join(''); }
function join(parts) {
  const length = parts.reduce((sum, p) => sum + p.byteLength, 0);
  if (length > 70000) throw new Error('Fixture joined-byte envelope exceeded');
  const result = new Uint8Array(length); let at = 0;
  for (const p of parts) { result.set(p, at); at += p.byteLength; }
  return result;
}
function byteSource(bytes, ends, t) {
  if (bytes.byteLength > 4096 || ends.length > 64 || ends.at(-1) !== bytes.byteLength) throw new Error('Fixture source envelope exceeded');
  let at = 0, index = 0;
  const record = { pulls: 0, closes: 0, cancels: 0, bytes: 0, completed: false };
  const stream = new ReadableStream({
    type: 'bytes',
    pull(controller) {
      if (++record.pulls > 64) throw new Error('Fixture source pull cap exceeded');
      const end = ends[index++];
      if (!(end > at && end <= bytes.byteLength)) throw new Error('Invalid authored chunk boundary');
      const chunk = bytes.slice(at, end); at = end; record.bytes += chunk.byteLength;
      controller.enqueue(chunk);
      if (at === bytes.byteLength) { controller.close(); record.closes++; record.completed = true; }
    },
    cancel() { record.cancels++; record.completed = true; },
  });
  t.resources.push(record);
  return { stream, record };
}
async function decode(bytes, ends, expected, t, resolve) {
  const source = byteSource(bytes, ends, t), retained = new Map(), lookups = [];
  // Each yielded base is saved before next() is called, as required by the real API.
  const iterator = decodePackStream(source.stream, { maxPackSize: 4096, maxObjectSize: 1024,
    resolveBase(oid) { t.operation(); lookups.push(oid); return resolve ? retained.get(oid) : undefined; },
  });
  let completed = false;
  try {
    for (let i = 0; i <= expected.length; i++) {
      t.operation(); const step = await iterator.next();
      if (i === expected.length) {
        t.same(step.done, true, 'generator finishes after exact object count and verified trailer');
        completed = true; break;
      }
      t.same(step.done, false, 'expected object is yielded');
      t.eq({ type: step.value.type, oid: step.value.oid }, { type: expected[i].type, oid: expected[i].oid }, 'literal object type and OID');
      t.bytes(step.value.payload, unhex(expected[i].payload_hex), 'literal object payload');
      retained.set(step.value.oid, step.value);
    }
  } finally {
    // This triggers the production using/dispose path on early exit as well.
    // PackReader privately owns its reader/digest. We never replace it or reach into it.
    await iterator.return();
    retained.clear();
    if (!completed) t.cleanupNeedsExternal = true;
  }
  t.same(completed, true, 'pack generator completion witnessed');
  t.eq({ closes: source.record.closes, cancels: source.record.cancels, bytes: source.record.bytes }, { closes: 1, cancels: 0, bytes: bytes.byteLength }, 'finite producer fully closes without cancellation');
  return lookups;
}

export async function X201(t) {
  const payload = unhex(V.loose.object.payload_hex);
  t.operation(); t.same(await gitObjectOid('blob', payload), V.loose.object.oid, 'known Git book object identity includes canonical header');
  t.operation(); const decoded = decodeLooseObject(unhex(V.loose.zlib_hex));
  t.same(decoded.type, 'blob', 'fixed valid loose object type');
  t.bytes(decoded.payload, payload, 'fixed stored-block loose input payload');
  t.operation(); const encoded = encodeLooseObject('blob', payload);
  t.ok(encoded.byteLength > 0 && encoded.byteLength <= 1024, 'bounded native compressed output');
  // Native inflate is an independent format oracle, not an exact compressed-byte comparison.
  t.operation(); t.bytes(inflateSync(encoded), unhex(V.loose.whole_hex), 'encoder inflated bytes include exact Git header and payload');
}

export async function X202(t) {
  const input = V.tree.input_order.map(index => ({ ...V.tree.entries[index] }));
  t.operation(); const encoded = encodeGitTree(input);
  t.bytes(encoded, unhex(V.tree.object.payload_hex), 'literal canonical tree order a.b before a directory before a0');
  t.eq(input, V.tree.input_order.map(index => V.tree.entries[index]), 'tree encoder leaves caller entry ordering unchanged');
  t.operation(); t.same(await gitObjectOid('tree', encoded), V.tree.object.oid, 'canonical tree identity');
  t.operation(); t.eq(parseGitTree(unhex(V.tree.object.payload_hex)), V.tree.entries, 'all five modes and names parse from independent literal tree');
  t.operation(); const raw = scanGitTree(unhex(V.tree.object.payload_hex));
  t.eq(raw.map(e => ({ mode: e.mode, nameHex: hex(e.nameBytes), oid: e.oid })), V.tree.entries.map(e => ({ mode: e.mode, nameHex: hex(new TextEncoder().encode(e.name)), oid: e.oid })), 'raw scanner retains exact entry bytes and OIDs');
  t.eq(V.tree.entries.map(e => { t.operation(); return treeEntryObjectType(e.mode); }), V.tree.types, 'five modes map to blob tree and commit referents');
}

export async function X203(t) {
  const commit = {
    tree: V.commit.tree, parents: [...V.commit.parents],
    author: { name: 'Fixture Author', email: 'author@example.invalid', timestamp: new Date(1700000000999), utcOffsetMinutes: 330 },
    committer: { name: 'Fixture Committer', email: 'committer@example.invalid', timestamp: new Date(1700000001999), utcOffsetMinutes: -210 },
    headers: [{ name: 'x-note', value: 'alpha' }, { name: 'x-note', value: 'beta' }],
    message: '\r\n\nMerge fixture\r\n\nDetails\r\n\n',
  };
  t.operation(); const encoded = encodeGitCommit(commit);
  t.bytes(encoded, unhex(V.commit.object.payload_hex), 'literal canonical commit author committer parents headers and message');
  t.operation(); t.same(await gitObjectOid('commit', encoded), V.commit.object.oid, 'canonical commit identity');
  t.operation(); t.eq(parseGitCommitRefs(encoded), { tree: V.commit.tree, parents: V.commit.parents }, 'merge parents retain authored order');
  t.operation(); t.eq(readGitCommitHeader(encoded, 'x-note'), ['alpha', 'beta'], 'repeated custom headers retain order');
  const continued = unhex(V.commit.continued_hex);
  t.operation(); t.eq(parseGitCommitRefs(continued), V.commit.continued_refs, 'valid continued custom header leaves commit references intact');
  t.operation(); t.eq(readGitCommitHeader(continued, 'x-note'), V.commit.continued_values, 'continuation removes exactly one space and preserves blank value line');
}

export async function X204(t) {
  const base = unhex(V.delta.base_hex), delta = unhex(V.delta.instructions_hex);
  t.operation(); const output = applyGitDelta(delta, base, 70000);
  t.same(output.byteLength, 65561, 'single valid delta exact result size');
  t.bytes(output, unhex(V.delta.expected_hex), 'literal insertion default 64KiB copy offset257 copy and final insertion');
  t.bytes(base, unhex(V.delta.base_hex), 'delta leaves base unchanged');
  t.operation(); t.same(hex(new Uint8Array(await crypto.subtle.digest('SHA-256', output))), V.delta.target_sha256, 'independent literal full-result digest');
}

export async function X205(t) {
  const objects = V.pack.objects.map(o => ({ type: o.type, payload: unhex(o.payload_hex) }));
  t.operation(); const chunks = await buildPackBytes(objects);
  t.ok(Array.isArray(chunks) && chunks.length > 0 && chunks.length <= 128, 'bounded build output chunk list');
  const built = join(chunks);
  t.ok(built.byteLength >= 32 && built.byteLength <= 4096, 'bounded complete built pack');
  t.bytes(built.subarray(0, 12), unhex('5041434b0000000200000004'), 'PACK v2 four-object header');
  const body = built.subarray(0, built.byteLength - 20);
  t.operation(); t.bytes(built.subarray(built.byteLength - 20), new Uint8Array(await crypto.subtle.digest('SHA-1', body)), 'built trailer covers body and excludes trailer');
  const builtLookups = await decode(built, [12, built.byteLength - 13, built.byteLength], V.pack.objects, t, false);
  t.eq(builtLookups, [], 'built complete pack needs no base resolution');
  const bytes = unhex(V.pack.hex);
  t.same(hex(bytes.subarray(V.pack.body_bytes)), V.pack.trailer_hex, 'independent golden has literal valid trailer');
  const lookups = await decode(bytes, [1, 4, 12, 14, 31, 64, 128, V.pack.body_bytes - 3, V.pack.body_bytes + 7, bytes.byteLength], V.pack.objects, t, false);
  t.eq(lookups, [], 'complete undeltified pack needs no base resolution');
}

export async function X206(t) {
  const bytes = unhex(V.chain.hex);
  t.bytes(bytes.subarray(281, 284), unhex('6e810d'), 'literal valid OFS entry uses backward distance269');
  t.bytes(bytes.subarray(310, 330), unhex(V.chain.lookup_oids[1]), 'REF entry points at yielded intermediate object');
  const lookups = await decode(bytes, [1, 12, 13, 14, 279, 281, 282, 283, 284, 309, 310, 329, 330, 347, 354, 367], V.chain.objects, t, true);
  t.eq(lookups, V.chain.lookup_oids, 'OFS then REF resolver accesses retained bases in pack order');
  t.same(hex(bytes.subarray(V.chain.body_bytes)), V.chain.trailer_hex, 'complete valid delta chain retains its independent trailer');
}
export const CASES = { X201, X202, X203, X204, X205, X206 };
