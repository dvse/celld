import { check, equal, poll, rejected, drop } from './fixture.js';

// Each literal function is an authored trace, never an argument/seed grid.
export const orderCases = {
  async O001(s) {
    const t = await s.target(); await s.alive(t); equal((await s.stats()).events, [], 'clean start');
    const first = s.watch(t.mark('before')), failed = s.watch(t.fail('middle')), last = s.watch(t.mark('after'));
    equal(await first, 'before', 'first result'); const error = await rejected(() => failed, 'planned:middle', 'synchronous middle failure'); equal(await last, 'after', 'later result');
    const state = await s.events(['main:mark:before', 'main:fail:middle', 'main:mark:after']); await s.alive(t); return { error, state };
  },
  async O002(s) {
    const t = await s.target(); await s.alive(t);
    const failed = s.watch(t.wait('failure', 'held', true)); await s.entered('main:enter:held');
    equal(await t.mark('while-held'), 'while-held', 'later invocation blocked by pending result');
    await s.events(['main:enter:held', 'main:mark:while-held']); await s.peer.release(s.tag, 'failure');
    const error = await rejected(() => failed, 'planned:held', 'asynchronous held failure');
    await t.mark('after-rejection'); const state = await s.events(['main:enter:held', 'main:mark:while-held', 'main:exit:held', 'main:mark:after-rejection']); return { error, state };
  },
  async O003(s) {
    const t = await s.target(); await s.alive(t); equal((await s.stats()).events, [], 'clean getter witness');
    const failed = s.watch(t.bad.then(value => value)), following = s.watch(t.mark('after-getter'));
    const error = await rejected(() => failed, 'planned:getter', 'getter dispatch failure'); await following;
    const state = await s.events(['main:getter', 'main:mark:after-getter']); await s.alive(t); return { error, state };
  },
  async O004(s) {
    const t = await s.target(); await t.mark('control'); const before = await s.stats();
    const error = await rejected(() => t.mark(Symbol('ordinary-uncloneable')), 'clone', 'argument encode before transport enqueue');
    equal((await s.stats()).events, before.events, 'rejected encode entered target');
    await t.mark('after-encode'); const state = await s.events(['main:mark:control', 'main:mark:after-encode']); await s.alive(t); return { error, state };
  },
  async O005(s) {
    const t = await s.target(), cb = s.callback('reverse', { action: () => t.mark('reentered') });
    equal(await t.reenter(cb.stub), 'reentered', 'same-capability reverse result');
    await s.events(['main:outer:start', 'main:mark:reentered', 'main:outer:end']); equal(cb.state.events, ['reverse:action'], 'reverse invocation count');
    await drop(cb.stub); await s.callbackDisposed(cb); await s.alive(t); return { callback: cb.state, state: await s.stats() };
  },
  async O006(s) {
    const a = await s.target('lane-a'), b = await s.target('lane-b');
    const held = s.watch(a.wait('a', 'held')); await s.entered('lane-a:enter:held');
    equal(await b.mark('independent'), 'independent', 'unrelated target waited on lane A completion');
    await s.events(['lane-a:enter:held', 'lane-b:mark:independent']); await s.peer.release(s.tag, 'a'); equal(await held, 'held', 'held result');
    await a.mark('resumed'); return await s.events(['lane-a:enter:held', 'lane-b:mark:independent', 'lane-a:exit:held', 'lane-a:mark:resumed']);
  },
  async O007(s) {
    const t = await s.target(), held = s.watch(t.wait('release-last', 'in-flight'));
    await s.entered('main:enter:in-flight'); await drop(t);
    const before = await s.stats(), error = await rejected(() => t.mark('forbidden'), 'disposed', 'disposed handle must not admit new work');
    equal((await s.stats()).events, before.events, 'disposed call reached target');
    await s.peer.release(s.tag, 'release-last'); equal(await held, 'in-flight', 'last stub disposal canceled an already-entered operation');
    const state = await s.disposed('main'); equal(state.events, ['main:enter:in-flight', 'main:exit:in-flight'], 'pending call effect count');
    const live = await s.target('fresh'); equal(await live.ping(), 'fresh', 'post-disposal root liveness'); return { error, state };
  },
  async O008(s) {
    const cb = s.callback('observer', { visit: value => { if (value === 'bad') throw new Error('planned:notification'); return value; } });
    await s.peer.retain(s.tag, 'stream', cb.stub); await s.peer.notify(s.tag, 'stream', 'first'); await s.peer.notify(s.tag, 'stream', 'bad'); await s.peer.notify(s.tag, 'stream', 'last');
    const state = await poll(() => s.stats(), x => x.events.includes('notified:last') && x.events.includes('notification-failed:bad'), 'notification completions');
    equal(cb.state.events, ['observer:first', 'observer:bad', 'observer:last'], 'notification invocation order'); equal(state.errors.length, 1, 'notification error count'); check(state.errors[0].includes('planned:notification'), 'notification wrong error');
    equal(await s.peer.emit(s.tag, 'stream', 'alive'), 'alive', 'notification failure poisoned retained callback'); await s.peer.remove(s.tag, 'stream'); await drop(cb.stub); await s.callbackDisposed(cb); return { state, callback: cb.state };
  },
  async O009(s) {
    const t = await s.target(), cb = s.callback('borrow');
    equal(await t.call(cb.stub, 'first'), 'borrow:first', 'borrowed call'); equal(cb.state.disposals, 0, 'callee disposed caller-owned original');
    equal(await cb.stub.visit('original'), 'borrow:original', 'original survives successful parameter cleanup');
    await drop(cb.stub); await s.callbackDisposed(cb); equal(cb.state.events, ['borrow:first', 'borrow:original'], 'borrow effects'); await s.alive(t); return cb.state;
  },
  async O010(s) {
    const t = await s.target(), cb = s.callback('never-called'); await s.alive(t); const before = await s.stats();
    const error = await rejected(() => t.rejectParameter(cb.stub), 'planned:parameter', 'callee rejection before callback');
    equal(cb.state.events, [], 'rejected callee invoked argument'); equal(cb.state.disposals, 0, 'callee rejection revoked original');
    equal((await s.stats()).events, [...before.events, 'main:reject-parameter'], 'callee entry count');
    equal(await cb.stub.visit('control'), 'never-called:control', 'callback survives exception'); await drop(cb.stub); await s.callbackDisposed(cb); await s.alive(t); return { error, callback: cb.state };
  },
  async O011(s) {
    const t = await s.target(), cb = s.callback('throws', { visit: value => { if (value === 'bad') throw new Error('planned:callback'); return value; } });
    equal(await t.call(cb.stub, 'control'), 'control', 'positive callback'); const before = await s.stats();
    const error = await rejected(() => t.call(cb.stub, 'bad'), 'planned:callback', 'reverse callback exception');
    equal((await s.stats()).events, [...before.events, 'main:call:bad'], 'reverse failure duplicated forward entry'); equal(cb.state.events, ['throws:control', 'throws:bad'], 'callback throw effects');
    equal(await t.call(cb.stub, 'after'), 'after', 'callback rejection poisoned next borrow'); await drop(cb.stub); await s.callbackDisposed(cb); await s.alive(t); return { error, callback: cb.state };
  },
  async O012(s) {
    const t = await s.target(), child = s.own(await t.child('child')); await drop(t); await s.disposed('main');
    equal(await child.mark('orphan-live'), 'orphan-live', 'parent disposal revoked independent child'); equal((await s.stats()).disposals.child ?? 0, 0, 'child disposed early');
    await drop(child); const state = await s.disposed('child'); equal(state.disposals, { main: 1, child: 1 }, 'independent target lifetimes'); return state;
  },
  async O013(s) {
    const t = await s.target(), a = s.own(t.dup()), b = s.own(a.dup());
    await drop(a); await drop(t); equal((await s.stats()).disposals, {}, 'ancestor dup disposal killed descendant');
    equal(await b.mark('last-branch'), 'last-branch', 'descendant duplicate stopped'); await drop(b); const state = await s.disposed('main'); equal(state.disposals.main, 1, 'duplicate cohort double release'); return state;
  },
  async O014(s) {
    const cb = s.callback('retained-on-error'); equal(cb.state.events, [], 'clean callback');
    const error = await rejected(() => s.peer.retain(s.tag, 'kept', cb.stub, true), 'planned:retain', 'retain followed by provider exception');
    equal((await s.stats()).events, ['retain:kept'], 'retain mutation missing or repeated'); await drop(cb.stub); equal(cb.state.disposals, 0, 'exception cleanup discarded retained duplicate');
    equal(await s.peer.emit(s.tag, 'kept', 'later'), 'retained-on-error:later', 'retained callback after rejection'); await s.peer.remove(s.tag, 'kept'); await s.callbackDisposed(cb); return { error, callback: cb.state };
  },
  async O015(s) {
    const tree = s.own(await s.peer.tree(s.tag)); await drop(tree.left); await s.disposed('left');
    equal(await tree.right.mark('survivor'), 'survivor', 'disposing one returned child killed sibling'); equal((await s.stats()).disposals.right ?? 0, 0, 'sibling disposed early');
    await drop(tree); const state = await s.disposed('right'); equal(state.disposals, { left: 1, right: 1 }, 'container repeated child disposal'); return state;
  },
  async O016(s) {
    const t = await s.target(); await t.mark('control'); await drop(t); await drop(t); const before = await s.disposed('main');
    const error = await rejected(() => t.mark('stale'), 'disposed', 'call after repeated handle disposal'); equal((await s.stats()).events, before.events, 'stale call effect'); equal((await s.stats()).disposals.main, 1, 'same handle released twice');
    const live = await s.target('replacement'); equal(await live.mark('live'), 'live', 'replacement target liveness'); return { error, before, after: await s.stats() };
  },
  async O017(s) {
    const t = await s.target(), sibling = s.own(t.dup()); await drop(t); const before = await s.stats();
    const error = await rejected(() => t.dup(), 'disposed', 'dup of dead handle'); equal(await s.stats(), before, 'failed dup changed target state');
    equal(await sibling.mark('still-owned'), 'still-owned', 'failed dup damaged sibling'); await drop(sibling); const state = await s.disposed('main'); return { error, state };
  },
  async O018(s) {
    const aliases = s.own(await s.peer.aliases(s.tag)), survivor = s.own(aliases.first.dup());
    equal(await aliases.first.ping(), 'alias', 'first alias'); equal(await aliases.second.ping(), 'alias', 'second alias');
    await drop(aliases); equal((await s.stats()).disposals.alias ?? 0, 0, 'aliased result disposal over-released duplicate');
    equal(await survivor.mark('survives-container'), 'survives-container', 'result alias cohort damaged'); await drop(survivor); return await s.disposed('alias');
  },
  async O019(s) {
    const cb = s.callback('aliased');
    equal(await s.peer.aliasParameters(s.tag, cb.stub, cb.stub), ['aliased:one', 'aliased:two'], 'repeated same argument routed incorrectly');
    equal(cb.state.disposals, 0, 'parameter alias cleanup consumed original twice'); equal(await cb.stub.visit('caller'), 'aliased:caller', 'original after repeated aliases');
    await drop(cb.stub); await s.callbackDisposed(cb); equal(cb.state.events, ['aliased:one', 'aliased:two', 'aliased:caller'], 'parameter alias effects'); return cb.state;
  },
  async O020(s) {
    const t = await s.target(), cb = s.callback('shared');
    const good = s.watch(t.holdBorrow(cb.stub, 'good', 'good')), bad = s.watch(t.holdBorrow(cb.stub, 'bad', 'bad', true));
    await s.entered('main:borrow:good'); await s.entered('main:borrow:bad'); await drop(cb.stub); await s.peer.release(s.tag, 'bad');
    const error = await rejected(() => bad, 'planned:bad', 'one overlapping borrow rejects'); equal(cb.state.disposals, 0, 'failed borrow released sibling pending lease'); equal(cb.state.events, [], 'bad branch called callback');
    await s.peer.release(s.tag, 'good'); equal(await good, 'shared:good', 'remaining borrow lost authority'); await s.callbackDisposed(cb); await s.alive(t); return { error, callback: cb.state, state: await s.stats() };
  },
  async O021(s) {
    const gate = s.localGate(), old = s.callback('old', { visit: () => gate.promise }), fresh = s.callback('new');
    await s.peer.retain(s.tag, 'active', old.stub); const pending = s.watch(s.peer.emit(s.tag, 'active', 'pending'));
    await poll(async () => old.state, x => x.events.includes('old:pending'), 'old callback entered'); await s.peer.retain(s.tag, 'active', fresh.stub); await drop(old.stub);
    equal(await s.peer.emit(s.tag, 'active', 'next'), 'new:next', 'replacement callback not active while old pending');
    gate.release('old-result'); equal(await pending, 'old-result', 'replacement canceled entered old callback'); await s.callbackDisposed(old);
    await s.peer.remove(s.tag, 'active'); await drop(fresh.stub); await s.callbackDisposed(fresh); return { old: old.state, fresh: fresh.state };
  },
  async O022(s) {
    const cb = s.callback('two-slots'); await s.peer.retain(s.tag, 'alpha', cb.stub); await s.peer.retain(s.tag, 'beta', cb.stub); await drop(cb.stub);
    await s.peer.remove(s.tag, 'alpha'); equal(cb.state.disposals, 0, 'removing alpha killed beta ownership');
    equal(await s.peer.emit(s.tag, 'alpha', 'missing'), 'absent', 'removed slot still calls'); equal(await s.peer.emit(s.tag, 'beta', 'live'), 'two-slots:live', 'remaining slot stopped');
    await s.peer.remove(s.tag, 'beta'); await s.callbackDisposed(cb); equal(cb.state.events, ['two-slots:live'], 'slot routing effects'); return cb.state;
  },
  async O023(s) {
    const old = s.callback('old'), fresh = s.callback('new'); await s.peer.retain(s.tag, 'one', old.stub); await drop(old.stub);
    equal(await s.peer.emit(s.tag, 'one', 'before'), 'old:before', 'old control'); await s.peer.retain(s.tag, 'one', fresh.stub); await s.callbackDisposed(old);
    equal(await s.peer.emit(s.tag, 'one', 'after'), 'new:after', 'replacement forwarded to stale target'); equal(old.state.events, ['old:before'], 'replaced callback invoked again');
    await s.peer.remove(s.tag, 'one'); await drop(fresh.stub); await s.callbackDisposed(fresh); return { old: old.state, fresh: fresh.state };
  },
  async O024(s) {
    const cb = s.callback('taken'); await s.peer.retain(s.tag, 'movable', cb.stub); await drop(cb.stub);
    const taken = s.own(await s.peer.take(s.tag, 'movable')); equal(await s.peer.emit(s.tag, 'movable', 'absent'), 'absent', 'transferred slot still retained');
    equal(await taken.visit('returned'), 'taken:returned', 'retained-to-result ownership transfer failed'); equal(cb.state.disposals, 0, 'transfer prematurely disposed callback');
    await drop(taken); await s.callbackDisposed(cb); equal(cb.state.events, ['taken:returned'], 'transfer effects'); return cb.state;
  },
  async O025(s) {
    const cb = s.callback('retained', { visit: value => { if (value === 'bad') throw new Error('planned:retained'); return value; } });
    await s.peer.retain(s.tag, 'retryable', cb.stub); await drop(cb.stub); equal(await s.peer.emit(s.tag, 'retryable', 'before'), 'before', 'retained positive control'); const before = await s.stats();
    const error = await rejected(() => s.peer.emit(s.tag, 'retryable', 'bad'), 'planned:retained', 'retained callback rejection'); equal((await s.stats()).events, [...before.events, 'emit:retryable:bad'], 'failed retained dispatch duplicated');
    equal(await s.peer.emit(s.tag, 'retryable', 'after'), 'after', 'callback rejection implicitly unsubscribed'); equal(cb.state.events, ['retained:before', 'retained:bad', 'retained:after'], 'retained error effects');
    await s.peer.remove(s.tag, 'retryable'); await s.callbackDisposed(cb); return { error, callback: cb.state };
  },
  async O026(s) {
    const cb = s.callback('self-remove', { visit: async () => { equal(await s.peer.remove(s.tag, 'self'), 'removed', 'reentrant unsubscribe'); return 'unsubscribed'; } });
    await s.peer.retain(s.tag, 'self', cb.stub); await drop(cb.stub);
    equal(await s.peer.emit(s.tag, 'self', 'once'), 'unsubscribed', 'reentrant unsubscribe canceled current callback'); await s.callbackDisposed(cb);
    equal(await s.peer.emit(s.tag, 'self', 'never'), 'absent', 'self-unsubscribed callback called again'); equal(cb.state.events, ['self-remove:once'], 'reentrant unsubscribe effect count'); return { callback: cb.state, state: await s.stats() };
  },
  async O027(s) {
    const gate = s.localGate(), cb = s.callback('pending-notify', { visit: () => gate.promise });
    await s.peer.retain(s.tag, 'notify', cb.stub); equal(await s.peer.notify(s.tag, 'notify', 'held'), 'queued', 'notification did not return without awaiting callback');
    await poll(async () => cb.state, x => x.events.length === 1, 'notification callback entered'); await s.peer.remove(s.tag, 'notify'); await drop(cb.stub);
    gate.release('done'); const state = await poll(() => s.stats(), x => x.events.includes('notified:held'), 'entered notification survives last release');
    equal(state.errors, [], 'pending notification rejected by release'); await s.callbackDisposed(cb); equal(await s.peer.emit(s.tag, 'notify', 'absent'), 'absent', 'released notification slot still active'); return { state, callback: cb.state };
  },
  async O028(s) {
    const t = await s.target(), leaf = s.callback('leaf'), parent = s.callback('parent', { child: () => leaf.stub.dup() });
    const returned = s.own(await t.callbackChild(parent.stub)); await drop(parent.stub); await s.callbackDisposed(parent); await drop(leaf.stub);
    equal(await returned.visit('after-parent'), 'leaf:after-parent', 'nested reverse returned capability lost after callback parameter scope'); equal(leaf.state.disposals, 0, 'result ownership lost');
    await drop(returned); await s.callbackDisposed(leaf); await s.alive(t); return { parent: parent.state, leaf: leaf.state, state: await s.stats() };
  },
  async O029(s) {
    const cb = s.callback('expired'); equal(await s.peer.borrowWithoutDup(s.tag, cb.stub), 'borrowed', 'store borrowed parameter'); const before = [...cb.state.events];
    const error = await rejected(() => s.peer.callBorrowed(s.tag), 'disposed', 'borrowed parameter retained without dup'); equal(cb.state.events, before, 'expired parameter reached target');
    equal(await cb.stub.visit('original'), 'expired:original', 'expired receiver invalidated caller original');
    await s.peer.retain(s.tag, 'proper', cb.stub); equal(await s.peer.emit(s.tag, 'proper', 'valid'), 'expired:valid', 'fresh dup retention failed'); await s.peer.remove(s.tag, 'proper'); await drop(cb.stub); await s.callbackDisposed(cb); return { error, callback: cb.state, state: await s.stats() };
  },
  async O030(s) {
    const t = await s.target(), destination = await s.target('destination'), cb = s.callback('forward');
    equal(await t.forward(destination, cb.stub), 'forward:forwarded', 'forwarded callback failed');
    equal(await destination.mark('still-owned'), 'still-owned', 'nested parameter dispatch moved caller target'); equal(await cb.stub.visit('caller'), 'forward:caller', 'nested forwarding moved caller callback');
    await s.events(['main:forward:start', 'destination:call:forwarded', 'main:forward:end', 'destination:mark:still-owned']);
    await drop(cb.stub); await s.callbackDisposed(cb); await s.alive(t); return { callback: cb.state, state: await s.stats() };
  },
  async O031(s) {
    const raw = s.callback('raw-twice'); raw.expectedDisposals = 3;
    // The separately constructed local stub is not sent. Two raw exports create distinct cohorts.
    await s.peer.retain(s.tag, 'first', raw.target); await s.peer.retain(s.tag, 'second', raw.target);
    await s.peer.remove(s.tag, 'first'); await s.callbackDisposed(raw, 1);
    equal(await s.peer.emit(s.tag, 'second', 'survivor'), 'raw-twice:survivor', 'separate raw-export cohort revoked sibling');
    await s.peer.remove(s.tag, 'second'); await s.callbackDisposed(raw, 2);
    await drop(raw.stub); await s.callbackDisposed(raw, 3); equal(raw.state.events, ['raw-twice:survivor'], 'raw cohort effects'); return raw.state;
  },
  async O032(s) {
    const tree = s.own(await s.peer.tree(s.tag)); await s.peer.retain(s.tag, 'child', tree.right); await drop(tree);
    await s.disposed('left'); equal((await s.stats()).disposals.right ?? 0, 0, 'container revoked remote retained child');
    const retained = s.own(await s.peer.take(s.tag, 'child')); equal(await retained.mark('retained-result'), 'retained-result', 'remote retained result missing');
    await drop(retained); const state = await s.disposed('right'); equal(state.disposals, { left: 1, right: 1 }, 'result tree and retained cohort counts'); return state;
  },
  async O033(s) {
    const t = await s.target(), promise = s.own(t.laterChild('publish', 'late'));
    // Promise disposal abandons ownership of its eventual result, not the entered method body.
    s.watch(promise); await s.entered('main:prepare:late'); await drop(promise); await s.peer.release(s.tag, 'publish');
    await poll(() => s.stats(), x => x.events.includes('main:publish:late'), 'producer completes after promise disposal');
    const state = await s.disposed('late'); equal(state.events, ['main:prepare:late', 'main:publish:late'], 'abandoned result producer effects'); await s.alive(t); return state;
  },
  async O034(s) {
    const t = await s.target(), promise = s.own(t.child('resolved')), child = s.own(await promise), survivor = s.own(child.dup());
    await drop(promise); const before = await s.stats(); const error = await rejected(() => child.mark('expired-result'), 'disposed', 'resolved promise owns result stub');
    equal((await s.stats()).events, before.events, 'disposed resolved result called target'); equal(before.disposals.resolved ?? 0, 0, 'result duplicate disposed early');
    equal(await survivor.mark('survives'), 'survives', 'result duplicate not independent of promise'); await drop(survivor); const state = await s.disposed('resolved'); await s.alive(t); return { error, state };
  },
  async O035(s) {
    const t = await s.target(), promise = s.own(t.laterChild('pipeline', 'unadmitted')); s.watch(promise);
    await s.entered('main:prepare:unadmitted'); await drop(promise); const before = await s.stats();
    const error = await rejected(() => promise.mark('must-not-enqueue'), 'disposed', 'pipeline call after pending promise disposal');
    equal((await s.stats()).events, before.events, 'disposed promise admitted new pipeline'); await s.peer.release(s.tag, 'pipeline');
    const state = await s.disposed('unadmitted'); equal(state.events, ['main:prepare:unadmitted', 'main:publish:unadmitted'], 'rejected pipeline effects'); await s.alive(t); return { error, state };
  },
  async O036(s) {
    const t = await s.target(), promise = s.own(t.laterChild('queued', 'queued-child')), queued = s.watch(promise.mark('already-enqueued'));
    await s.entered('main:prepare:queued-child'); await drop(promise); await s.peer.release(s.tag, 'queued');
    equal(await queued, 'already-enqueued', 'disposing producer promise canceled previously admitted pipeline call');
    const state = await s.disposed('queued-child'); equal(state.events, ['main:prepare:queued-child', 'main:publish:queued-child', 'queued-child:mark:already-enqueued'], 'queued pipeline effects'); await s.alive(t); return state;
  }
};
export const promiseDisposalCases = new Set(['O033', 'O034', 'O035', 'O036']);
