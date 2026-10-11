export const cases = Object.freeze({
  async Y301(t) {
    // This is a default stream, not a byte stream or a host HTTP body. Its
    // deliberately single enqueued chunk survives default-stream tee as one
    // chunk per branch. The body clone must copy branch-two chunk storage.
    const source = t.stream(new ReadableStream({ start(controller) {
      controller.enqueue(Uint8Array.of(10, 20, 30, 40));
      controller.close();
    } }));
    const original = new Response(source);
    const copy = t.clone(original);
    const leftReader = t.reader(original.body);
    const rightReader = t.reader(copy.body);
    const first = await Promise.allSettled([t.read(leftReader), t.read(rightReader)]);
    t.deep(first.map(result => result.status), ['fulfilled', 'fulfilled'], 'both initial raw reads fulfill before mutation');
    t.deep(first.map(result => result.value.done), [false, false], 'one deliberate source chunk reaches each branch');
    t.deep(first.map(result => result.value.value instanceof Uint8Array), [true, true], 'both raw chunks are Uint8Array values');
    const left = first[0].value.value;
    const right = first[1].value.value;
    // Fresh primitive snapshots keep earlier evidence stable after mutation.
    t.deep([...left], [10, 20, 30, 40], 'original raw chunk has the fixed source bytes');
    t.deep([...right], [10, 20, 30, 40], 'clone raw chunk has the fixed source bytes');
    left[0] = 99;
    t.deep([...left], [99, 20, 30, 40], 'raw original chunk mutation takes effect locally');
    t.deep([...right], [10, 20, 30, 40], 'raw clone chunk retains its bytes after sibling mutation');
    t.equal(left.buffer === right.buffer, false, 'raw branch chunks use distinct ArrayBuffer storage');
    const eof = await Promise.allSettled([t.read(leftReader), t.read(rightReader)]);
    t.deep(eof.map(result => result.status), ['fulfilled', 'fulfilled'], 'both EOF reads fulfill before cleanup');
    t.deep(eof.map(result => result.value.done), [true, true], 'each branch reaches EOF immediately after its single chunk');
    t.deep(eof.map(result => result.value.value === undefined), [true, true], 'both terminal reads contain no extra value');
  },
});
