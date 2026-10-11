# wake-recovery

19 cases; 19 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [Coalesce repeated Fleet hints through the whole cold pipeline](coalesce-repeated-fleet-hints-through-the-whole-cold-pipeline.case.json) | yes | native |
| [Defer an already-due restored alarm until startup publication](defer-an-already-due-restored-alarm-until-startup-publication.case.json) | yes | native |
| [Filter unknown Owned hints before allocating state or permits](filter-unknown-owned-hints-before-allocating-state-or-permits.case.json) | yes | native |
| [Hold Queue concurrency until persisted settlement or expiry](hold-queue-concurrency-until-persisted-settlement-or-expiry.case.json) | yes | native |
| [Isolate registration completion credit by cell](isolate-registration-completion-credit-by-cell.case.json) | yes | native |
| [Keep newest wake coverage after reversed PUT completions](keep-newest-wake-coverage-after-reversed-put-completions.case.json) | yes | native |
| [Keep original cron occurrence identity across retry scheduling](keep-original-cron-occurrence-identity-across-retry-scheduling.case.json) | yes | native |
| [Let an elected hint revisit a cached remote route](let-an-elected-hint-revisit-a-cached-remote-route.case.json) | yes | native |
| [Merge cold Queue deadlines without delaying unrelated work](merge-cold-queue-deadlines-without-delaying-unrelated-work.case.json) | yes | native |
| [Prefer a scheduled occurrence over a tying or slower retry](prefer-a-scheduled-occurrence-over-a-tying-or-slower-retry.case.json) | yes | native |
| [Preserve cold work through elected-waker handoff](preserve-cold-work-through-elected-waker-handoff.case.json) | yes | native |
| [Recover failed cold restore through an Owned hint](recover-failed-cold-restore-through-an-owned-hint.case.json) | yes | native |
| [Reestablish only the lost cell publication cache](reestablish-only-the-lost-cell-publication-cache.case.json) | yes | native |
| [Retain alarm demand after the last queued caller cancels](retain-alarm-demand-after-the-last-queued-caller-cancels.case.json) | yes | native |
| [Retain sparse future schedules across long calendar gaps](retain-sparse-future-schedules-across-long-calendar-gaps.case.json) | yes | native |
| [Retry an unknown global wake PUT without changing its name](retry-an-unknown-global-wake-put-without-changing-its-name.case.json) | yes | native |
| [Reuse wake coverage across unrelated SQLite commits](reuse-wake-coverage-across-unrelated-sqlite-commits.case.json) | yes | native |
| [Scan around live and delayed Queue rows then reclaim the expired row](scan-around-live-and-delayed-queue-rows-then-reclaim-the-expired-row.case.json) | yes | native |
| [Use fixed Queue failure delay and stop at the delivery budget](use-fixed-queue-failure-delay-and-stop-at-the-delivery-budget.case.json) | yes | native |
