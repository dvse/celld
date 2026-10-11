// Source-only application fixtures. The imported production module is byte-exact.
// All storage is the actual DurableObjectState.storage passed by fixture.js.
import { collection, createTypedStorage, singleton } from './vendor/cloudflare-os/packages/typed-storage/src/index.ts';

export function C201(s, t) {
  const db = createTypedStorage(s, { collections: {
    docs: collection()({ primaryKey: 'id', nonUniqueIndexes: { tags: row => row.tags } }),
  } });
  db.docs.put({ id: 'a', tags: ['blue', 'green'] });
  db.docs.put({ id: 'b', tags: ['blue'] });
  db.docs.put({ id: 'c', tags: ['green', 'red'] });
  db.docs.put({ id: 'd', tags: ['red'] });
  // Each read is fully consumed before the next starts. Production code, rather
  // than this fixture, must buffer the outer native list before child lists.
  const first = t.rows(db.docs.tags.list({ limit: 1 }));
  const continuation = t.rows(db.docs.tags.list({ startAfter: 'blue', limit: 1 }));
  const deduped = t.rows(db.docs.tags.list({ limit: 2, dedupe: true }));
  t.eq({ first, continuation, deduped }, {
    first: [{ id: 'a', tags: ['blue', 'green'] }, { id: 'b', tags: ['blue'] }],
    continuation: [{ id: 'a', tags: ['blue', 'green'] }, { id: 'c', tags: ['green', 'red'] }],
    deduped: [{ id: 'a', tags: ['blue', 'green'] }, { id: 'b', tags: ['blue'] }, { id: 'c', tags: ['green', 'red'] }],
  }, 'outer limit counts complete index keys; continuation and within-call dedupe retain exact memberships');
  const reverse = t.rows(db.docs.tags.list({ reverse: true, limit: 2 }));
  const reverseDeduped = t.rows(db.docs.tags.list({ reverse: true, limit: 2, dedupe: true }));
  t.eq({ reverse, reverseDeduped }, {
    reverse: [{ id: 'd', tags: ['red'] }, { id: 'c', tags: ['green', 'red'] }, { id: 'c', tags: ['green', 'red'] }, { id: 'a', tags: ['blue', 'green'] }],
    reverseDeduped: [{ id: 'd', tags: ['red'] }, { id: 'c', tags: ['green', 'red'] }, { id: 'a', tags: ['blue', 'green'] }],
  }, 'reverse orders both index keys and matching primary keys before first-encounter dedupe');
  const groupPage = t.rows(db.docs.tags.get('blue', { reverse: true, limit: 1 }));
  const groupTail = t.rows(db.docs.tags.get('blue', { reverse: true, end: 'b', limit: 1 }));
  t.eq({ groupPage, groupTail }, {
    groupPage: [{ id: 'b', tags: ['blue'] }],
    groupTail: [{ id: 'a', tags: ['blue', 'green'] }],
  }, 'get pages matching primary-key records rather than outer index keys');
}

