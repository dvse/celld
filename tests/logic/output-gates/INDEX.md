# output-gates

33 cases; 33 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [Contain short-proof reset to the affected cell](contain-short-proof-reset-to-the-affected-cell.case.json) | yes | native |
| [Drain an alarm barrier when a different output proof resets the cell](drain-an-alarm-barrier-when-a-different-output-proof-resets-the-cell.case.json) | yes | native |
| [Drop proof cache across same-epoch runtime generation swap](drop-proof-cache-across-same-epoch-runtime-generation-swap.case.json) | yes | native |
| [Expire a bucket verification that never responds](expire-a-bucket-verification-that-never-responds.case.json) | yes | native |
| [Fence every held cell between bucket proof and ownership readback](fence-every-held-cell-between-bucket-proof-and-ownership-readback.case.json) | yes | native |
| [Find an older covering barrier when ticket arrival order reverses position order](find-an-older-covering-barrier-when-ticket-arrival-order-reverses-position-order.case.json) | yes | native |
| [Gate a reader whose observed commit precedes the writer ticket](gate-a-reader-whose-observed-commit-precedes-the-writer-ticket.case.json) | yes | native |
| [Hold a higher reader and its follower beyond a lower writer proof](hold-a-higher-reader-and-its-follower-beyond-a-lower-writer-proof.case.json) | yes | native |
| [Hold late alarm writes even after the firing operation timed out](hold-late-alarm-writes-even-after-the-firing-operation-timed-out.case.json) | yes | native |
| [Ignore a consumed alarm observation from the runtime being reset](ignore-a-consumed-alarm-observation-from-the-runtime-being-reset.case.json) | yes | native |
| [Ignore a retired fence timer after a timely lease renewal](ignore-a-retired-fence-timer-after-a-timely-lease-renewal.case.json) | yes | native |
| [Ignore a stale alarm completion after epoch replacement](ignore-a-stale-alarm-completion-after-epoch-replacement.case.json) | yes | native |
| [Ignore an unrelated ownership verification op while real readback waits](ignore-an-unrelated-ownership-verification-op-while-real-readback-waits.case.json) | yes | native |
| [Invalidate a pending sibling when bucket ownership is lost](invalidate-a-pending-sibling-when-bucket-ownership-is-lost.case.json) | yes | native |
| [Invalidate cached proof at failed-runtime reset and new epoch](invalidate-cached-proof-at-failed-runtime-reset-and-new-epoch.case.json) | yes | native |
| [Keep a cached low observation behind a later unproven write](keep-a-cached-low-observation-behind-a-later-unproven-write.case.json) | yes | native |
| [Keep a cancelled follower until shared bucket verification completes](keep-a-cancelled-follower-until-shared-bucket-verification-completes.case.json) | yes | native |
| [Keep a cancelled writer pinned while its reader waits](keep-a-cancelled-writer-pinned-while-its-reader-waits.case.json) | yes | native |
| [Keep a reader attached to an output newer than an alarm barrier](keep-a-reader-attached-to-an-output-newer-than-an-alarm-barrier.case.json) | yes | native |
| [Keep an older failed ticket distinct after a later proof released its reader](keep-an-older-failed-ticket-distinct-after-a-later-proof-released-its-reader.case.json) | yes | native |
| [Keep proof caches local to a cell](keep-proof-caches-local-to-a-cell.case.json) | yes | native |
| [Keep reader behind the latest alarm after earlier writer succeeds](keep-reader-behind-the-latest-alarm-after-earlier-writer-succeeds.case.json) | yes | native |
| [Keep simultaneous ownership readbacks bound to their exact ops](keep-simultaneous-ownership-readbacks-bound-to-their-exact-ops.case.json) | yes | native |
| [Let admitted handler gates finish a quiescing generation swap](let-admitted-handler-gates-finish-a-quiescing-generation-swap.case.json) | yes | native |
| [Prevent a stale timestamp from restoring expired output authority](prevent-a-stale-timestamp-from-restoring-expired-output-authority.case.json) | yes | native |
| [Rearm failed alarm ownership without losing discoverability](rearm-failed-alarm-ownership-without-losing-discoverability.case.json) | yes | native |
| [Refuse extending authority from an unanswered or late renewal](refuse-extending-authority-from-an-unanswered-or-late-renewal.case.json) | yes | native |
| [Reject an old sampled epoch without poisoning the new gate](reject-an-old-sampled-epoch-without-poisoning-the-new-gate.case.json) | yes | native |
| [Require ownership for bucket-proven alarm wake retirement](require-ownership-for-bucket-proven-alarm-wake-retirement.case.json) | yes | native |
| [Retain a finished reader follower until its barrier settles](retain-a-finished-reader-follower-until-its-barrier-settles.case.json) | yes | native |
| [Retain activity pin until a finished request settles its final channel](retain-activity-pin-until-a-finished-request-settles-its-final-channel.case.json) | yes | native |
| [Separate earlier write acknowledgment from a reader following a later failed write](separate-earlier-write-acknowledgment-from-a-reader-following-a-later-failed-write.case.json) | yes | native |
| [Take a fresh durability ticket for a response chunk after its head](take-a-fresh-durability-ticket-for-a-response-chunk-after-its-head.case.json) | yes | native |
