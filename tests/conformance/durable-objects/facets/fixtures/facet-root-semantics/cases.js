export const CASES = {
  async Z201(s, t) {
    const facet = s.local('inherited');
    const direct = await facet.identity();
    const nested = await facet.descendantIdentity('leaf');
    t.deep(direct, { kind: 'DurableObjectId', value: String(s.ctx.id), name: s.ctx.id.name }, 'facet inherits named root identity');
    t.deep(nested, direct, 'omitted nested ID inherits immediate parent identity with name');
  },
  async Z202(s, t) {
    const named = s.env.ROOT.idFromName('display-only');
    const a = s.local('named', {}, named), b = s.local('literal', {}, 'literal-display');
    t.deep(await a.identity(), { kind: 'DurableObjectId', value: String(named), name: 'display-only' }, 'explicit namespace ID retains named ID kind');
    t.deep(await b.identity(), { kind: 'string', value: 'literal-display', name: null }, 'explicit string remains a string');
    t.deep(await b.descendantIdentity('leaf'), { kind: 'string', value: 'literal-display', name: null }, 'nested omitted ID inherits overridden string rather than root ID');
    t.deep(await a.descendantIdentity('leaf', 'child-display'), { kind: 'string', value: 'child-display', name: null }, 'child override replaces immediate parent display identity');
  },
  async Z203(s, t) {
    const facet = s.local('receiver');
    const first = await (await facet.fetch('https://owned.fixture.invalid/first')).json();
    const second = await facet.step('rpc');
    const third = await (await facet.fetch('https://owned.fixture.invalid/third')).json();
    t.deep([first.heap, second.heap, third.heap], [1, 2, 3], 'fetch and RPC share one facet instance heap');
    t.deep([first.count, second.count, third.count], [1, 2, 3], 'both dispatch surfaces share facet storage');
    t.same(first.birth, second.birth, 'RPC uses the fetch-constructed instance');
    t.same(second.birth, third.birth, 'later fetch retains the same receiver');
  },
  async Z204(s, t) {
    const facet = s.loaded('plain', 'Plain', { label: 'plain-startup' });
    const a = await (await facet.fetch('https://owned.fixture.invalid/plain')).json();
    const b = await facet.increment();
    t.deep(a, { calls: 1, stored: 1, label: 'plain-startup', origin: 'loaded-origin' }, 'plain constructor receives facet state, props and loader environment');
    t.deep(b, { calls: 2, stored: 2, label: 'plain-startup', origin: 'loaded-origin' }, 'js_rpc dispatch reuses plain facet constructor and storage');
  },
  async Z205(s, t) {
    s.ctx.storage.kv.put('level', 100);
    const facet = s.local('one');
    t.deep(await facet.chain(['two', 'three'], [10, 20, 30]), [10, 20, 30], 'three descendant levels execute below root at supported depth four');
    t.deep(await facet.chainRead(['two', 'three']), [10, 20, 30], 'all permitted hierarchy levels retain independent values');
    t.same(s.ctx.storage.kv.get('level'), 100, 'deep hierarchy does not overwrite root level');
  },
  async Z206(s, t) {
    const left = s.local('left'), right = s.local('right');
    await left.childPut('settings', 'value', 'left-settings');
    await right.childPut('settings', 'value', 'right-settings');
    t.same(await left.childRead('settings', 'value'), 'left-settings', 'left parent path selects left settings');
    t.same(await right.childRead('settings', 'value'), 'right-settings', 'right parent path selects right settings');
    t.deep(await left.descendantIdentity('settings'), await right.descendantIdentity('settings'), 'equal inherited display IDs do not collapse nested storage paths');
  },
  async Z207(s, t) {
    const literal = s.local('workspace/tools'), branch = s.local('workspace');
    await literal.put('value', 'literal-name');
    await branch.childPut('tools', 'value', 'nested-path');
    t.same(await literal.read('value'), 'literal-name', 'slash-containing legal facet name is one component');
    t.same(await branch.childRead('tools', 'value'), 'nested-path', 'two-component nested path remains independent');
  },
  async Z208(s, t) {
    s.ctx.storage.sql.exec('CREATE TABLE shared (number INTEGER NOT NULL)').toArray();
    s.ctx.storage.sql.exec('INSERT INTO shared VALUES (7)').toArray();
    const facet = s.local('schema');
    t.deep(await facet.schema('text'), { columns: ['label'], rows: [{ label: 'facet-row' }] }, 'facet can own incompatible same-named table schema');
    t.deep(await facet.childSchema('leaf', 'blob'), { columns: ['payload'], rows: [{ payload: [1, 2] }] }, 'nested facet has third independent schema catalog');
    t.deep(s.ctx.storage.sql.exec('SELECT * FROM shared').toArray(), [{ number: 7 }], 'root schema and row remain unchanged');
    t.deep(await facet.schemaState(), { columns: ['label'], rows: [{ label: 'facet-row' }] }, 'grandchild DDL did not alter parent schema');
  },
  async Z209(s, t) {
    const template = s.ctx.exports.Facet({ props: { label: 'persistent-props' } });
    const a = s.custom('active', () => ({ class: template }));
    t.deep(await a.mutateProps(), { label: 'persistent-props', visits: 1, initialLabel: 'persistent-props' }, 'first facet turn mutates startup props');
    t.deep(await a.mutateProps(), { label: 'persistent-props', visits: 2, initialLabel: 'persistent-props' }, 'facet props belong to persistent receiver across turns');
    const b = s.custom('fresh', () => ({ class: template }));
    t.deep(await b.propsState(), { label: 'persistent-props', visits: 0, initialLabel: 'persistent-props' }, 'second facet gets pristine class-template props');
  },
  async Z210(s, t) {
    const shared = { key: 'shared' };
    const props = { date: new Date('2026-01-02T03:04:05.000Z'), bigint: 9007199254740993n, bytes: new Uint16Array([17, 513]), shared, map: new Map([[shared, 9]]), set: new Set([shared]) };
    props.self = props;
    const facet = s.loaded('typed', 'Facet', props);
    t.deep(await facet.typedAtConstruction(), { date: '2026-01-02T03:04:05.000Z', dateBrand: true, bigint: '9007199254740993', bytes: [17, 513], bytesBrand: true, mapBrand: true, setBrand: true, alias: true, cycle: true, score: 9 }, 'native facet startup decoding preserves typed graph before constructor');
  },
  async Z211(s, t) {
    await s.ctx.storage.put('startup-config', { label: 'saved-v1' });
    let startups = 0;
    const facet = s.custom('config', async () => {
      startups++;
      const props = await s.ctx.storage.get('startup-config');
      return { class: s.ctx.exports.Facet({ props }) };
    });
    await s.ctx.storage.put('startup-config', { label: 'saved-v2' });
    t.same(startups, 0, 'get alone does not resolve persisted startup configuration');
    t.deep(await facet.propsState(), { label: 'saved-v2', visits: 0, initialLabel: 'saved-v2' }, 'async startup reads committed supervisor config before constructor');
    await s.ctx.storage.put('startup-config', { label: 'saved-v3' });
    t.deep(await facet.propsState(), { label: 'saved-v2', visits: 0, initialLabel: 'saved-v2' }, 'later supervisor edits do not silently reconfigure running facet');
    t.same(startups, 1, 'one completed asynchronous configuration read');
  },
  async Z212(s, t) {
    const parent = s.local('relay', { label: 'supervisor-child' });
    const response = await parent.fetch('https://owned.fixture.invalid/relay/leaf?tag=job-7', { method: 'POST', headers: { 'x-route': 'root-to-child' }, body: 'work-item' });
    t.same(response.status, 202, 'nested facet response status crosses both dispatch edges');
    t.same(response.headers.get('x-parent-scope'), 'supervisor-child', 'parent receives and annotates child response');
    t.same(response.headers.get('x-child-scope'), 'leaf', 'child response header retained');
    t.deep(await response.json(), { method: 'POST', tag: 'job-7', route: 'root-to-child', body: 'work-item' }, 'nested fetch forwards ordinary request method, URL, header and body');
    t.same(await parent.childRead('leaf', 'echo'), 'work-item', 'nested fetch reaches expected descendant database');
    t.same(await parent.read('echo'), null, 'parent never receives child request write');
  },
  async Z213(s, t) {
    const facet = s.local('transaction');
    await s.ctx.storage.transaction(async tx => {
      await tx.put('root-row', 'tentative-root');
      await facet.put('facet-row', 'committed-facet');
      tx.rollback();
    });
    t.same(await s.ctx.storage.get('root-row') ?? null, null, 'explicit application rollback removes root write');
    t.same(await facet.read('facet-row'), 'committed-facet', 'awaited facet write commits independently of root transaction');
  },
  async Z215(s, t) {
    const parent = s.local('decision-parent');
    t.deep(await parent.commitWithDeclinedChild(), { outcome: 'declined', child: null }, 'child returns ordinary application decision after own rollback');
    t.same(await parent.read('parent'), 'committed-parent', 'handled child rollback does not roll back parent transaction');
    t.same(await parent.read('decision'), 'declined', 'parent commits workflow decision beside its state');
    t.same(await parent.childRead('leaf', 'child'), null, 'declined child write remains absent');
  },
  async Z216(s, t) {
    s.ctx.storage.kv.put('root', 'root-keep');
    const parent = s.local('clear-parent');
    await parent.put('own', 'remove-own');
    await parent.childPut('leaf', 'value', 'child-keep');
    t.deep(await parent.clearOwn(), { own: [] }, 'storage.deleteAll clears only current facet database');
    t.same(await parent.childRead('leaf', 'value'), 'child-keep', 'storage.deleteAll does not recursively delete child facet');
    t.same(s.ctx.storage.kv.get('root'), 'root-keep', 'facet storage.clear does not clear root database');
  },
  async Z217(s, t) {
    const parent = s.local('selective-delete');
    await parent.put('own', 'parent-keep');
    await parent.childPut('remove', 'value', 'remove-me');
    await parent.childPut('keep', 'value', 'sibling-keep');
    t.same(await parent.deleteChildAndRead('remove'), null, 'same-name recreation waits for completed leaf deletion');
    t.same(await parent.childRead('keep', 'value'), 'sibling-keep', 'deleting child preserves sibling database');
    t.same(await parent.read('own'), 'parent-keep', 'deleting child preserves parent database');
    t.same(await parent.childPut('remove', 'value', 'new-value'), 'new-value', 'recreated leaf is writable');
  },
  async Z218(s, t) {
    s.ctx.storage.kv.put('root', 'root-keep');
    const parent = s.local('tree'), sibling = s.local('tree-sibling');
    await parent.chain(['branch', 'leaf'], [1, 2, 3]);
    await sibling.put('value', 'sibling-keep');
    s.ctx.facets.delete('tree');
    const fresh = s.local('tree');
    t.deep(await fresh.chainRead(['branch', 'leaf']), [null, null, null], 'public facet delete removes complete descendant database subtree');
    t.same(await sibling.read('value'), 'sibling-keep', 'subtree deletion preserves adjacent root child');
    t.same(s.ctx.storage.kv.get('root'), 'root-keep', 'subtree deletion preserves root database');
    t.deep(await fresh.chain(['branch', 'leaf'], [4, 5, 6]), [4, 5, 6], 'recreated subtree starts clean and supports normal writes');
  },
  async Z219(s, t) {
    const local = s.local('local-module'), loaded = s.loaded('loaded-module', 'Facet', {});
    const a = await local.moduleInfo(), b = await loaded.moduleInfo();
    t.same(a.token, s.localToken, 'unmigrated loopback facet executes in root module isolate');
    t.ok(b.token !== s.localToken, 'loaded facet executes in loaded module isolate');
    t.deep(await loaded.nestedModule(), { parent: 'loaded-origin', child: 'loaded-origin:leaf' }, 'loaded facet ctx.exports resolves nested class and environment in loaded module');
    t.deep(await local.nestedModule(), { parent: 'root-origin', child: 'root-origin:leaf' }, 'same exported child name retains local module environment');
  },
};
