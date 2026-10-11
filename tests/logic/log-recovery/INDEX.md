# log-recovery

23 cases; 23 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [Bound queued overload without fabricating coverage and allow a fresh retry budget](bound-queued-overload-without-fabricating-coverage-and-allow-a-fresh-retry-budget.case.json) | yes | native |
| [Fence capture-to-credit gap before changing log epoch](fence-capture-to-credit-gap-before-changing-log-epoch.case.json) | yes | native |
| [Floor recovery at bucket proof when retained follower ends earlier](floor-recovery-at-bucket-proof-when-retained-follower-ends-earlier.case.json) | yes | native |
| [Honor recovery record after competing reconfiguration loses its CAS](honor-recovery-record-after-competing-reconfiguration-loses-its-cas.case.json) | yes | native |
| [Keep later per-cell coverage behind an uncovered ledger head](keep-later-per-cell-coverage-behind-an-uncovered-ledger-head.case.json) | yes | native |
| [Keep old checkpoint objects until paged fill unpins its chain](keep-old-checkpoint-objects-until-paged-fill-unpins-its-chain.case.json) | yes | native |
| [Preserve restore-selected base despite an excluded newer snapshot](preserve-restore-selected-base-despite-an-excluded-newer-snapshot.case.json) | yes | native |
| [Re-recruit a healed gray follower while preserving swap rate cap](re-recruit-a-healed-gray-follower-while-preserving-swap-rate-cap.case.json) | yes | native |
| [Recover an acknowledged prefix with an unacknowledged longer follower tail](recover-an-acknowledged-prefix-with-an-unacknowledged-longer-follower-tail.case.json) | yes | native |
| [Recover correlated follower partition without quarantining every peer](recover-correlated-follower-partition-without-quarantining-every-peer.case.json) | yes | native |
| [Reject delayed bundle credit after seal and preserve its uncovered rows](reject-delayed-bundle-credit-after-seal-and-preserve-its-uncovered-rows.case.json) | yes | native |
| [Reject stale lower restore base against a higher recorded mark](reject-stale-lower-restore-base-against-a-higher-recorded-mark.case.json) | yes | native |
| [Release previous-epoch retention margin only after successor opener](release-previous-epoch-retention-margin-only-after-successor-opener.case.json) | yes | native |
| [Renew partial recovery then replace only a stale claimant](renew-partial-recovery-then-replace-only-a-stale-claimant.case.json) | yes | native |
| [Reopen sealed session with fresh member confirmations and ledger](reopen-sealed-session-with-fresh-member-confirmations-and-ledger.case.json) | yes | native |
| [Repeat retirement prerequisite after its write fails](repeat-retirement-prerequisite-after-its-write-fails.case.json) | yes | native |
| [Require per-cell tail and empty capture gap for graceful close](require-per-cell-tail-and-empty-capture-gap-for-graceful-close.case.json) | yes | native |
| [Respect grace after a fenced owner lands a late old-epoch object](respect-grace-after-a-fenced-owner-lands-a-late-old-epoch-object.case.json) | yes | native |
| [Retain fleet witness after gray eviction until bucket retry proves coverage](retain-fleet-witness-after-gray-eviction-until-bucket-retry-proves-coverage.case.json) | yes | native |
| [Retry only surviving victims after a partial GC delete failure](retry-only-surviving-victims-after-a-partial-gc-delete-failure.case.json) | yes | native |
| [Separate retired old-epoch rows from live tail in one mixed bundle](separate-retired-old-epoch-rows-from-live-tail-in-one-mixed-bundle.case.json) | yes | native |
| [Split captured-ticket stall budget from a newer queued ticket](split-captured-ticket-stall-budget-from-a-newer-queued-ticket.case.json) | yes | native |
| [Wait for own opener visibility before retiring prior epochs](wait-for-own-opener-visibility-before-retiring-prior-epochs.case.json) | yes | native |