export function C202(s, t) {
  const db = createTypedStorage(s, { collections: {
    docs: collection()({ primaryKey: 'id', uniqueIndexes: { slug: row => row.slug, mail: row => row.mail }, nonUniqueIndexes: { team: row => row.team } }),
  } });
  db.docs.put({ id: 'a', slug: 'alpha', mail: 'a@fixture.invalid', team: 'red', revision: 1 });
  db.docs.put({ id: 'b', slug: 'beta', mail: 'b@fixture.invalid', team: 'blue', revision: 2 });
  let updateError, insertError;
  try { db.docs.put({ id: 'a', slug: 'gamma', mail: 'b@fixture.invalid', team: 'green', revision: 9 }); }
  catch (error) { updateError = error.message; }
  try { db.docs.put({ id: 'c', slug: 'gamma', mail: 'b@fixture.invalid', team: 'green', revision: 10 }); }
  catch (error) { insertError = error.message; }
  t.eq([updateError, insertError], ["Update conflicts with record 'b' in 'docs.mail'.", "Insertion conflicts with record 'b' in 'docs.mail'."], 'ordinary legal name conflicts reject both replacement and new registration');
  t.eq(t.rows(s.kv.list()), [
    ['docs.mail:a@fixture.invalid', 'a'], ['docs.mail:b@fixture.invalid', 'b'],
    ['docs.slug:alpha', 'a'], ['docs.slug:beta', 'b'],
    ['docs.team#', 2], ['docs.team.0:a', {}], ['docs.team.1:b', {}], ['docs.team:blue', 1], ['docs.team:red', 0],
    ['docs:a', { id: null, slug: 'alpha', mail: 'a@fixture.invalid', team: 'red', revision: 1 }],
    ['docs:b', { id: null, slug: 'beta', mail: 'b@fixture.invalid', team: 'blue', revision: 2 }],
  ], 'failed second-index claims roll back earlier slug mutations and preserve all rows, index children and counters');
  db.docs.put({ id: 'a', slug: 'gamma', mail: 'c@fixture.invalid', team: 'blue', revision: 3 });
  t.eq(t.rows(s.kv.list()), [
    ['docs.mail:b@fixture.invalid', 'b'], ['docs.mail:c@fixture.invalid', 'a'],
    ['docs.slug:beta', 'b'], ['docs.slug:gamma', 'a'],
    ['docs.team#', 2], ['docs.team.1:a', {}], ['docs.team.1:b', {}], ['docs.team:blue', 1],
    ['docs:a', { id: null, slug: 'gamma', mail: 'c@fixture.invalid', team: 'blue', revision: 3 }],
    ['docs:b', { id: null, slug: 'beta', mail: 'b@fixture.invalid', team: 'blue', revision: 2 }],
  ], 'later valid replacement commits one coherent row plus both unique indexes and nonunique membership');
  t.eq(t.rows(db.docs.team.get('blue')), [
    { id: 'a', slug: 'gamma', mail: 'c@fixture.invalid', team: 'blue', revision: 3 },
    { id: 'b', slug: 'beta', mail: 'b@fixture.invalid', team: 'blue', revision: 2 },
  ], 'reconstructed records remain readable through the successfully updated index');
}

export function C203(s, t) {
  const db = createTypedStorage(s, { collections: {
    docs: collection()({ primaryKey: 'id', uniqueIndexes: { alias: row => row.alias }, nonUniqueIndexes: {
      labels: row => row.state === 'pending' ? ['pending', row.kind] : row.state === 'hidden' ? null : row.kind,
    } }),
  } });
  db.docs.put({ id: 'a', alias: null, state: 'pending', kind: 'draft' });
  db.docs.put({ id: 'b', alias: 'beta', state: 'pending', kind: 'draft' });
  db.docs.put({ id: 'a', alias: 'alpha', state: 'complete', kind: 'draft' });
  t.eq(t.rows(s.kv.list({ prefix: 'docs.labels' })), [
    ['docs.labels#', 2], ['docs.labels.0:b', {}], ['docs.labels.1:a', {}], ['docs.labels.1:b', {}], ['docs.labels:draft', 1], ['docs.labels:pending', 0],
  ], 'array-to-scalar transition preserves the shared draft membership and its allocated group');
  db.docs.put({ id: 'a', alias: 'alpha', state: 'pending', kind: 'final' });
  db.docs.put({ id: 'a', alias: null, state: 'hidden', kind: 'final' });
  db.docs.put({ id: 'b', alias: 'beta', state: 'complete', kind: 'draft' });
  t.eq(t.rows(s.kv.list({ prefix: 'docs.labels' })), [
    ['docs.labels#', 3], ['docs.labels.1:b', {}], ['docs.labels:draft', 1],
  ], 'scalar-to-array-to-null removes only changed memberships and reclaims last-member group rows');
  t.same(db.docs.alias.get('alpha'), undefined, 'nullable unique index removes formerly present alias');
  db.docs.put({ id: 'a', alias: 'alpha', state: 'pending', kind: 'final' });
  t.eq(t.rows(s.kv.list()), [
    ['docs.alias:alpha', 'a'], ['docs.alias:beta', 'b'],
    ['docs.labels#', 5], ['docs.labels.1:b', {}], ['docs.labels.3:a', {}], ['docs.labels.4:a', {}],
    ['docs.labels:draft', 1], ['docs.labels:final', 4], ['docs.labels:pending', 3],
    ['docs:a', { id: null, alias: 'alpha', state: 'pending', kind: 'final' }],
    ['docs:b', { id: null, alias: 'beta', state: 'complete', kind: 'draft' }],
  ], 'null-to-array recreation uses fresh group IDs while preserving unrelated scalar and unique memberships');
}

