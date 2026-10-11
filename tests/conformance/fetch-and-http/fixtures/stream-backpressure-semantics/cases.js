// Six handwritten ordinary direct-celld traces. Never import into a reference runtime.
export const cases = Object.freeze({
  async S301(t) {
    const first = t.gate('first-write'); const second = t.gate('second-write'); const third = t.gate('third-write');
    const enteredFirst = t.gate('first-entered'); const enteredSecond = t.gate('second-entered'); const enteredThird = t.gate('third-entered');
    const bytes = []; const events = []; let active = 0; let maxActive = 0; let closes = 0; let aborts = 0;
    const stream = new WritableStream({
      write: t.callback('weighted-sink-write', chunk => {
        bytes.push([...chunk]); const n = bytes.length; active++; maxActive = Math.max(maxActive, active); events.push('write-' + n);
        const held = n === 1 ? first : n === 2 ? second : third;
        (n === 1 ? enteredFirst : n === 2 ? enteredSecond : enteredThird).open();
        return held.promise.then(() => { active--; events.push('done-' + n); });
      }),
      close: t.callback('weighted-sink-close', () => { closes++; events.push('close'); }),
      abort: t.callback('weighted-sink-abort', () => { aborts++; }),
    }, new ByteLengthQueuingStrategy({ highWaterMark: 3 }));
    const owner = t.writer(stream); const writer = owner.value;
    const ready0 = writer.ready; const initial = t.observe(ready0, 'ready-epoch-0');
    await t.value(initial);
    t.equal(writer.desiredSize, 3, 'initial weighted capacity is three');
    const a = t.write(owner, Uint8Array.of(11, 12), 'write-a');
    await enteredFirst.promise;
    t.equal(writer.desiredSize, 1, 'in-flight two-byte write retains its weight');
    t.same(writer.ready, ready0, 'below-pressure admission retains original ready promise');
    const b = t.write(owner, Uint8Array.of(13), 'write-b');
    const ready1 = writer.ready; const pressure1 = t.observe(ready1, 'ready-epoch-1');
    t.equal(writer.desiredSize, 0, 'two plus one bytes fill weighted capacity');
    t.equal(ready1 === ready0, false, 'threshold crossing allocates a new ready epoch');
    t.same(writer.ready, ready1, 'repeated ready getter retains pressured epoch');
    await t.checkpoint();
    t.deep([pressure1.status, a.status, b.status], ['pending', 'pending', 'pending'], 'ready and both writes remain pending at pressure');
    t.deep(events, ['write-1'], 'second callback is not admitted alongside held first');
    first.open();
    await t.value(a); await enteredSecond.promise; await t.value(pressure1);
    t.equal(writer.desiredSize, 2, 'first completion restores two units with second still in flight');
    t.equal(b.status, 'pending', 'ready fulfillment does not require held second write to finish');
    t.equal(second.opened, false, 'second callback gate remains closed when ready fulfills');
    t.same(writer.ready, ready1, 'fulfilled pressure epoch stays current below threshold');
    second.open(); await t.value(b);
    t.equal(writer.desiredSize, 3, 'full drain restores initial weighted capacity');
    const c = t.write(owner, Uint8Array.of(14, 15, 16), 'write-c');
    const ready2 = writer.ready; const pressure2 = t.observe(ready2, 'ready-epoch-2');
    await enteredThird.promise; await t.checkpoint();
    t.equal(writer.desiredSize, 0, 'final three-byte write reaches same fixed threshold');
    t.equal(ready2 === ready1 || ready2 === ready0, false, 'later threshold crossing creates a distinct third epoch');
    t.same(writer.ready, ready2, 'later pressured epoch is stable across getters');
    t.deep([pressure2.status, c.status], ['pending', 'pending'], 'later ready epoch is independently pending');
    third.open(); await t.value(c); await t.value(pressure2);
    t.equal(writer.desiredSize, 3, 'final completion restores capacity');
    await t.value(t.close(owner, 'weighted-close')); await t.value(owner.closed);
    t.deep(bytes, [[11, 12], [13], [14, 15, 16]], 'sink receives exact fixed bytes once in order');
    t.deep(events, ['write-1', 'done-1', 'write-2', 'done-2', 'write-3', 'done-3', 'close'], 'weighted trace has exact serialized callback order');
    t.deep([maxActive, closes, aborts], [1, 1, 0], 'one active callback and one successful close without abort');
    t.equal(writer.desiredSize, 0, 'closed writer has zero desired size');
    t.release(owner);
    t.equal(stream.locked, false, 'weighted writer lock released after settlement');
  },

  async S302(t) {
    const startGate = t.gate('sink-start'); const events = []; let starts = 0; let closes = 0; let aborts = 0;
    const startedPromise = startGate.promise.then(() => { events.push('start-done'); });
    const started = t.observe(startedPromise, 'actual-sink-start-result');
    const stream = new WritableStream({
      start: t.callback('sink-start-callback', () => { starts++; events.push('start'); return startedPromise; }),
      write: t.callback('sink-start-write', chunk => { events.push('write-' + chunk); }),
      close: t.callback('sink-start-close', () => { closes++; events.push('close'); }),
      abort: t.callback('sink-start-abort', () => { aborts++; }),
    });
    const owner = t.writer(stream); const writer = owner.value;
    const initialReady = t.observe(writer.ready, 'ready-before-sink-start');
    await t.value(initialReady);
    t.deep([starts, initialReady.status, started.status], [1, 'fulfilled', 'pending'], 'initial ready fulfills while successful sink start is held');
    t.equal(startGate.opened, false, 'initial readiness does not open sink start gate');
    const a = t.write(owner, 'A', 'start-queued-a'); const b = t.write(owner, 'B', 'start-queued-b');
    const close = t.close(owner, 'start-queued-close');
    await t.checkpoint();
    t.deep(events, ['start'], 'queued operations cannot enter callbacks before start completion');
    t.deep([a.status, b.status, close.status, owner.closed.status], ['pending', 'pending', 'pending', 'pending'], 'all admitted requests await held initialization');
    t.equal(closes, 0, 'underlying close has not entered during initialization');
    startGate.open(); await t.value(started);
    await t.value(a); await t.value(b); await t.value(close); await t.value(owner.closed);
    t.deep(events, ['start', 'start-done', 'write-A', 'write-B', 'close'], 'successful start release admits exact FIFO writes and close');
    t.deep([a.status, b.status, close.status, owner.closed.status], ['fulfilled', 'fulfilled', 'fulfilled', 'fulfilled'], 'queued promises all fulfill after initialization');
    t.deep([starts, closes, aborts], [1, 1, 0], 'one start one close and no abort');
    t.equal(writer.desiredSize, 0, 'successfully closed initialized writer has zero desired size');
    t.release(owner);
    t.equal(stream.locked, false, 'initialized writer lock released');
  },

  async S303(t) {
    const writeGate = t.gate('pressure-write'); const closeGate = t.gate('pressure-close');
    const writeEntered = t.gate('pressure-write-entered'); const closeEntered = t.gate('pressure-close-entered');
    const events = []; let writes = 0; let closes = 0; let aborts = 0;
    const stream = new WritableStream({
      write: t.callback('pressure-write-callback', chunk => {
        writes++; events.push('write-' + chunk); writeEntered.open();
        return writeGate.promise.then(() => { events.push('write-done'); });
      }),
      close: t.callback('pressure-close-callback', () => {
        closes++; events.push('close-enter'); closeEntered.open();
        return closeGate.promise.then(() => { events.push('close-done'); });
      }),
      abort: t.callback('pressure-abort-callback', () => { aborts++; }),
    });
    const owner = t.writer(stream); const writer = owner.value;
    const write = t.write(owner, 'held', 'pressure-write-request'); await writeEntered.promise;
    const ready = writer.ready; const pressured = t.observe(ready, 'close-relieved-ready');
    await t.checkpoint();
    t.deep([writer.desiredSize, pressured.status, write.status], [0, 'pending', 'pending'], 'entered held write creates genuine pressure before close');
    const close = t.close(owner, 'pressure-close-request');
    await t.value(pressured); events.push('ready-fulfilled');
    t.same(writer.ready, ready, 'close resolves the existing ready epoch rather than replacing it');
    t.deep([writer.desiredSize, writeGate.opened], [0, false], 'close lifts ready while full write weight and closed gate remain');
    t.deep([write.status, close.status, owner.closed.status], ['pending', 'pending', 'pending'], 'ready fulfillment is independent from write close and closed');
    t.deep(events, ['write-held', 'ready-fulfilled'], 'ready relief precedes write completion and close callback admission');
    t.equal(closes, 0, 'queued close cannot overtake held write');
    writeGate.open(); await t.value(write); await closeEntered.promise; await t.checkpoint();
    t.deep([write.status, close.status, owner.closed.status], ['fulfilled', 'pending', 'pending'], 'underlying close acknowledgment still gates terminal promises');
    t.deep(events, ['write-held', 'ready-fulfilled', 'write-done', 'close-enter'], 'close enters only after held write settles');
    closeGate.open(); await t.value(close); await t.value(owner.closed);
    t.deep(events, ['write-held', 'ready-fulfilled', 'write-done', 'close-enter', 'close-done'], 'exact close-relief transition order');
    t.deep([writes, closes, aborts], [1, 1, 0], 'normal ready relief uses one write one close and no abort');
    t.equal(writer.desiredSize, 0, 'closed pressure-relief writer has zero desired size');
    t.release(owner);
    t.equal(stream.locked, false, 'pressure-relief writer lock released');
  },

  async S304(t) {
    const startGate = t.gate('transform-start'); let starts = 0; let transforms = 0; let cancels = 0; const inputs = [];
    const startedPromise = startGate.promise.then(() => undefined);
    const started = t.observe(startedPromise, 'actual-transform-start-result');
    const stream = new TransformStream({
      start: t.callback('demand-transform-start', () => { starts++; return startedPromise; }),
      transform: t.callback('demand-transform', (chunk, controller) => { transforms++; inputs.push(chunk); controller.enqueue(chunk.toUpperCase() + '!'); }),
      cancel: t.callback('demand-transform-cancel', () => { cancels++; }),
    });
    const reader = t.reader(stream.readable); const writer = t.writer(stream.writable);
    startGate.open(); await t.value(started); await t.checkpoint();
    t.deep([starts, started.status], [1, 'fulfilled'], 'actual transformer start result settles before demand experiment');
    const firstWrite = t.write(writer, 'alpha', 'demand-write-alpha');
    await t.checkpoint();
    t.deep([transforms, firstWrite.status], [0, 'pending'], 'HWM0 blocks first transform and write without a read');
    const firstRead = t.read(reader, 'demand-read-alpha');
    const first = await t.value(firstRead); await t.value(firstWrite);
    t.deep(first, { value: 'ALPHA!', done: false }, 'first read admits exact first transform output');
    t.deep([transforms, firstWrite.status], [1, 'fulfilled'], 'one read admits exactly one completed transform');
    const secondWrite = t.write(writer, 'beta', 'demand-write-beta');
    await t.checkpoint();
    t.deep([transforms, secondWrite.status], [1, 'pending'], 'consumed output rearms demand gate before second transform');
    const secondRead = t.read(reader, 'demand-read-beta');
    const second = await t.value(secondRead); await t.value(secondWrite);
    t.deep(second, { value: 'BETA!', done: false }, 'second read admits exact second transform output');
    t.deep(inputs, ['alpha', 'beta'], 'transform callbacks receive exactly the two fixed inputs');
    await t.value(t.close(writer, 'demand-close')); await t.value(writer.closed);
    t.deep(await t.value(t.read(reader, 'demand-eof')), { value: undefined, done: true }, 'demand-gated transform ends after close');
    t.deep(await t.value(t.read(reader, 'demand-stable-eof')), { value: undefined, done: true }, 'demand-gated EOF is stable');
    await t.value(reader.closed);
    t.deep([transforms, cancels, reader.closed.status, writer.closed.status], [2, 0, 'fulfilled', 'fulfilled'], 'successful demand trace settles both sides without cancel');
    t.release(reader); t.release(writer);
    t.deep([stream.readable.locked, stream.writable.locked], [false, false], 'demand trace releases both public locks');
  },

  async S305(t) {
    const flushGate = t.gate('transform-flush'); const flushEntered = t.gate('transform-flush-entered');
    let transforms = 0; let flushes = 0; let cancels = 0; const events = [];
    const stream = new TransformStream({
      transform: t.callback('tail-transform', (chunk, controller) => { transforms++; events.push('transform-' + chunk); controller.enqueue('prefix:' + chunk); }),
      flush: t.callback('tail-flush', controller => {
        flushes++; events.push('flush-enter'); flushEntered.open();
        return flushGate.promise.then(() => { controller.enqueue('tail!'); events.push('tail-enqueued'); });
      }),
      cancel: t.callback('tail-cancel', () => { cancels++; }),
    });
    const reader = t.reader(stream.readable); const writer = t.writer(stream.writable);
    // Demand precedes waiting for write, so a correct HWM0 transform can progress.
    const prefixRead = t.read(reader, 'flush-prefix-read');
    const prefixWrite = t.write(writer, 'fixed', 'flush-prefix-write');
    const prefix = await t.value(prefixRead); await t.value(prefixWrite);
    t.deep(prefix, { value: 'prefix:fixed', done: false }, 'prefix is consumed with compatible HWM0 demand');
    t.equal(transforms, 1, 'exactly one ordinary transform precedes flush');
    const close = t.close(writer, 'flush-close'); await flushEntered.promise;
    const tailRead = t.read(reader, 'flush-tail-read'); await t.checkpoint();
    t.deep([transforms, flushes, cancels], [1, 1, 0], 'successful close enters one held flush');
    t.equal(flushGate.opened, false, 'flush tail gate is still closed during pending observations');
    t.deep([tailRead.status, close.status, reader.closed.status, writer.closed.status], ['pending', 'pending', 'pending', 'pending'], 'held flush owns tail read and both terminal states');
    t.deep(events, ['transform-fixed', 'flush-enter'], 'no tail or terminal event precedes flush release');
    flushGate.open();
    t.deep(await t.value(tailRead), { value: 'tail!', done: false }, 'released flush emits fixed tail before EOF');
    await t.value(close); await t.value(writer.closed);
    t.deep(await t.value(t.read(reader, 'flush-eof')), { value: undefined, done: true }, 'flush tail is followed by EOF');
    t.deep(await t.value(t.read(reader, 'flush-stable-eof')), { value: undefined, done: true }, 'flush EOF stays stable without duplicate tail');
    await t.value(reader.closed);
    t.deep(events, ['transform-fixed', 'flush-enter', 'tail-enqueued'], 'exact successful transform and flush output trace');
    t.deep([transforms, flushes, cancels, close.status, reader.closed.status, writer.closed.status], [1, 1, 0, 'fulfilled', 'fulfilled', 'fulfilled'], 'flush and both sides complete once without cancellation');
    t.release(reader); t.release(writer);
    t.deep([stream.readable.locked, stream.writable.locked], [false, false], 'flush trace releases both public locks');
  },

  async S306(t) {
    const firstGate = t.gate('first-pull-ack'); const secondGate = t.gate('second-pull-ack');
    const firstEntered = t.gate('first-pull-entered'); const secondEntered = t.gate('second-pull-entered');
    let controller; let pulls = 0; let closes = 0; let cancels = 0; let firstDesired; const events = [];
    const firstPromise = firstGate.promise.then(() => { events.push('first-pull-result-settled'); });
    const firstSettlement = t.observe(firstPromise, 'actual-first-pull-result');
    const stream = new ReadableStream({
      start: t.callback('weighted-source-start', value => { controller = value; }),
      pull: t.callback('weighted-source-pull', value => {
        pulls++;
        if (pulls === 1) {
          events.push('pull-1'); value.enqueue(Uint8Array.of(31, 32, 33, 34)); firstDesired = value.desiredSize; firstEntered.open();
          return firstPromise;
        }
        if (pulls === 2) {
          events.push('pull-2'); secondEntered.open();
          return secondGate.promise.then(() => { value.enqueue(Uint8Array.of(35, 36, 37, 38)); closes++; value.close(); events.push('source-close'); });
        }
        throw new Error('finite source received more than two pulls');
      }),
      cancel: t.callback('weighted-source-cancel', () => { cancels++; }),
    }, new ByteLengthQueuingStrategy({ highWaterMark: 4 }));
    const reader = t.reader(stream); await firstEntered.promise;
    t.equal(firstDesired, 0, 'one four-byte chunk exhausts weighted source capacity');
    t.equal(firstSettlement.status, 'pending', 'first returned pull promise is genuinely held');
    firstGate.open(); await t.value(firstSettlement); await t.checkpoint();
    t.equal(firstSettlement.status, 'fulfilled', 'actual returned pull promise settles before admission observation');
    t.equal(pulls, 1, 'settled full weighted queue admits no second pull before demand');
    t.equal(controller.desiredSize, 0, 'full weighted queue retains zero desired size without demand');
    t.deep(events, ['pull-1', 'first-pull-result-settled'], 'no refill entry before first dequeue');
    const first = await t.value(t.read(reader, 'weighted-source-first-read'));
    t.deep({ value: [...first.value], done: first.done }, { value: [31, 32, 33, 34], done: false }, 'first read returns exact first four bytes');
    await secondEntered.promise;
    t.equal(pulls, 2, 'dequeue admits exactly one weighted refill');
    t.equal(controller.desiredSize, 4, 'dequeue restores four units before held refill enqueue');
    t.equal(secondGate.opened, false, 'second refill remains independently held');
    secondGate.open();
    const second = await t.value(t.read(reader, 'weighted-source-second-read'));
    t.deep({ value: [...second.value], done: second.done }, { value: [35, 36, 37, 38], done: false }, 'refill returns exact second four bytes');
    t.deep(await t.value(t.read(reader, 'weighted-source-eof')), { value: undefined, done: true }, 'finite weighted source reaches EOF');
    t.deep(await t.value(t.read(reader, 'weighted-source-stable-eof')), { value: undefined, done: true }, 'weighted source EOF remains stable');
    await t.value(reader.closed);
    t.deep([pulls, closes, cancels, reader.closed.status], [2, 1, 0, 'fulfilled'], 'exact two pulls and one source close without cancellation');
    t.deep(events, ['pull-1', 'first-pull-result-settled', 'pull-2', 'source-close'], 'weighted source has exact bounded callback order');
    t.release(reader);
    t.equal(stream.locked, false, 'weighted source reader lock released');
  },
});
