// Fixed finite storage/API workflows. No dynamic test generation or private hooks.
export async function D201(s, t) {
  const shared = { score: 7 }, value = { left: shared, right: shared };
  value.self = value;
  const pending = s.put('doc', value);
  shared.score = 99; value.extra = 'later';
  await pending;
  const got = await s.get('doc');
  t.eq(got.left.score, 7, 'put snapshots nested values before yielding');
  t.same(got.left, got.right, 'shared references survive one stored graph');
  t.same(got.self, got, 'cycle survives storage serialization');
  t.eq(Object.hasOwn(got, 'extra'), false, 'post-admission field excluded');
}

export async function D202(s, t) {
  const objectKey = { key: 'object' };
  const value = { date: new Date('2026-01-02T03:04:05.000Z'), big: 9007199254740993n, map: new Map([[objectKey, 'mapped']]), set: new Set([objectKey]), bytes: new Uint16Array([17, 513]) };
  await s.put('typed', value);
  const got = await s.get('typed'), key = [...got.map.keys()][0];
  t.ok(got.date instanceof Date && got.map instanceof Map && got.set instanceof Set && got.bytes instanceof Uint16Array, 'storage revives standard structured-clone brands');
  t.eq(got.date.toISOString(), '2026-01-02T03:04:05.000Z', 'date value exact');
  t.same(got.big, 9007199254740993n, 'BigInt remains lossless');
  t.eq([...got.bytes], [17, 513], 'typed view elements exact');
  t.eq(got.map.get(key), 'mapped', 'object-key Map lookup works');
  t.ok(got.set.has(key), 'cross-container alias preserved');
}

export async function D203(s, t) {
  await s.put('doc', { nested: { value: 1 }, list: ['first'] });
  const a = await s.get('doc'); a.nested.value = 9; a.list.push('mutated');
  const b = await s.get('doc');
  t.eq(b, { nested: { value: 1 }, list: ['first'] }, 'returned mutation does not write storage');
  t.ok(a !== b && a.nested !== b.nested, 'two reads are independently deserialized');
  await s.put('doc', a);
  t.eq(await s.get('doc'), { nested: { value: 9 }, list: ['first', 'mutated'] }, 'explicit subsequent put persists selected edited snapshot');
}

export async function D204(s, t) {
  await s.put('joint', { revision: 1 });
  t.eq(s.kv.get('joint'), { revision: 1 }, 'sync KV observes settled async put');
  s.kv.put('joint', { revision: 2 });
  t.eq(await s.get('joint'), { revision: 2 }, 'async get observes sync KV replacement');
  t.eq(s.kv.delete('joint'), true, 'sync deletion reports existing key');
  t.same(await s.get('joint'), undefined, 'async read observes sync deletion');
}

export async function D205(s, t) {
  const record = Object.create({ inherited: 'excluded' }); record.alpha = { n: 1 }; record.beta = { n: 2 };
  await s.put(record);
  const map = new Map([['beta', { n: 20 }], ['gamma', { n: 3 }]]);
  const write = s.put(map); map.get('beta').n = 200; map.set('late', { n: 4 }); await write;
  t.eq([...(await s.list())], [['alpha', { n: 1 }], ['beta', { n: 20 }], ['gamma', { n: 3 }]], 'own record fields and admitted Map entries are snapshotted before batch flush');
  t.same(await s.get('inherited'), undefined, 'prototype field is not a batch entry');
  t.same(await s.get('late'), undefined, 'late Map entry is not admitted');
}

export async function D206(s, t) {
  await s.put({ alpha: 1, beta: 2 });
  const found = await s.get(['beta', 'missing', 'alpha', 'beta']);
  t.ok(found instanceof Map, 'get-many returns Map');
  t.eq([...found], [['alpha', 1], ['beta', 2]], 'get-many sorts and deduplicates present keys');
  t.eq(found.has('missing'), false, 'missing key omitted rather than represented by null');
  t.eq((await s.get([])).size, 0, 'empty ordinary get-many returns empty Map');
}

export async function D207(s, t) {
  await s.put({ 'log/a': 1, 'log/b': 2, 'log/c': 3, 'log/d': 4, 'log/e': 5, 'logs/c': 6 });
  const inclusive = await s.list({ prefix: 'log/', start: 'log/b', end: 'log/e', limit: 2 });
  t.eq([...inclusive], [['log/b', 2], ['log/c', 3]], 'prefix, inclusive start and exclusive end intersect before limit');
  const subset = await s.list({ prefix: 'log/', startAfter: 'log/b', end: 'log/e', limit: 1 });
  t.eq([...subset], [['log/c', 3]], 'exclusive startAfter replaces inclusive start in a separate valid read');
  const suffix = await s.list({ prefix: 'log/', startAfter: 'log/c', end: 'log/e' });
  t.eq([...suffix], [['log/d', 4]], 'continuation excludes both endpoints and adjacent prefix');
}

