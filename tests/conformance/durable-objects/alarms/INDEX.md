# durable-objects/alarms

28 cases; 28 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [A delete committed within an explicit transaction might not remove the wake mirror even though normal delete works.](a-delete-committed-within-an-explicit-transaction-might-not-remove-the-wake-mirror-even-though-norma.case.json) | no | recovery |
| [A failed-handler retry record could override a newer alarm after restart, even when live completion respects the new generation.](a-failed-handler-retry-record-could-override-a-newer-alarm-after-restart-even-when-live-completion-r.case.json) | no | recovery |
| [A failed SQL transaction in the handler could leak its effect or prevent a subsequent retry from committing the intended effect.](a-failed-sql-transaction-in-the-handler-could-leak-its-effect-or-prevent-a-subsequent-retry-from-com.case.json) | no | recovery |
| [A generation created by setAlarm inside a failed transaction could survive in memory and suppress the old alarm retry.](a-generation-created-by-set-alarm-inside-a-failed-transaction-could-survive-in-memory-and-suppress-t.case.json) | no | recovery |
| [A handler that deliberately deletes its alarm and then fails could accidentally resurrect it through automatic retry.](a-handler-that-deliberately-deletes-its-alarm-and-then-fails-could-accidentally-resurrect-it-through.case.json) | no | recovery |
| [A nested savepoint rollback could publish the inner alarm or undo the outer alarm.](a-nested-savepoint-rollback-could-publish-the-inner-alarm-or-undo-the-outer-alarm.case.json) | no | recovery |
| [A rolled-back setAlarm could leave a watcher move despite the SQLite rollback.](a-rolled-back-set-alarm-could-leave-a-watcher-move-despite-the-sqlite-rollback.case.json) | no | recovery |
| [A stale persisted wake entry could resurrect the first timestamp after process death even though the newer alarm was acknowledged.](a-stale-persisted-wake-entry-could-resurrect-the-first-timestamp-after-process-death-even-though-the.case.json) | no | recovery |
| [A suspended event could stall unrelated durable objects or mix their state under a bounded simultaneous foreground cohort.](a-suspended-event-could-stall-unrelated-durable-objects-or-mix-their-state-under-a-bounded-simultane.case.json) | no | recovery |
| [A transactional alarm could fail to reach the scheduler or be committed without its companion SQL marker.](a-transactional-alarm-could-fail-to-reach-the-scheduler-or-be-committed-without-its-companion-sql-ma.case.json) | no | recovery |
| [A visibility fix could reject the scheduler as well as an ordinary class method call, or reject RPC only after running the handler.](a-visibility-fix-could-reject-the-scheduler-as-well-as-an-ordinary-class-method-call-or-reject-rpc-o.case.json) | no | recovery |
| [Advancing the timestamp could deliver the new event but leave an old future wake capable of running it again.](advancing-the-timestamp-could-deliver-the-new-event-but-leave-an-old-future-wake-capable-of-running.case.json) | no | recovery |
| [alarm](alarm.case.json) | no | example |
| [An earlier watcher wake could survive overwriting the one stored alarm with a later generation.](an-earlier-watcher-wake-could-survive-overwriting-the-one-stored-alarm-with-a-later-generation.case.json) | no | recovery |
| [An escaped handler exception could suppress retry or incorrectly roll back previously synchronized application state.](an-escaped-handler-exception-could-suppress-retry-or-incorrectly-roll-back-previously-synchronized-a.case.json) | no | recovery |
| [Automatic failure backoff of an old invocation could mutate a replacement committed by another concurrent RPC.](automatic-failure-backoff-of-an-old-invocation-could-mutate-a-replacement-committed-by-another-concu.case.json) | no | recovery |
| [Deleting a pending alarm may leave a wake that fires, or poison later normal scheduling for the same object.](deleting-a-pending-alarm-may-leave-a-wake-that-fires-or-poison-later-normal-scheduling-for-the-same.case.json) | no | recovery |
| [Deleting the schedule during a running handler could incorrectly cancel the event or let its later success recreate the deleted wake.](deleting-the-schedule-during-a-running-handler-could-incorrectly-cancel-the-event-or-let-its-later-s.case.json) | no | recovery |
| [Failure cleanup could overwrite a new generation deliberately armed by the failing handler.](failure-cleanup-could-overwrite-a-new-generation-deliberately-armed-by-the-failing-handler.case.json) | no | recovery |
| [getAlarm could expose the in-flight generation or hide a newer alarm explicitly set by that handler.](get-alarm-could-expose-the-in-flight-generation-or-hide-a-newer-alarm-explicitly-set-by-that-handler.case.json) | no | recovery |
| [Releasing a child savepoint could prematurely publish its alarm before the outer transaction commits.](releasing-a-child-savepoint-could-prematurely-publish-its-alarm-before-the-outer-transaction-commits.case.json) | no | recovery |
| [Retry bookkeeping could skip counts, retry indefinitely, or abandon before the source-defined six retries are exhausted.](retry-bookkeeping-could-skip-counts-retry-indefinitely-or-abandon-before-the-source-defined-six-retr.case.json) | no | recovery |
| [Rollback might restore the in-memory alarm but fail to persist its wake record correctly for cold restoration.](rollback-might-restore-the-in-memory-alarm-but-fail-to-persist-its-wake-record-correctly-for-cold-re.case.json) | no | recovery |
| [Rolling back a replacement could restore SQL but lose the original wake, or publish the attempted earlier wake.](rolling-back-a-replacement-could-restore-sql-but-lose-the-original-wake-or-publish-the-attempted-ear.case.json) | no | recovery |
| [Successful completion of an already-entered old handler could consume a newer alarm set by another ordinary RPC.](successful-completion-of-an-already-entered-old-handler-could-consume-a-newer-alarm-set-by-another-o.case.json) | no | recovery |
| [Successful event effects could be durable while the consumed alarm deletion is missing, causing a second dispatch after cold startup.](successful-event-effects-could-be-durable-while-the-consumed-alarm-deletion-is-missing-causing-a-sec.case.json) | no | recovery |
| [The watcher might consume an intermediate setAlarm even though set-delete-set commits one final state.](the-watcher-might-consume-an-intermediate-set-alarm-even-though-set-delete-set-commits-one-final-sta.case.json) | no | recovery |
| [transaction.rollback() could differ from exception rollback and leave a pending alarm deleted.](transaction-rollback-could-differ-from-exception-rollback-and-leave-a-pending-alarm-deleted.case.json) | no | recovery |