export function C204(s, t) {
  let db = createTypedStorage(s, { collections: {
    docs: collection()({ primaryKey: 'id' }),
  }, singletons: { version: 1 } });
  db.docs.put({ id: 'a', slug: 'first', tags: ['blue'] });
  db.docs.put({ id: 'b', slug: 'second', tags: ['blue', 'red'] });
  // The old schema is no longer used after this code/schema migration.
  db = createTypedStorage(s, { collections: {
    docs: collection()({ primaryKey: 'id', uniqueIndexes: { slug: row => row.slug }, nonUniqueIndexes: { tags: row => row.tags } }),
  }, singletons: { version: 1 } });
  t.eq([t.rows(db.docs.slug.list()), t.rows(db.docs.tags.list())], [[], []], 'late-declared indexes are empty until explicit migration rebuild');
  const receipt = db.transaction(() => { db.docs.slug.rebuild(); db.docs.tags.rebuild(); db.version.put(2); return 'migration-v2'; });
  t.eq([receipt, db.version.get(), s.kv.get('docs.tags#')], ['migration-v2', 2, 2], 'real nested index rebuilds and migration stamp commit inside typed transaction');
  t.eq(t.rows(db.docs.tags.list()), [
    { id: 'a', slug: 'first', tags: ['blue'] }, { id: 'b', slug: 'second', tags: ['blue', 'red'] }, { id: 'b', slug: 'second', tags: ['blue', 'red'] },
  ], 'first rebuild backfills every existing record membership');
  db.transaction(() => { db.docs.slug.rebuild(); db.docs.tags.rebuild(); });
  t.eq(t.rows(s.kv.list({ prefix: 'docs.tags' })), [
    ['docs.tags#', 4], ['docs.tags.2:a', {}], ['docs.tags.2:b', {}], ['docs.tags.3:b', {}], ['docs.tags:blue', 2], ['docs.tags:red', 3],
  ], 'second real rebuild sweeps old index children while retaining the monotonic group allocation counter');
  db.docs.put({ id: 'b', slug: 'second-v2', tags: ['green'] });
  t.eq(t.rows(s.kv.list()), [
    ['docs.slug:first', 'a'], ['docs.slug:second-v2', 'b'],
    ['docs.tags#', 5], ['docs.tags.2:a', {}], ['docs.tags.4:b', {}], ['docs.tags:blue', 2], ['docs.tags:green', 4],
    ['docs:a', { id: null, slug: 'first', tags: ['blue'] }], ['docs:b', { id: null, slug: 'second-v2', tags: ['green'] }], ['version', 2],
  ], 'post-migration edit maintains both rebuilt indexes and original records without orphaned child rows');
}

export function C205(s, t) {
  const db = createTypedStorage(s, { collections: {
    docs: collection()({ primaryKey: 'id', uniqueIndexes: { slug: row => row.slug }, nonUniqueIndexes: { tags: row => row.tags } }),
    audit: collection()({ primaryKey: 'id' }),
  } });
  db.docs.put({ id: 'a', slug: 'one', tags: ['red', 'shared'] });
  db.docs.put({ id: 'b', slug: 'two', tags: ['red'] });
  db.docs.put({ id: 'c', slug: 'three', tags: ['red', 'shared'] });
  db.docs.put({ id: 'd', slug: 'four', tags: ['blue', 'shared'] });
  const subscriber = {
    add() {}, update() {},
    remove(record) {
      // Ordinary app read-and-audit callback. This opens another native list in
      // addition to the production index subscriber's own membership probes.
      t.rows(db.docs.tags.get('shared'));
      db.audit.put({ id: record.id, removedSlug: record.slug });
    },
  };
  db.docs.subscribe(subscriber);
  let deleted;
  try { deleted = db.docs.tags.delete('red'); }
  finally { db.docs.unsubscribe(subscriber); }
  t.eq([deleted, db.docs.tags.delete('red')], [3, 0], 'buffered group deletion consumes every original member exactly once and then reports empty');
  t.eq(t.rows(db.docs.list()), [{ id: 'd', slug: 'four', tags: ['blue', 'shared'] }], 'group delete removes whole records while preserving the unselected overlapping member');
  t.eq(t.rows(db.audit.list()), [{ id: 'a', removedSlug: 'one' }, { id: 'b', removedSlug: 'two' }, { id: 'c', removedSlug: 'three' }], 'each originally selected record produces one exact stored application audit despite callback lists');
  t.eq(t.rows(s.kv.list({ prefix: 'docs.' })), [
    ['docs.slug:four', 'd'], ['docs.tags#', 3], ['docs.tags.1:d', {}], ['docs.tags.2:d', {}], ['docs.tags:blue', 2], ['docs.tags:shared', 1],
  ], 'all removed unique postings and overlapping nonunique children are reclaimed without invalidating the buffered deletion');
}

