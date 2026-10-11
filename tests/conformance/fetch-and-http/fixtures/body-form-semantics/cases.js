// Handwritten ordinary body/form cases. Run only in the deployed direct-celld Worker.
export const cases = Object.freeze({
  async Y201(t) {
    const backing = Uint8Array.of(250, 65, 66, 251);
    const view = new DataView(backing.buffer, 1, 2);
    const blob = new Blob(['é', view, new Blob([Uint8Array.of(0, 255)]), '!'], { type: 'APPLICATION/X-FIXTURE' });
    backing.fill(9);
    t.equal(blob.size, 7, 'mixed Blob parts concatenate exact visible bytes');
    t.equal(blob.type, 'application/x-fixture', 'Blob type is ASCII lowercased');
    t.deep([...new Uint8Array(await blob.arrayBuffer())], [195, 169, 65, 66, 0, 255, 33], 'Blob copies offset view before later caller mutation');
  },

  async Y202(t) {
    const blob = new Blob([Uint8Array.of(1, 2, 3, 4)]);
    const first = new Uint8Array(await blob.arrayBuffer());
    const second = new Uint8Array(await blob.arrayBuffer());
    first.fill(99);
    t.deep([...second], [1, 2, 3, 4], 'separate Blob reads return independent buffers');
    const bytes = await blob.bytes();
    bytes[1] = 77;
    t.deep([...new Uint8Array(await blob.arrayBuffer())], [1, 2, 3, 4], 'mutating bytes result cannot alter immutable Blob storage');
    t.equal(first.buffer === second.buffer, false, 'arrayBuffer reads do not share ownership');
    t.equal(blob.size, 4, 'repeated reads do not consume Blob');
  },

  async Y203(t) {
    const blob = new Blob(['0123456789'], { type: 'text/plain' });
    const middle = blob.slice(-5, -1, 'APPLICATION/X-SLICE');
    t.equal(await middle.text(), '5678', 'negative endpoints are relative to Blob size');
    t.equal(middle.type, 'application/x-slice', 'slice has independently normalized content type');
    t.equal(middle.size, 4, 'slice has exact byte length');
    t.equal(await blob.slice(8, 3).text(), '', 'reversed range yields empty Blob');
    t.equal(await blob.slice(-99, 3).text(), '012', 'negative start clamps to beginning');
    t.equal(blob.slice(0, 2).type, '', 'omitted slice type does not inherit source type');
    t.equal(await blob.text(), '0123456789', 'slicing leaves source bytes unchanged');
  },

  async Y204(t) {
    const blob = new Blob(['independent']);
    const abandoned = t.stream(blob.stream());
    const kept = t.stream(blob.stream());
    await abandoned.cancel('ordinary-unused-copy');
    const reader = t.reader(kept.getReader());
    const content = await t.readAll(reader);
    t.deep(content, [105, 110, 100, 101, 112, 101, 110, 100, 101, 110, 116], 'cancelling one Blob stream does not poison another stream');
    t.equal(await blob.text(), 'independent', 'Blob remains readable after stream cancellation');
    t.equal(blob.size, 11, 'stream lifecycle does not change Blob value');
  },

  async Y205(t) {
    const file = new File(['hello'], 'original.txt', { type: 'TEXT/PLAIN', lastModified: 123456789 });
    const form = new FormData();
    form.append('unchanged', file);
    form.append('renamed', file, 'upload.txt');
    form.append('default', new Blob(['raw'], { type: 'APPLICATION/X-RAW' }));
    t.equal(form.get('unchanged') === file, true, 'File append without filename preserves File identity');
    const renamed = form.get('renamed');
    t.equal(renamed instanceof File && renamed !== file, true, 'explicit filename creates a renamed File');
    t.equal(renamed.name, 'upload.txt', 'explicit upload filename');
    t.equal(renamed.lastModified, 123456789, 'renaming preserves File lastModified');
    t.equal(renamed.type, 'text/plain', 'renaming preserves normalized type');
    t.equal(await renamed.text(), 'hello', 'renaming preserves bytes');
    t.equal(file.name, 'original.txt', 'original File metadata unchanged');
    t.equal(form.get('default').name, 'blob', 'plain Blob becomes File with default name');
    t.equal(form.get('default').type, 'application/x-raw', 'Blob-to-File entry retains type');
  },

  async Y206(t) {
    const retained = new File(['keep'], 'keep.txt', { lastModified: 10 });
    const form = new FormData();
    form.append('asset', 'placeholder');
    form.append('other', retained);
    form.append('asset', new File(['old'], 'old.txt', { lastModified: 20 }));
    form.append('tail', 'end');
    form.set('asset', new Blob([Uint8Array.of(7, 8)], { type: 'application/x-pair' }), 'pair.bin');
    t.deep([...form.keys()], ['asset', 'other', 'tail'], 'mixed-type set replaces first position and removes later duplicate entries');
    t.equal(form.getAll('asset').length, 1, 'set leaves one asset entry');
    t.equal(form.get('asset') instanceof File, true, 'Blob replacement uses File entry conversion');
    t.equal(form.get('asset').name, 'pair.bin', 'replacement filename retained');
    t.deep([...new Uint8Array(await form.get('asset').arrayBuffer())], [7, 8], 'replacement file bytes');
    t.equal(form.get('other') === retained, true, 'unrelated File identity preserved');
    t.equal(form.get('tail'), 'end', 'unrelated string entry preserved');
  },

  async Y207(t) {
    const response = t.body(new Response(Uint8Array.of(0, 255, 128, 65), { headers: { 'content-type': 'APPLICATION/OCTET-STREAM' } }));
    const blob = await t.consume(response, 'blob');
    t.equal(blob instanceof Blob, true, 'Response.blob returns a Blob value');
    t.equal(blob.type, 'application/octet-stream', 'body MIME type becomes normalized Blob type');
    t.equal(blob.size, 4, 'body-to-Blob conversion keeps exact byte length');
    t.deep([...new Uint8Array(await blob.arrayBuffer())], [0, 255, 128, 65], 'binary response bytes do not pass through text decoding');
    t.equal(response.bodyUsed, true, 'Response.blob consumes the response body');
    t.deep([...new Uint8Array(await blob.arrayBuffer())], [0, 255, 128, 65], 'resulting Blob remains independently readable');
  },

  async Y208(t) {
    const form = new FormData();
    form.append('name', 'before');
    form.append('count', '2');
    const request = t.body(new Request('https://upload.example.test/form', { method: 'POST', body: form }));
    const copy = t.clone(request);
    t.body(request);
    form.set('name', 'after');
    form.append('extra', 'late');
    const boundary = t.boundary(request.headers.get('content-type'));
    const wire = await t.consume(copy, 'text');
    t.deep(t.multipartTextParts(wire, boundary), [['name', 'before'], ['count', '2']], 'independent multipart framing oracle sees construction-time entries');
    t.equal(request.bodyUsed, false, 'consuming clone leaves original request unconsumed');
    const parsed = await t.consume(request, 'formData');
    t.deep([...parsed], [['name', 'before'], ['count', '2']], 'original multipart request parses its construction-time entries');
    t.equal(parsed.has('extra'), false, 'later FormData additions cannot alter extracted request body');
  },

  async Y209(t) {
    const payload = new Blob([
      '--BodyBinary\r\nContent-Disposition: form-data; name="upload"; filename="bytes.bin"\r\nContent-Type: application/octet-stream\r\n\r\n',
      Uint8Array.of(0, 255, 128, 13, 10, 65),
      '\r\n--BodyBinary\r\nContent-Disposition: form-data; name="caption"\r\n\r\ncafé\r\n--BodyBinary--\r\n',
    ]);
    const response = t.body(new Response(payload, { headers: { 'content-type': 'multipart/form-data; boundary=BodyBinary' } }));
    const form = await t.consume(response, 'formData');
    const file = form.get('upload');
    t.deep([...form.keys()], ['upload', 'caption'], 'multipart byte scanner retains part order');
    t.equal(file instanceof File, true, 'filename parameter creates File value');
    t.equal(file.name, 'bytes.bin', 'file name decoded from part header');
    t.equal(file.type, 'application/octet-stream', 'file part type preserved');
    t.deep([...new Uint8Array(await file.arrayBuffer())], [0, 255, 128, 13, 10, 65], 'binary file bytes are never UTF-8 replaced');
    t.equal(form.get('caption'), 'café', 'text part is UTF-8 decoded independently');
  },

  async Y210(t) {
    const response = t.body(new Response('--MarkerLine\r\nContent-Disposition: form-data; name="file"; filename="notes.txt"\r\nContent-Type: text/plain\r\n\r\nprefix--MarkerLine-suffix\r\nsecond line\r\n--MarkerLine--\r\n', { headers: { 'content-type': 'multipart/form-data; boundary=MarkerLine' } }));
    const form = await t.consume(response, 'formData');
    t.equal([...form.keys()].length, 1, 'mid-line boundary-looking text does not create another part');
    t.equal(await form.get('file').text(), 'prefix--MarkerLine-suffix\r\nsecond line', 'scanner recognizes delimiters only at line start');
    t.equal(form.get('file').name, 'notes.txt', 'file metadata survives embedded marker text');
  },

  async Y211(t) {
    const response = t.body(new Response('--ParamOrder\r\nContent-Disposition: form-data; filename="report.txt"; name="upload"\r\nContent-Type: text/plain\r\n\r\nreport\r\n--ParamOrder--\r\n', { headers: { 'content-type': 'multipart/form-data; boundary="ParamOrder"' } }));
    const form = await t.consume(response, 'formData');
    t.deep([...form.keys()], ['upload'], 'name parameter matches complete parameter despite filename preceding it');
    t.equal(form.get('report.txt'), null, 'filename is not confused with field name');
    t.equal(form.get('upload').name, 'report.txt', 'quoted boundary and reordered disposition parameters parse');
    t.equal(await form.get('upload').text(), 'report', 'reordered headers preserve payload');
  },

  async Y212(t) {
    const form = new FormData();
    form.append('note', 'first\nsecond\rthird\r\nfourth');
    const request = t.body(new Request('https://upload.example.test/notes', { method: 'POST', body: form }));
    const boundary = t.boundary(request.headers.get('content-type'));
    const wire = await t.consume(request, 'text');
    t.deep(t.multipartTextParts(wire, boundary), [['note', 'first\r\nsecond\r\nthird\r\nfourth']], 'multipart text field line breaks normalize to CRLF');
    t.equal(form.get('note'), 'first\nsecond\rthird\r\nfourth', 'wire normalization does not mutate original FormData value');
  },

  async Y213(t) {
    const params = new URLSearchParams([['event', 'launch'], ['count', '2']]);
    const request = t.body(new Request('https://upload.example.test/event', { method: 'POST', body: params }));
    const copy = t.clone(request);
    t.body(request);
    params.set('event', 'changed');
    t.equal(request.headers.get('content-type'), 'application/x-www-form-urlencoded;charset=UTF-8', 'URLSearchParams BodyInit infers its form media type');
    t.equal(await t.consume(copy, 'text'), 'event=launch&count=2', 'typed extraction snapshots URLSearchParams serialization');
    const form = await t.consume(request, 'formData');
    t.equal(form instanceof FormData, true, 'Body formData dispatch recognizes inferred media type');
    t.deep([...form], [['event', 'launch'], ['count', '2']], 'typed body parses to FormData rather than re-reading source params');
    t.equal(request.bodyUsed, true, 'form body consumer marks request used');
  },

  async Y214(t) {
    const original = t.body(new Request('https://upload.example.test/transfer', { method: 'POST', body: 'inherited' }));
    const moved = t.requestFrom(original);
    t.equal(original.bodyUsed, true, 'constructing from Request without replacement transfers its body');
    t.equal(moved.bodyUsed, false, 'new Request owns an initially unused transferred body');
    t.equal(await t.consume(moved, 'text'), 'inherited', 'transferred body retains payload');
    const source = t.body(new Request('https://upload.example.test/override', { method: 'POST', body: 'old' }));
    const replacement = t.requestFrom(source, { body: 'new' });
    t.equal(source.bodyUsed, false, 'explicit replacement body leaves prior body undisturbed');
    t.equal(await t.consume(source, 'text'), 'old', 'original remains consumable when body is overridden');
    t.equal(await t.consume(replacement, 'text'), 'new', 'replacement body is used by new Request');
  },

  async Y215(t) {
    const response = t.body(new Response(Uint8Array.of(9, 8, 7), { status: 201, statusText: 'Created', headers: { 'x-mode': 'original' } }));
    const copy = t.clone(response);
    t.body(response);
    copy.headers.set('x-mode', 'copy');
    t.equal(response.headers.get('x-mode'), 'original', 'response clone owns a separate header list');
    t.equal(copy.status, 201, 'response clone preserves status');
    t.equal(copy.statusText, 'Created', 'response clone preserves statusText');
    const copied = new Uint8Array(await t.consume(copy, 'arrayBuffer'));
    copied.fill(0);
    t.equal(response.bodyUsed, false, 'consuming clone leaves source body unused');
    t.deep([...new Uint8Array(await t.consume(response, 'arrayBuffer'))], [9, 8, 7], 'clone consumer buffer edits cannot alter source body');
    t.equal(copy.bodyUsed, true, 'clone consumed state is independent');
  },

  async Y216(t) {
    const value = { order: 7, tags: ['ready'] };
    const response = t.body(Response.json(value, { status: 202, headers: { 'x-job': 'queued' } }));
    value.order = 99;
    value.tags.push('late');
    t.equal(response.status, 202, 'Response.json retains supplied status');
    t.equal(response.headers.get('content-type'), 'application/json', 'Response.json provides JSON content type');
    t.equal(response.headers.get('x-job'), 'queued', 'Response.json preserves supplied metadata');
    t.equal(await t.consume(response, 'text'), '{"order":7,"tags":["ready"]}', 'JSON response serializes object once at construction');
    t.equal(response.bodyUsed, true, 'JSON response body consumption is tracked');
  },

  async Y217(t) {
    const response = t.body(new Response(null, { status: 204 }));
    t.equal(response.body, null, 'null Response has no stream');
    t.equal(await t.consume(response, 'text'), '', 'consuming absent body yields empty text');
    t.equal(response.bodyUsed, false, 'absent body cannot become disturbed');
    t.equal((await t.consume(response, 'arrayBuffer')).byteLength, 0, 'null body remains available as empty bytes');
    t.equal(response.bodyUsed, false, 'second null-body conversion still has no disturbed stream');
    const request = t.body(new Request('https://upload.example.test/empty', { method: 'POST' }));
    t.equal(request.body, null, 'POST with no BodyInit has absent rather than empty-stream body');
    t.equal(request.bodyUsed, false, 'bodyless Request starts unused');
  },

  async Y218(t) {
    const response = t.body(new Response(Uint8Array.of(21, 22, 23)));
    const reader = t.reader(response.body.getReader());
    t.equal(response.bodyUsed, false, 'acquiring a reader alone does not disturb body');
    const first = await reader.read();
    t.equal(first.done, false, 'nonempty body provides bytes before EOF');
    t.equal(response.bodyUsed, true, 'direct reader consumption is reflected by Body.bodyUsed');
    const all = await t.readAll(reader, first.value);
    t.deep(all, [21, 22, 23], 'body state tracking does not change payload');
    t.equal(response.bodyUsed, true, 'disturbed state persists at EOF');
  },

  async Y219(t) {
    const inferred = t.body(new Response('hello'));
    const explicit = t.body(new Response('hello', { headers: { 'content-type': 'text/x-fixture' } }));
    const request = t.body(new Request('https://upload.example.test/text', { method: 'POST', body: 'hello' }));
    t.equal(inferred.headers.get('content-type'), 'text/plain;charset=UTF-8', 'string Response BodyInit infers text media type');
    t.equal(request.headers.get('content-type'), 'text/plain;charset=UTF-8', 'string Request BodyInit infers text media type');
    t.equal(explicit.headers.get('content-type'), 'text/x-fixture', 'explicit content type takes precedence over inferred type');
    t.equal(await t.consume(inferred, 'text'), 'hello', 'inference does not alter string body');
    t.equal(await t.consume(request, 'text'), 'hello', 'request extraction retains string bytes');
    t.equal(await t.consume(explicit, 'text'), 'hello', 'explicit media type does not transcode body');
  },

  async Y220(t) {
    const stream = t.stream(new ReadableStream({ start(controller) {
      controller.enqueue(Uint8Array.of(10, 20));
      controller.enqueue(Uint8Array.of(30, 40));
      controller.close();
    } }));
    const response = t.body(new Response(stream, { status: 203, headers: { 'x-origin': 'local-stream' } }));
    const copy = t.clone(response);
    t.body(response); // Register the replacement branch if clone tees the original.
    t.equal(response.bodyUsed, false, 'cloning leaves original response body unused');
    t.equal(copy.bodyUsed, false, 'cloned streaming response starts unused');
    const results = await Promise.allSettled([t.consume(response, 'arrayBuffer'), t.consume(copy, 'arrayBuffer')]);
    t.deep(results.map(result => result.status), ['fulfilled', 'fulfilled'], 'both finite clone consumers settle successfully before cleanup');
    t.deep([...new Uint8Array(results[0].value)], [10, 20, 30, 40], 'original branch has complete finite local payload');
    t.deep([...new Uint8Array(results[1].value)], [10, 20, 30, 40], 'cloned branch has complete finite local payload');
    t.equal(copy.status, 203, 'streaming clone preserves response status');
    t.equal(copy.headers.get('x-origin'), 'local-stream', 'streaming clone preserves ordinary metadata');
  },
});