export async function D208(s, t) {
  await s.put({ 'item/a': 1, 'item/b': 2, 'item/c': 3, 'item/d': 4, 'other/z': 9 });
  const first = await s.list({ prefix: 'item/', reverse: true, limit: 2 });
  const second = await s.list({ prefix: 'item/', reverse: true, end: 'item/c', limit: 2 });
  t.eq([...first], [['item/d', 4], ['item/c', 3]], 'first reverse page is descending');
  t.eq([...second], [['item/b', 2], ['item/a', 1]], 'exclusive end continues reverse page without duplicate');
  t.eq([...(await s.list({ prefix: 'item/', reverse: true, end: 'item/a', limit: 2 }))], [], 'final reverse continuation terminates');
}

export async function D209(s, t) {
  await s.put({ alpha: { v: 1 }, beta: { v: 2 } });
  const snapshot = await s.list(); snapshot.get('alpha').v = 100; snapshot.set('local', { v: 3 });
  await s.put('beta', { v: 20 });
  t.eq(snapshot.get('beta'), { v: 2 }, 'materialized list values do not track later storage writes');
  t.eq([...(await s.list())], [['alpha', { v: 1 }], ['beta', { v: 20 }]], 'mutating returned Map and nested value does not write storage');
}

export async function D210(s, t) {
  await s.put({ alpha: 1, beta: 2, gamma: 3 });
  t.eq(await s.delete(['beta', 'missing', 'beta', 'alpha']), 2, 'batch counts distinct existing deletions only');
  t.eq(await s.delete('beta'), false, 'already absent scalar deletion reports false');
  t.eq([...(await s.list())], [['gamma', 3]], 'unselected key survives batch');
  t.eq(await s.delete('gamma'), true, 'present scalar deletion reports true');
  t.eq(await s.delete([]), 0, 'empty deletion has zero effects');
}

export async function D211(s, t) {
  await s.put('before', 'kv');
  s.sql.exec('CREATE TABLE app_rows (id INTEGER PRIMARY KEY, value TEXT)');
  s.sql.exec('INSERT INTO app_rows VALUES (1, ?)', 'sql');
  await s.deleteAll();
  t.eq([...(await s.list())], [], 'deleteAll removes application KV');
  t.eq(s.sql.exec("SELECT name FROM sqlite_schema WHERE type='table' AND name='app_rows'").toArray(), [], 'deleteAll removes application SQL schema');
  await s.put('after', 'fresh');
  s.sql.exec('CREATE TABLE app_rows (id INTEGER PRIMARY KEY, value TEXT)');
  s.sql.exec('INSERT INTO app_rows VALUES (2, ?)', 'new');
  t.eq(await s.get('after'), 'fresh', 'KV works after schema reinitialization');
  t.eq(s.sql.exec('SELECT id, value FROM app_rows').one(), { id: 2, value: 'new' }, 'same application table name can be cleanly recreated');
}

export function D212(s, t) {
  const backing = new Uint8Array([9, 1, 2, 3, 8]);
  const row = s.sql.exec('SELECT ? AS integer_value, ? AS real_value, ? AS text_value, ? AS null_value, ? AS blob_value', 2147483648, 1.25, 'A\u0000λ', null, new DataView(backing.buffer, 1, 3)).one();
  t.eq([row.integer_value, row.real_value, row.text_value, row.null_value], [2147483648, 1.25, 'A\u0000λ', null], 'native SQL values preserve types and embedded text code points');
  t.ok(row.blob_value instanceof ArrayBuffer, 'BLOB result crosses as ArrayBuffer');
  t.eq([...new Uint8Array(row.blob_value)], [1, 2, 3], 'DataView binding uses only its byte window');
}

export function D213(s, t) {
  const cursor = s.sql.exec('SELECT 7 AS repeated, 9 AS repeated, 11 AS tail');
  t.eq(cursor.columnNames, ['repeated', 'repeated', 'tail'], 'column metadata retains duplicate aliases');
  t.eq([...cursor.raw()], [[7, 9, 11]], 'raw view preserves each duplicate column by position');
  t.eq(s.sql.exec('SELECT 7 AS repeated, 9 AS repeated, 11 AS tail').one(), { repeated: 9, tail: 11 }, 'object projection uses last duplicate property while raw retains both');
}

export function D214(s, t) {
  s.sql.exec('CREATE TABLE receipts (id INTEGER PRIMARY KEY, value TEXT)');
  const receipt = s.sql.exec('INSERT INTO receipts (id, value) VALUES (1, ?), (2, ?) RETURNING id, value', 'left', 'right');
  const returned = receipt.toArray().sort((a, b) => a.id - b.id);
  t.eq(returned, [{ id: 1, value: 'left' }, { id: 2, value: 'right' }], 'RETURNING cursor emits complete insertion receipt set without imposing output order');
  t.eq(s.sql.exec('SELECT id, value FROM receipts ORDER BY id').toArray(), [{ id: 1, value: 'left' }, { id: 2, value: 'right' }], 'exhausting receipt cursor completes both writes');
  t.eq(receipt.next().done, true, 'receipt cursor stays exhausted after independent SELECT');
}