export function C206(s, t) {
  const db = createTypedStorage(s, { collections: {
    revisions: collection()({ primaryKey: row => row.document + '/' + row.revision,
      uniqueIndexes: { label: row => row.label }, nonUniqueIndexes: { document: row => row.document } }),
  } });
  db.revisions.put({ document: 'memo', revision: 1, label: 'draft', bytes: 3 });
  db.revisions.put({ document: 'memo', revision: 2, label: 'final', bytes: 7 });
  const stale = { document: 'memo', revision: 1, label: 'obsolete', bytes: 99 };
  t.eq([db.revisions.deleteRecord(stale), db.revisions.deleteRecord(stale)], [true, false], 'computed primary-key deletion ignores stale non-key properties and accurately reports repeated deletion');
  t.eq(t.rows(db.revisions.document.get('memo')), [{ document: 'memo', revision: 2, label: 'final', bytes: 7 }], 'stored old record supplies index removal while other revision remains indexed');
  t.eq(t.rows(s.kv.list()), [
    ['revisions.document#', 1], ['revisions.document.0:memo/2', {}], ['revisions.document:memo', 0], ['revisions.label:final', 'memo/2'],
    ['revisions:memo/2', { document: 'memo', revision: 2, label: 'final', bytes: 7 }],
  ], 'computed-key delete leaves exactly the surviving main record and its real unique/nonunique postings');
}

export function C207(s, t) {
  let db = createTypedStorage(s, { collections: {
    items: collection()({ primaryKey: 'id', uniqueIndexes: { slug: row => row.slug } }),
  }, singletons: { revision: 0 } });
  db.items.put({ id: 'a', slug: 'one', value: 'saved' });
  db.revision.put(4);
  // Sequential code rename only. No old handle is used after constructing the
  // renamed schema, so subscriber sets are never treated as concurrent aliases.
  db = createTypedStorage(s, { collections: {
    documents: collection()({ primaryKey: 'id', storageName: 'items', uniqueIndexes: { slug: row => row.slug } }),
  }, singletons: { generation: singleton(0, { storageKey: 'revision' }) } });
  t.eq([db.documents.get('a'), db.documents.slug.get('one'), db.generation.get()], [
    { id: 'a', slug: 'one', value: 'saved' }, { id: 'a', slug: 'one', value: 'saved' }, 4,
  ], 'renamed collection, index and singleton read their original persisted locations');
  db.transaction(() => { db.documents.put({ id: 'a', slug: 'two', value: 'edited' }); db.generation.put(5); });
  t.eq(t.rows(s.kv.list()), [
    ['items.slug:two', 'a'], ['items:a', { id: null, slug: 'two', value: 'edited' }], ['revision', 5],
  ], 'renamed code updates original physical rows with no new-name shadow rows or obsolete index key');
  db = createTypedStorage(s, { collections: {
    documents: collection()({ primaryKey: 'id', storageName: 'items', uniqueIndexes: { slug: row => row.slug } }),
  }, singletons: { generation: singleton(0, { storageKey: 'revision' }) } });
  t.eq([t.rows(db.documents.list()), db.generation.get()], [[{ id: 'a', slug: 'two', value: 'edited' }], 5], 'new renamed-schema instance retains the completed ordinary storage update');
}

export const CASES = { C201, C202, C203, C204, C205, C206, C207 };
