// Handwritten ordinary R2 workflows over fresh synthetic keys in a private store.
export async function I201(t) {
  const written = await t.put('text', 'héλ');
  t.eq([written.key, written.size], [t.key('text'), 5], 'put reports decoded key and UTF-8 byte size');
  t.ok(written.uploaded instanceof Date && Number.isFinite(written.uploaded.getTime()), 'upload timestamp is a usable Date');
  t.eq(written.httpEtag, '"' + written.etag + '"', 'HTTP etag quotes the opaque object etag');
  const head = await t.head('text');
  t.same(head.body, undefined, 'head is metadata-only');
  t.eq([head.key, head.size, head.etag], [t.key('text'), 5, written.etag], 'head describes the stored revision');
  t.eq(await t.read(await t.get('text'), 'text'), 'héλ', 'get reads exact original text');
}
export async function I202(t) {
  const bytes = new Uint8Array([99, 10, 20, 30, 88]);
  await t.put('view', new DataView(bytes.buffer, 1, 3));
  bytes.fill(0);
  t.eq([...new Uint8Array(await t.read(await t.get('view'), 'arrayBuffer'))], [10, 20, 30], 'DataView byte window stored without unrelated backing bytes');
  const blob = new Blob([new Uint8Array([4, 5]), 'Z']);
  await t.put('blob', blob);
  t.eq([...new Uint8Array(await t.read(await t.get('blob'), 'arrayBuffer'))], [4, 5, 90], 'Blob parts flatten to exact bytes through value conversion');
}
export async function I203(t) {
  let next = 0, closed = false;
  const chunks = [new Uint8Array([1, 2]), new Uint8Array(0), new Uint8Array([3, 4, 5])];
  const body = new ReadableStream({ pull(c) { if (next < 3) c.enqueue(chunks[next++]); else { closed = true; c.close(); } } });
  t.trackInput(body, () => closed);
  const written = await t.put('stream', body);
  t.eq([next, closed, written.size], [3, true, 5], 'finite streaming put drains through empty chunk and EOF');
  t.eq([...new Uint8Array(await t.read(await t.get('stream'), 'arrayBuffer'))], [1, 2, 3, 4, 5], 'stored body concatenates nonempty chunks exactly');
}
export async function I204(t) {
  await t.put('metadata', 'body', { httpMetadata: { contentType: 'text/plain', contentLanguage: 'en', cacheControl: 'max-age=60', cacheExpiry: new Date('2030-01-02T03:04:05.000Z') }, customMetadata: { Project: 'demo', label: 'café' } });
  const object = await t.head('metadata'), headers = new Headers({ 'X-Keep': 'unchanged', 'Content-Type': 'replace-me' });
  object.writeHttpMetadata(headers);
  t.eq([headers.get('content-type'), headers.get('content-language'), headers.get('cache-control'), headers.get('expires'), headers.get('x-keep')], ['text/plain', 'en', 'max-age=60', 'Wed, 02 Jan 2030 03:04:05 GMT', 'unchanged'], 'metadata writer replaces only stored content fields and formats expiry');
  t.eq(Object.entries(object.customMetadata).sort(), [['Project', 'demo'], ['label', 'café']], 'case-sensitive Unicode custom metadata survives its envelope');
  t.eq(object.httpMetadata.cacheExpiry.toISOString(), '2030-01-02T03:04:05.000Z', 'metadata expiry revives as Date');
}
export async function I205(t) {
  await t.put('replace', 'old', { httpMetadata: new Headers({ 'Content-Type': 'text/plain', 'Cache-Control': 'max-age=90', 'X-Unrelated': 'not-content-metadata' }), customMetadata: { stale: 'remove' } });
  await t.put('replace', 'new', { httpMetadata: { contentLanguage: 'fr' }, customMetadata: { current: 'keep' } });
  const h = await t.head('replace');
  t.eq(h.customMetadata, { current: 'keep' }, 'overwrite replaces custom metadata rather than merging stale entries');
  t.eq([h.httpMetadata.contentType, h.httpMetadata.cacheControl, h.httpMetadata.contentLanguage], [undefined, undefined, 'fr'], 'overwrite clears omitted prior content fields');
  t.eq(await t.read(await t.get('replace'), 'text'), 'new', 'body replaced together with metadata');
}
export async function I206(t) {
  await t.put('readers', 'independent-reader-content');
  const first = await t.get('readers'), second = await t.get('readers');
  t.eq([first.bodyUsed, second.bodyUsed], [false, false], 'fresh reads each begin unconsumed');
  const reader = first.body.getReader();
  try { const chunk = await reader.read(); t.ok(chunk.done === false && chunk.value.length > 0, 'first stream begins finite data'); await reader.cancel('ordinary consumer done'); t.markBodyClosed(first); }
  finally { reader.releaseLock(); }
  t.eq(second.bodyUsed, false, 'cancelling one reader does not disturb another');
  t.eq(await t.read(second, 'text'), 'independent-reader-content', 'independent reader remains complete after peer cancellation');
  t.eq(await t.read(await t.get('readers'), 'text'), 'independent-reader-content', 'consumer cancellation does not remove stored object');
}
export async function I207(t) {
  const written = await t.put('conditional-read', 'payload', { customMetadata: { revision: 'one' } });
  const unmodified = await t.get('conditional-read', { onlyIf: { etagDoesNotMatch: written.etag } });
  t.ok(unmodified !== null, 'failed read condition still reports existing object');
  t.same(unmodified.body, undefined, 'unmet read condition yields metadata without body');
  t.eq([unmodified.etag, unmodified.customMetadata.revision], [written.etag, 'one'], 'metadata identifies the withheld revision');
  const matched = await t.get('conditional-read', { onlyIf: new Headers({ 'If-Match': written.httpEtag }) });
  t.eq(await t.read(matched, 'text'), 'payload', 'quoted conditional header permits matching object read');
  t.same(await t.get('missing-read'), null, 'missing object remains distinct from conditional metadata-only result');
}
export async function I208(t) {
  const prior = await t.put('cas', 'first');
  const updated = await t.put('cas', 'second', { onlyIf: { etagMatches: prior.etag } });
  t.ok(updated !== null, 'matching compare-and-set returns a stored object');
  const refused = await t.put('cas', 'must-not-replace', { onlyIf: { etagMatches: prior.etag } });
  t.same(refused, null, 'stale ordinary write condition is refused without throwing');
  t.eq(await t.read(await t.get('cas'), 'text'), 'second', 'refused conditional write leaves successful revision intact');
  t.eq((await t.head('cas')).etag, updated.etag, 'refused write leaves metadata revision intact');
}
export async function I209(t) {
  const first = await t.put('create-only', 'created', { onlyIf: new Headers({ 'If-None-Match': '*' }) });
  t.ok(first !== null, 'create-only header condition accepts absent key');
  const second = await t.put('create-only', 'blocked-replacement', { onlyIf: { etagDoesNotMatch: '*' } });
  t.same(second, null, 'create-only object condition refuses an existing key');
  t.eq(await t.read(await t.get('create-only'), 'text'), 'created', 'create-only refusal preserves initial object');
}
export async function I210(t) {
  await t.put('ranges', '0123456789');
  const middle = await t.get('ranges', { range: { offset: 2, length: 4 } });
  t.eq([middle.size, middle.range.offset, middle.range.length], [10, 2, 4], 'range response retains full object size and exact returned window');
  t.eq(await t.read(middle, 'text'), '2345', 'structured bounded range has correct byte boundaries');
  const suffix = await t.get('ranges', { range: new Headers({ Range: 'bytes=-3' }) });
  t.eq(await t.read(suffix, 'text'), '789', 'header suffix range selects final bytes');
  t.eq(await t.read(await t.get('ranges'), 'text'), '0123456789', 'range reads do not change full-object content');
}
export async function I211(t) {
  await t.put('pages/c', 'C'); await t.put('pages/a', 'A'); await t.put('pages/b', 'B');
  const keys = [], cursors = new Set(); let cursor, complete = false;
  for (let pageNumber = 0; pageNumber < 6; pageNumber++) {
    const page = await t.list({ prefix: t.key('pages/'), limit: 2, ...(cursor ? { cursor } : {}) });
    t.ok(page.objects.length <= 2, 'each bounded page obeys requested maximum');
    keys.push(...page.objects.map(o => o.key));
    if (!page.truncated) { t.same(page.cursor, undefined, 'complete page omits cursor'); complete = true; break; }
    t.ok(typeof page.cursor === 'string' && page.cursor.length > 0 && !cursors.has(page.cursor), 'truncated page has advancing opaque cursor');
    cursors.add(page.cursor); cursor = page.cursor;
  }
  t.ok(complete, 'finite three-object enumeration completes within six pages');
  t.eq(keys, [t.key('pages/a'), t.key('pages/b'), t.key('pages/c')], 'bounded pagination returns each ASCII key once in order');
}
export async function I212(t) {
  await t.put('tree/root.txt', 'root'); await t.put('tree/sub/a', 'a'); await t.put('tree/sub/b', 'b'); await t.put('tree/other/c', 'c');
  const page = await t.list({ prefix: t.key('tree/'), delimiter: '/', limit: 10 });
  t.eq(page.objects.map(o => o.key), [t.key('tree/root.txt')], 'delimiter exposes only direct child objects');
  t.eq(page.delimitedPrefixes.slice().sort(), [t.key('tree/other/'), t.key('tree/sub/')], 'nested objects roll up once per distinct child prefix without imposing prefix-array order');
  t.eq(page.truncated, false, 'tiny complete directory fits bounded page');
}
export async function I213(t) {
  await t.put('extras/object', 'data', { httpMetadata: { contentType: 'text/plain' }, customMetadata: { label: 'visible' } });
  const plain = await t.list({ prefix: t.key('extras/'), limit: 5 });
  const httpOnly = await t.list({ prefix: t.key('extras/'), limit: 5, include: ['httpMetadata'] });
  const customOnly = await t.list({ prefix: t.key('extras/'), limit: 5, include: ['customMetadata'] });
  t.eq([plain.objects.length, httpOnly.objects.length, customOnly.objects.length], [1, 1, 1], 'each metadata projection retains the same object');
  t.eq([plain.objects[0].httpMetadata, plain.objects[0].customMetadata], [{}, {}], 'omitted extras are not fabricated');
  t.eq([httpOnly.objects[0].httpMetadata.contentType, httpOnly.objects[0].customMetadata], ['text/plain', {}], 'http-only projection includes no custom metadata');
  t.eq([customOnly.objects[0].httpMetadata, customOnly.objects[0].customMetadata], [{}, { label: 'visible' }], 'custom-only projection includes no HTTP metadata');
}
export async function I214(t) {
  await t.put('same-name', 'first-bucket', {}, 'A'); await t.put('same-name', 'second-bucket', {}, 'B');
  t.eq(await t.read(await t.get('same-name', {}, 'A'), 'text'), 'first-bucket', 'first binding resolves its own keyspace');
  t.eq(await t.read(await t.get('same-name', {}, 'B'), 'text'), 'second-bucket', 'second binding resolves its own keyspace');
  await t.remove(['same-name'], 'A');
  t.same(await t.head('same-name', 'A'), null, 'first binding deletion visible');
  t.eq(await t.read(await t.get('same-name', {}, 'B'), 'text'), 'second-bucket', 'first binding deletion cannot remove second binding object');
}
export async function I215(t) {
  await t.put('delete/a', 'A'); await t.put('delete/b', 'B'); await t.put('delete/c', 'C');
  await t.remove(['delete/a', 'delete/c']);
  t.same(await t.head('delete/a'), null, 'batch removes first requested object');
  t.same(await t.get('delete/c'), null, 'batch removes second requested body');
  t.eq(await t.read(await t.get('delete/b'), 'text'), 'B', 'unrequested neighbor remains intact');
  await t.remove(['delete/a', 'delete/c']);
  t.eq((await t.list({ prefix: t.key('delete/'), limit: 5 })).objects.map(o => o.key), [t.key('delete/b')], 'idempotent absent deletion leaves exact surviving listing');
}
export async function I216(t) {
  await t.put('paths/a/b', 'plain'); await t.put('paths/a//b', 'middle-empty'); await t.put('paths/a/b/', 'trailing-empty'); await t.put('paths/λ.txt', 'unicode');
  t.eq(await t.read(await t.get('paths/a/b'), 'text'), 'plain', 'ordinary path remains distinct');
  t.eq(await t.read(await t.get('paths/a//b'), 'text'), 'middle-empty', 'empty middle segment is preserved');
  t.eq(await t.read(await t.get('paths/a/b/'), 'text'), 'trailing-empty', 'empty final segment is preserved');
  const page = await t.list({ prefix: t.key('paths/'), limit: 10 });
  t.eq(page.objects.map(o => o.key).sort(), [t.key('paths/a//b'), t.key('paths/a/b'), t.key('paths/a/b/'), t.key('paths/λ.txt')].sort(), 'listing decodes keys without conflating empty or Unicode segments');
}
export async function I217(t) {
  const sha = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';
  const object = await t.put('checksum', 'abc', { sha256: sha });
  t.eq(t.hex(object.checksums.sha256), sha, 'supplied correct SHA-256 is retained as exact bytes');
  t.eq(t.hex(object.checksums.md5), '900150983cd24fb0d6963f7d28e17f72', 'single-part object records standard MD5');
  const h = await t.head('checksum');
  t.eq(h.checksums.toJSON(), { md5: '900150983cd24fb0d6963f7d28e17f72', sha256: sha }, 'head checksum JSON preserves both algorithm names and digests');
}
export async function I218(t) {
  const upload = await t.multipart('complete', { customMetadata: { workflow: 'complete' } });
  const part = await t.upload(upload, 1, 'one-final-part');
  t.eq(part.partNumber, 1, 'upload receipt names the submitted part');
  const object = await t.complete(upload, [part]);
  t.eq([object.key, object.size, object.customMetadata.workflow], [t.key('complete'), 14, 'complete'], 'completion reports assembled object and creation metadata');
  t.eq(await t.read(await t.get('complete'), 'text'), 'one-final-part', 'single final part becomes readable after completion');
}
export async function I219(t) {
  await t.put('abort', 'prior-object');
  const upload = await t.multipart('abort'); await t.upload(upload, 1, 'uncommitted-part');
  t.eq(await t.read(await t.get('abort'), 'text'), 'prior-object', 'incomplete multipart upload does not replace existing object');
  await t.abort(upload);
  t.eq(await t.read(await t.get('abort'), 'text'), 'prior-object', 'aborting upload preserves prior committed object');
  t.eq((await t.head('abort')).size, 12, 'prior object metadata remains after abort');
}
export async function I220(t) {
  const upload = await t.multipart('resume');
  const resumed = t.resume('resume', upload.uploadId);
  t.eq([resumed.key, resumed.uploadId], [t.key('resume'), upload.uploadId], 'same-node resumed handle names the same active upload');
  const part = await t.upload(resumed, 1, 'resumed-final');
  await t.complete(resumed, [part]); t.markUploadComplete(upload);
  t.eq(await t.read(await t.get('resume'), 'text'), 'resumed-final', 'same active-request resumed handle completes the original upload');
  t.eq((await t.head('resume')).size, 13, 'completed upload metadata reports exact bytes');
}
export const CASES = { I201, I202, I203, I204, I205, I206, I207, I208, I209, I210, I211, I212, I213, I214, I215, I216, I217, I218, I219, I220 };
