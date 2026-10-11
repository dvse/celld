// Handwritten public-API traces. Execute only in the direct-celld Worker.
export const cases = {
  async S201(t) {
    const writes = []; let closes = 0; let aborts = 0;
    const source = t.source([11, 12], true);
    const sink = t.sink({ write(value) { writes.push(value); }, close() { closes++; }, abort() { aborts++; } });
    const pipe = t.pipe(source, sink, { preventClose: true });
    const result = await pipe.promise;
    t.equal(result.status, 'fulfilled', 'pipe fulfills at source EOF');
    t.deep(writes, [11, 12], 'pipe transfers fixed prefix');
    t.equal(closes, 0, 'preventClose omits sink close');
    t.equal(aborts, 0, 'successful pipe does not abort sink');
    t.unlocked(source, sink, 'pipe releases both locks');
    await t.writeAndClose(sink, 13);
    t.deep(writes, [11, 12, 13], 'new writer reuses preserved sink');
    t.equal(closes, 1, 'explicit final close occurs once');
    t.unlocked(source, sink, 'reuse releases both locks');
  },

  async S202(t) {
    const reason = new Error('ordinary-source-failure');
    const accepted = t.gate('prefix-accepted');
    const writes = []; let aborts = 0; let closes = 0;
    const source = t.source([21], false);
    const sink = t.sink({ write(value) { writes.push(value); accepted.open(); }, abort() { aborts++; }, close() { closes++; } });
    const pipe = t.pipe(source, sink, { preventAbort: true });
    await accepted.promise;
    t.failSource(source, reason);
    const result = await pipe.promise;
    t.equal(result.status, 'rejected', 'source error rejects pipe');
    t.same(result.reason, reason, 'source error identity reaches pipe');
    t.equal(aborts, 0, 'preventAbort suppresses sink abort');
    t.unlocked(source, sink, 'errored pipe releases locks');
    await t.writeAndClose(sink, 22);
    t.deep(writes, [21, 22], 'sink accepts later independent write');
    t.equal(closes, 1, 'preserved sink closes once');
    t.unlocked(source, sink, 'reuse has no public locks');
  },

  async S203(t) {
    const reason = new Error('ordinary-sink-failure');
    const writes = []; let cancels = 0;
    const source = t.source([31], false, () => { cancels++; });
    const sink = t.sink({ write(value) { writes.push(value); throw reason; } });
    const result = await t.pipe(source, sink, { preventCancel: true }).promise;
    t.equal(result.status, 'rejected', 'sink error rejects pipe');
    t.same(result.reason, reason, 'sink error identity reaches pipe');
    t.equal(cancels, 0, 'preventCancel suppresses source cancellation');
    t.deep(writes, [31], 'only offered prefix reaches failed sink');
    t.unlocked(source, sink, 'failed pipe releases both locks');
    t.enqueue(source, 32); t.closeSource(source);
    t.deep(await t.drain(source), [32], 'source remains readable after failed pipe');
    t.equal(cancels, 0, 'source completes naturally without cancellation');
    t.unlocked(source, sink, 'manual drain releases source lock');
  },

  async S204(t) {
    const reason = new Error('ordinary-stop-pipe');
    const writeEntered = t.gate('write-entered'); const writeRelease = t.gate('write-release');
    const controller = new AbortController();
    const writes = []; let aborts = 0; let cancels = 0; let closes = 0;
    const source = t.source([41], false, () => { cancels++; });
    const sink = t.sink({ async write(value) { writes.push(value); if (value === 41) { writeEntered.open(); await writeRelease.promise; } }, abort() { aborts++; }, close() { closes++; } });
    const pipe = t.pipe(source, sink, { signal: controller.signal, preventAbort: true, preventCancel: true }, controller);
    await writeEntered.promise; controller.abort(reason);
    await t.checkpoint();
    t.equal(pipe.status, 'pending', 'signal shutdown waits for held write');
    writeRelease.open();
    const result = await pipe.promise;
    t.equal(result.status, 'rejected', 'signal stops pipe');
    t.same(result.reason, reason, 'signal identity survives prevented cleanup');
    t.deep([aborts, cancels, closes], [0, 0, 0], 'both resources preserved at pipe settlement');
    t.unlocked(source, sink, 'aborted pipe releases both locks');
    t.enqueue(source, 42); t.closeSource(source);
    t.deep(await t.drain(source), [42], 'source is independently drainable');
    await t.writeAndClose(sink, 43);
    t.deep(writes, [41, 43], 'sink is independently reusable');
    t.deep([aborts, cancels, closes], [0, 0, 1], 'only explicit sink close terminates preserved resources');
    t.unlocked(source, sink, 'reused resources end unlocked');
  },

  async S205(t) {
    const reason = new Error('stop-during-write');
    const writeEntered = t.gate('write-entered'); const writeRelease = t.gate('write-release');
    const abortEntered = t.gate('abort-entered'); const abortRelease = t.gate('abort-release');
    const cancelEntered = t.gate('cancel-entered'); const cancelRelease = t.gate('cancel-release');
    const controller = new AbortController(); const events = [];
    let abortReason; let cancelReason; let aborts = 0; let cancels = 0;
    const source = t.source([51], false, async reason => { cancels++; cancelReason = reason; events.push('cancel-enter'); cancelEntered.open(); await cancelRelease.promise; events.push('cancel-done'); });
    const sink = t.sink({ async write(value) { events.push('write-enter:' + value); writeEntered.open(); await writeRelease.promise; events.push('write-done'); }, async abort(reason) { aborts++; abortReason = reason; events.push('abort-enter'); abortEntered.open(); await abortRelease.promise; events.push('abort-done'); } });
    const pipe = t.pipe(source, sink, { signal: controller.signal }, controller);
    await writeEntered.promise; controller.abort(reason); await t.checkpoint();
    t.deep(events, ['write-enter:51'], 'cleanup cannot overtake held write');
    t.equal(pipe.status, 'pending', 'pipe stays pending during held write');
    writeRelease.open(); await Promise.all([abortEntered.promise, cancelEntered.promise]);
    t.before(events, 'write-done', 'abort-enter', 'write settles before sink abort');
    t.before(events, 'write-done', 'cancel-enter', 'write settles before source cancel');
    t.same(abortReason, reason, 'sink receives original signal reason');
    t.same(cancelReason, reason, 'source receives original signal reason');
    t.locked(source, sink, 'both locks retained during cleanup actions');
    abortRelease.open(); await t.checkpoint();
    t.equal(pipe.status, 'pending', 'source cancel completion is still required');
    cancelRelease.open(); const result = await pipe.promise;
    t.equal(result.status, 'rejected', 'completed signal shutdown rejects pipe');
    t.same(result.reason, reason, 'successful cleanup preserves signal reason');
    t.deep([aborts, cancels], [1, 1], 'each cleanup action runs exactly once');
    t.equal(events.includes('abort-done') && events.includes('cancel-done'), true, 'both asynchronous cleanup actions joined');
    t.unlocked(source, sink, 'cleanup completion releases both locks');
  },

  async S206(t) {
    const closeEntered = t.gate('close-entered'); const closeRelease = t.gate('close-release');
    const writes = []; let closes = 0;
    const source = t.source([61], true);
    const sink = t.sink({ write(value) { writes.push(value); }, async close() { closes++; closeEntered.open(); await closeRelease.promise; } });
    const pipe = t.pipe(source, sink);
    await closeEntered.promise; await t.checkpoint();
    t.deep(writes, [61], 'EOF follows completed data write');
    t.equal(pipe.status, 'pending', 'EOF pipe waits for sink close acknowledgment');
    t.locked(source, sink, 'locks remain while sink close is held');
    closeRelease.open(); const result = await pipe.promise;
    t.equal(result.status, 'fulfilled', 'sink close acknowledgment fulfills pipe');
    t.equal(closes, 1, 'sink close called exactly once');
    t.unlocked(source, sink, 'fulfilled pipe releases both locks');
  },

  async S207(t) {
    const controller = new AbortController(); controller.abort(0);
    let cancelReason; let abortReason; let cancels = 0; let aborts = 0; let writes = 0;
    const source = t.source([71], false, reason => { cancels++; cancelReason = reason; });
    const sink = t.sink({ write() { writes++; }, abort(reason) { aborts++; abortReason = reason; } });
    const result = await t.pipe(source, sink, { signal: controller.signal }, controller).promise;
    t.equal(result.status, 'rejected', 'pre-aborted pipe rejects');
    t.same(result.reason, 0, 'falsy signal reason is preserved exactly');
    t.same(cancelReason, 0, 'source cancellation receives falsy reason');
    t.same(abortReason, 0, 'sink abort receives falsy reason');
    t.deep([writes, cancels, aborts], [0, 1, 1], 'pre-abort transfers nothing and cleans both once');
    t.unlocked(source, sink, 'pre-abort leaves no pipe locks');
  },

  async S208(t) {
    const reason = new Error('pre-aborted-cleanup-join');
    const controller = new AbortController(); controller.abort(reason);
    const abortEntered = t.gate('abort-entered'); const abortRelease = t.gate('abort-release');
    const cancelEntered = t.gate('cancel-entered'); const cancelRelease = t.gate('cancel-release');
    let writes = 0; let abortDone = false; let cancelDone = false; let aborts = 0; let cancels = 0;
    const source = t.source([81], false, async () => { cancels++; cancelEntered.open(); await cancelRelease.promise; cancelDone = true; });
    const sink = t.sink({ write() { writes++; }, async abort() { aborts++; abortEntered.open(); await abortRelease.promise; abortDone = true; } });
    const pipe = t.pipe(source, sink, { signal: controller.signal }, controller);
    await Promise.all([abortEntered.promise, cancelEntered.promise]); await t.checkpoint();
    t.equal(pipe.status, 'pending', 'pre-abort waits for both cleanup actions');
    t.locked(source, sink, 'pre-abort keeps locks until cleanup joins');
    cancelRelease.open(); await t.checkpoint();
    t.equal(pipe.status, 'pending', 'sink abort completion is still required');
    abortRelease.open(); const result = await pipe.promise;
    t.equal(result.status, 'rejected', 'pre-abort rejects after actions finish');
    t.same(result.reason, reason, 'joined cleanup preserves signal error');
    t.deep([writes, aborts, cancels, abortDone, cancelDone], [0, 1, 1, true, true], 'no transfer and both cleanup completions witnessed');
    t.unlocked(source, sink, 'joined pre-abort releases locks');
  },

  async S209(t) {
    const signalReason = new Error('ordinary-signal-stop'); const cancelReason = new Error('ordinary-cancel-callback-failure');
    const accepted = t.gate('prefix-accepted'); const cancelEntered = t.gate('cancel-entered'); const cancelRelease = t.gate('cancel-release');
    const controller = new AbortController(); const writes = []; let aborts = 0; let closes = 0; let cancels = 0; let receivedReason;
    const source = t.source([91], false, async reason => { cancels++; receivedReason = reason; cancelEntered.open(); await cancelRelease.promise; throw cancelReason; });
    const sink = t.sink({ write(value) { writes.push(value); accepted.open(); }, abort() { aborts++; }, close() { closes++; } });
    const pipe = t.pipe(source, sink, { signal: controller.signal, preventAbort: true }, controller);
    await accepted.promise; controller.abort(signalReason); await cancelEntered.promise; await t.checkpoint();
    t.equal(pipe.status, 'pending', 'pipe waits for rejecting cancellation callback');
    cancelRelease.open(); const result = await pipe.promise;
    t.equal(result.status, 'rejected', 'failed cancellation rejects pipe');
    t.same(result.reason, cancelReason, 'cancel failure supersedes signal reason');
    t.same(receivedReason, signalReason, 'cancel callback still receives original signal reason');
    t.deep([aborts, cancels], [0, 1], 'preventAbort isolates one cancellation action');
    t.unlocked(source, sink, 'cancellation rejection releases locks');
    await t.writeAndClose(sink, 92);
    t.deep(writes, [91, 92], 'sink survives source cancellation failure');
    t.equal(closes, 1, 'surviving sink closes explicitly once');
    t.unlocked(source, sink, 'final cleanup leaves both unlocked');
  },
};
