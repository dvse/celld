# durable-objects/storage-kv

33 cases; 33 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [A bounded store500 failure allows an unproven success or leaves the root unable to make durable progress.](a-bounded-store500-failure-allows-an-unproven-success-or-leaves-the-root-unable-to-make-durable-prog.case.json) | no | recovery |
| [A bucket-acknowledged subset of a concurrent unique-key cohort disappears after all runtime heaps/local directories are discarded.](a-bucket-acknowledged-subset-of-a-concurrent-unique-key-cohort-disappears-after-all-runtime-heaps-lo.case.json) | no | recovery |
| [A dirty root with failed proofs blocks unrelated clean-root reads or corrupts that root during later recovery.](a-dirty-root-with-failed-proofs-blocks-unrelated-clean-root-reads-or-corrupts-that-root-during-later.case.json) | no | recovery |
| [A real scheduled alarm and foreground writes sharing a held durability proof lose each other or fail to recover together.](a-real-scheduled-alarm-and-foreground-writes-sharing-a-held-durability-proof-lose-each-other-or-fail.case.json) | no | recovery |
| [An already acknowledged cohort proof is incorrectly reused to release later dirty writer/read outputs.](an-already-acknowledged-cohort-proof-is-incorrectly-reused-to-release-later-dirty-writer-read-output.case.json) | no | recovery |
| [An explicitly rolled-back transaction contaminates neighboring successful transactions or survives recovery.](an-explicitly-rolled-back-transaction-contaminates-neighboring-successful-transactions-or-survives-r.case.json) | no | recovery |
| [An overlapping reader exports local SQL before durable proof or sees a half-written pair/ledger transaction.](an-overlapping-reader-exports-local-sql-before-durable-proof-or-sees-a-half-written-pair-ledger-tran.case.json) | no | recovery |
| [CHECK failure rolls back its own ledger but leaves a corrupted transaction state that breaks later sibling transfers.](check-failure-rolls-back-its-own-ledger-but-leaves-a-corrupted-transaction-state-that-breaks-later-s.case.json) | no | recovery |
| [Competing compare-and-swap transactions acknowledge multiple winners or restore a different winner than the acknowledged one.](competing-compare-and-swap-transactions-acknowledge-multiple-winners-or-restore-a-different-winner-t.case.json) | no | recovery |
| [Concurrent methods that entered but never passed their application gate mutate or acknowledge after owner loss.](concurrent-methods-that-entered-but-never-passed-their-application-gate-mutate-or-acknowledge-after.case.json) | no | recovery |
| [Concurrent outbound effects become visible before their SQL is proven durable.](concurrent-outbound-effects-become-visible-before-their-sql-is-proven-durable.case.json) | no | recovery |
| [Concurrent requests with one application key each increment the counter or recovery forgets the dedup marker.](concurrent-requests-with-one-application-key-each-increment-the-counter-or-recovery-forgets-the-dedu.case.json) | no | recovery |
| [Concurrent SQL increments acknowledge individually but restore a counter smaller than the committed operation ledger.](concurrent-sql-increments-acknowledge-individually-but-restore-a-counter-smaller-than-the-committed.case.json) | no | recovery |
| [Key-value, alarm, transaction and sync operations are callable](key-value-alarm-transaction-and-sync-operations-are-callable.case.json) | yes | http |
| [Killing all runtimes with new writes blocked before store persistence loses already acknowledged prefix or recovers torn/phantom transactions.](killing-all-runtimes-with-new-writes-blocked-before-store-persistence-loses-already-acknowledged-pre.case.json) | no | recovery |
| [List stored primitive and object values by key prefix](list-stored-primitive-and-object-values-by-key-prefix.case.json) | yes | http |
| [Traverse buffered nonunique index pages](os-typed-storage-c201.case.json) | no | http |
| [Roll back conflicting index subscriptions](os-typed-storage-c202.case.json) | no | http |
| [Transition nullable multikey memberships](os-typed-storage-c203.case.json) | no | http |
| [Rebuild newly declared storage indexes](os-typed-storage-c204.case.json) | no | http |
| [Delete buffered indexed groups safely](os-typed-storage-c205.case.json) | no | http |
| [Delete records through computed keys](os-typed-storage-c206.case.json) | no | http |
| [Preserve storage across schema renames](os-typed-storage-c207.case.json) | no | http |
| [Owner dies after bucket persisted bytes but before acknowledgement; resubmission with stable application IDs double-applies effects.](owner-dies-after-bucket-persisted-bytes-but-before-acknowledgement-resubmission-with-stable-applicat.case.json) | no | recovery |
| [Persist a counter across named-object fetches](persist-a-counter-across-named-object-fetches.case.json) | yes | http |
| [Physical bucket persistence is mistaken for acknowledged proof and releases writers/readers while store acknowledgements are held.](physical-bucket-persistence-is-mistaken-for-acknowledged-proof-and-releases-writers-readers-while-st.case.json) | no | recovery |
| [Readers or recovery observe only one side of a committed account transfer under contending writes.](readers-or-recovery-observe-only-one-side-of-a-committed-account-transfer-under-contending-writes.case.json) | no | recovery |
| [Recovery resurrects deleted documents or drops interleaved new documents when their acknowledgements overlap.](recovery-resurrects-deleted-documents-or-drops-interleaved-new-documents-when-their-acknowledgements.case.json) | no | recovery |
| [Restart loses a persisted future alarm or firing overwrites previously acknowledged concurrent foreground SQL.](restart-loses-a-persisted-future-alarm-or-firing-overwrites-previously-acknowledged-concurrent-foreg.case.json) | no | recovery |
| [Roll back a failed key-value transaction](roll-back-a-failed-key-value-transaction.case.json) | yes | http |
| [Rolled-back SQL leaves a false dirty barrier that deadlocks concurrent clean outbound effects when object-store writes are held.](rolled-back-sql-leaves-a-false-dirty-barrier-that-deadlocks-concurrent-clean-outbound-effects-when-o.case.json) | no | recovery |
| [Rolling back an inner savepoint drops outer work or leaks inner updates into concurrent readers and recovered state.](rolling-back-an-inner-savepoint-drops-outer-work-or-leaks-inner-updates-into-concurrent-readers-and.case.json) | no | recovery |
| [Two roots using identical operation IDs merge their recovered ledgers or rollback state across ownership changes.](two-roots-using-identical-operation-ids-merge-their-recovered-ledgers-or-rollback-state-across-owner.case.json) | no | recovery |
