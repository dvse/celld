# durable-objects/storage-sql

71 cases; 71 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [A batched transactional KV delete reports real deletion count but restores keys before a queued list on explicit rollback.](a-batched-transactional-kv-delete-reports-real-deletion-count-but-restores-keys-before-a-queued-list.case.json) | no | topology |
| [A deferred native stepping error is delivered after the last good row, exactly once, despite a peer query in between.](a-deferred-native-stepping-error-is-delivered-after-the-last-good-row-exactly-once-despite-a-peer-qu.case.json) | no | topology |
| [A handled rejection of an omitted child promise rolls back the child without rejecting a successful outer callback.](a-handled-rejection-of-an-omitted-child-promise-rolls-back-the-child-without-rejecting-a-successful.case.json) | no | topology |
| [A legal UNIQUE-constraint failure in a peer request cannot finalize or poison another live read statement.](a-legal-unique-constraint-failure-in-a-peer-request-cannot-finalize-or-poison-another-live-read-stat.case.json) | no | topology |
| [A live prepared-query cursor retains its parameters while a separate request executes the identical busy cached SQL.](a-live-prepared-query-cursor-retains-its-parameters-while-a-separate-request-executes-the-identical.case.json) | no | topology |
| [A locally resumed preentered request retains its original event identity and queues outside a different owner transaction.](a-locally-resumed-preentered-request-retains-its-original-event-identity-and-queues-outside-a-differ.case.json) | no | topology |
| [A paused raw SQL iterator is independent of a peer object-row cursor using the identical cached query.](a-paused-raw-sql-iterator-is-independent-of-a-peer-object-row-cursor-using-the-identical-cached-quer.case.json) | no | topology |
| [A pending root put from a rolled-back synchronous callback cannot contaminate the next async transaction boundary.](a-pending-root-put-from-a-rolled-back-synchronous-callback-cannot-contaminate-the-next-async-transac.case.json) | no | topology |
| [A put promise admitted through a transaction view cannot flush its discarded value into the queued next transaction.](a-put-promise-admitted-through-a-transaction-view-cannot-flush-its-discarded-value-into-the-queued-n.case.json) | no | topology |
| [A rejected async transaction releases its queue slot without resetting the recipient or poisoning its queued successor.](a-rejected-async-transaction-releases-its-queue-slot-without-resetting-the-recipient-or-poisoning-it.case.json) | no | topology |
| [A root storage transactionSync helper nests into the same event async transaction after an await and isolates its caught failure.](a-root-storage-transaction-sync-helper-nests-into-the-same-event-async-transaction-after-an-await-an.case.json) | no | topology |
| [An exhausted empty cursor cannot acquire rows from a later reuse of its cached statement.](an-exhausted-empty-cursor-cannot-acquire-rows-from-a-later-reuse-of-its-cached-statement.case.json) | no | topology |
| [An omitted nested transaction promise is drained before the parent commits and the queued top-level successor enters.](an-omitted-nested-transaction-promise-is-drained-before-the-parent-commits-and-the-queued-top-level.case.json) | no | topology |
| [Admit allocation through conditional SQL RETURNING](atomic-accounting-t201.case.json) | no | http |
| [Deduplicate payloads with UPSERT reference accounting](atomic-accounting-t202.case.json) | no | http |
| [Maintain folder totals through SQL triggers](atomic-accounting-t203.case.json) | no | http |
| [Cascade renamed document ownership into chunks](atomic-accounting-t204.case.json) | no | http |
| [Commit deferred head references with nested revisions](atomic-accounting-t205.case.json) | no | http |
| [Select active document through a partial unique index](atomic-accounting-t206.case.json) | no | http |
| [Extract bounded KV partitions into SQL accounting](atomic-accounting-t207.case.json) | no | http |
| [Rebuild bounded recursive ancestry accounting](atomic-accounting-t208.case.json) | no | http |
| [Prune revision partitions with window-ranked retention](atomic-accounting-t209.case.json) | no | http |
| [Merge overlapping writes across chunk boundaries](atomic-accounting-t210.case.json) | no | http |
| [Detect sparse extent gaps with native boundary windows](atomic-accounting-t211.case.json) | no | http |
| [Trim native BLOB ranges before boundary append](atomic-accounting-t212.case.json) | no | http |
| [Publish complete chunk manifest with conserved charge](atomic-accounting-t213.case.json) | no | http |
| [Index generated UTF-8 payload byte lengths](atomic-accounting-t214.case.json) | no | http |
| [Reconcile FTS postings with document byte totals](atomic-accounting-t215.case.json) | no | http |
| [Bind-count validation failure on identical SQL cannot discard another request live statement when the cache entry is busy.](bind-count-validation-failure-on-identical-sql-cannot-discard-another-request-live-statement-when-th.case.json) | no | topology |
| [Bind SQL parameters and read inserted rows](bind-sql-parameters-and-read-inserted-rows.case.json) | yes | http |
| [Cached prepared metadata is refreshed after a peer request changes the referenced table schema.](cached-prepared-metadata-is-refreshed-after-a-peer-request-changes-the-referenced-table-schema.case.json) | no | topology |
| [Explicit outer rollback with a pending child marks its view terminal immediately but waits for child teardown before database rollback.](explicit-outer-rollback-with-a-pending-child-marks-its-view-terminal-immediately-but-waits-for-child.case.json) | no | topology |
| [Explicit rollback settles its callback return while restoring both KV and SQL before a queued successor enters.](explicit-rollback-settles-its-callback-return-while-restoring-both-kv-and-sql-before-a-queued-succes.case.json) | no | topology |
| [Failure serializing an ordinary KV batch queues no successful prefix and leaves a held SQL cursor usable.](failure-serializing-an-ordinary-kv-batch-queues-no-successful-prefix-and-leaves-a-held-sql-cursor-us.case.json) | no | topology |
| [Finite native SQL aggregation completes while an independent recipient request remains held and both recover.](finite-native-sql-aggregation-completes-while-an-independent-recipient-request-remains-held-and-both.case.json) | no | topology |
| [Identical SQL with simultaneously live cursors in two recipients stays storage-scope local.](identical-sql-with-simultaneously-live-cursors-in-two-recipients-stays-storage-scope-local.case.json) | no | topology |
| [Object iteration and raw iteration share one cursor position without peer cached-query reuse rewinding either view.](object-iteration-and-raw-iteration-share-one-cursor-position-without-peer-cached-query-reuse-rewindi.case.json) | no | topology |
| [Snapshot capture input before awaiting digest](os-action-file-store-f201.case.json) | no | http |
| [Publish and reassemble real chunk boundaries](os-action-file-store-f202.case.json) | no | http |
| [Retain empty allocation without chunks](os-action-file-store-f203.case.json) | no | http |
| [Release genuine allocation only once](os-action-file-store-f204.case.json) | no | http |
| [Prune only eligible unreferenced captures](os-action-file-store-f205.case.json) | no | http |
| [Preserve captures through aggregate refusal](os-action-file-store-f206.case.json) | no | http |
| [Outer failure waits for its already-running child before rolling back both layers and admitting a successor.](outer-failure-waits-for-its-already-running-child-before-rolling-back-both-layers-and-admitting-a-su.case.json) | no | topology |
| [Pending batch put, get-many, list and delete preserve their API call order through microtask flushing.](pending-batch-put-get-many-list-and-delete-preserve-their-api-call-order-through-microtask-flushing.case.json) | no | topology |
| [Prepared closures created from committed and rolled-back transaction views reject new execution while root SQL remains usable.](prepared-closures-created-from-committed-and-rolled-back-transaction-views-reject-new-execution-whil.case.json) | no | topology |
| [Rollback of an unrelated peer write transaction preserves an already-active native reader.](rollback-of-an-unrelated-peer-write-transaction-preserves-an-already-active-native-reader.case.json) | no | topology |
| [Root-handle async reentry after an await composes with an inner sync helper under the correct outer rollback boundary.](root-handle-async-reentry-after-an-await-composes-with-an-inner-sync-helper-under-the-correct-outer.case.json) | no | topology |
| [Same-request queued async transactions preserve invocation order and distinct return values.](same-request-queued-async-transactions-preserve-invocation-order-and-distinct-return-values.case.json) | no | topology |
| [SQL BLOB values are copied before later binding serialization mutates their shared backing buffer.](sql-blob-values-are-copied-before-later-binding-serialization-mutates-their-shared-backing-buffer.case.json) | no | topology |
| [SQL prefix failure distinguishes unwrapped autocommit effects from the same failure inside an explicit transaction while an unrelated reader is live.](sql-prefix-failure-distinguishes-unwrapped-autocommit-effects-from-the-same-failure-inside-an-explic.case.json) | no | topology |
| [Snapshot an admitted cyclic storage graph](storage-sql-d201.case.json) | no | http |
| [Revive a typed structured-clone storage graph](storage-sql-d202.case.json) | no | http |
| [Isolate read snapshots until explicitly written](storage-sql-d203.case.json) | no | http |
| [Share state coherently across async and sync KV APIs](storage-sql-d204.case.json) | no | http |
| [Snapshot admitted bulk record and Map entries](storage-sql-d205.case.json) | no | http |
| [Return sparse ordered get-many results](storage-sql-d206.case.json) | no | http |
| [Intersect storage listing bounds before limiting](storage-sql-d207.case.json) | no | http |
| [Continue reverse storage pages with exclusive end](storage-sql-d208.case.json) | no | http |
| [Keep returned storage list detached from later edits](storage-sql-d209.case.json) | no | http |
| [Count only existing keys in successful deletion batches](storage-sql-d210.case.json) | no | http |
| [Reinitialize both storage surfaces after deleteAll](storage-sql-d211.case.json) | no | http |
| [Preserve mixed SQL types across native value conversion](storage-sql-d212.case.json) | no | http |
| [Retain positional duplicate SQL columns in raw results](storage-sql-d213.case.json) | no | http |
| [Complete SQL RETURNING receipts before later reads](storage-sql-d214.case.json) | no | http |
| [Capture prepared query text once and bind each invocation](storage-sql-d215.case.json) | no | http |
| [Report complete ingest batch effects accurately](storage-sql-d216.case.json) | no | http |
| [Respect quoted semicolons in complete SQL ingestion](storage-sql-d217.case.json) | no | http |
| [Keep complete trigger bodies inside one ingest statement](storage-sql-d218.case.json) | no | http |
| [Drain row-producing ingest statements before following writes](storage-sql-d219.case.json) | no | http |
| [Enroll ingestion in an application transaction boundary](storage-sql-d220.case.json) | no | http |