export function D215(s, t) {
  let conversions = 0, text = 'SELECT ? + 1 AS answer';
  const query = { toString() { conversions++; return text; } };
  const prepared = s.sql.prepare(query); text = 'SELECT ? + 100 AS answer';
  t.eq(prepared(4).one(), { answer: 5 }, 'prepared closure captures query string at construction');
  t.eq(prepared(8).one(), { answer: 9 }, 'later invocation retains source and uses fresh bindings');
  t.eq(conversions, 1, 'query object converted exactly once, not per invocation');
}

export function D216(s, t) {
  const result = s.sql.ingest("CREATE TABLE journal (id INTEGER PRIMARY KEY, value TEXT);INSERT INTO journal VALUES (1, 'first'), (2, 'second');UPDATE journal SET value='updated' WHERE id=2;");
  t.eq(result, { remainder: '', rowsWritten: 3, statementCount: 3 }, 'complete batch reports statement count and affected rows');
  t.eq(s.sql.exec('SELECT id, value FROM journal ORDER BY id').toArray(), [{ id: 1, value: 'first' }, { id: 2, value: 'updated' }], 'ingestion executes all complete statements in order');
}

export function D217(s, t) {
  s.sql.exec('CREATE TABLE phrases (id INTEGER PRIMARY KEY, text TEXT)');
  const result = s.sql.ingest("INSERT INTO phrases VALUES (1, 'left;right');INSERT INTO phrases VALUES (2, 'quote'';inside');");
  t.eq(result.statementCount, 2, 'semicolons inside quoted strings do not split statements');
  t.eq(result.remainder, '', 'all syntactically complete input consumed');
  t.eq(s.sql.exec('SELECT text FROM phrases ORDER BY id').toArray(), [{ text: 'left;right' }, { text: "quote';inside" }], 'quoted text arrives without parser-boundary corruption');
}

export function D218(s, t) {
  s.sql.exec('CREATE TABLE source_rows (id INTEGER PRIMARY KEY, value INTEGER)');
  s.sql.exec('CREATE TABLE audit_rows (id INTEGER, value INTEGER)');
  const result = s.sql.ingest('CREATE TRIGGER copy_row AFTER INSERT ON source_rows BEGIN INSERT INTO audit_rows VALUES (new.id, new.value); UPDATE audit_rows SET value=value+1 WHERE id=new.id; END;INSERT INTO source_rows VALUES (1, 5);');
  t.eq(result.statementCount, 2, 'trigger body remains one top-level ingested statement');
  t.eq(result.rowsWritten, 3, 'ingest write count includes insert and both trigger effects');
  t.eq(result.remainder, '', 'entire trigger and following insert consumed');
  t.eq(s.sql.exec('SELECT id, value FROM audit_rows').one(), { id: 1, value: 6 }, 'trigger internal statement order preserved');
}

export function D219(s, t) {
  s.sql.exec('CREATE TABLE progress (value INTEGER)');
  const result = s.sql.ingest('SELECT 1 AS item UNION ALL SELECT 2;INSERT INTO progress VALUES (7);SELECT value FROM progress;');
  t.eq(result, { remainder: '', rowsWritten: 1, statementCount: 3 }, 'row-producing statements drain before later statements and count as statements, not writes');
  t.eq(s.sql.exec('SELECT value FROM progress').one(), { value: 7 }, 'write after discarded SELECT rows completes');
}

export function D220(s, t) {
  s.sql.exec('CREATE TABLE ledger (id INTEGER PRIMARY KEY, value INTEGER)');
  s.sql.exec('INSERT INTO ledger VALUES (1, 10)');
  const marker = new Error('planned application rollback'); let caught;
  try { s.transactionSync(() => {
    s.sql.ingest('UPDATE ledger SET value=20 WHERE id=1;INSERT INTO ledger VALUES (2, 30);');
    s.kv.put('transaction-only', 'discard');
    throw marker;
  }); } catch (error) { caught = error; }
  t.same(caught, marker, 'transaction propagates original application exception');
  t.eq(s.sql.exec('SELECT id, value FROM ledger ORDER BY id').toArray(), [{ id: 1, value: 10 }], 'ingest participates in surrounding transaction rollback');
  t.same(s.kv.get('transaction-only'), undefined, 'same rollback also removes ordinary sync KV effect');
  const committed = s.transactionSync(() => { s.sql.ingest('UPDATE ledger SET value=11 WHERE id=1;'); return 'receipt'; });
  t.eq(committed, 'receipt', 'subsequent successful transaction returns its callback value');
  t.eq(s.sql.exec('SELECT value FROM ledger WHERE id=1').one(), { value: 11 }, 'subsequent ingested write commits normally');
}

export const CASES = { D201, D202, D203, D204, D205, D206, D207, D208, D209, D210, D211, D212, D213, D214, D215, D216, D217, D218, D219, D220 };
