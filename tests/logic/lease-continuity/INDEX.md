# lease-continuity

19 cases; 19 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [applied at and after expiry fences](applied-at-and-after-expiry-fences.case.json) | yes | native |
| [applied before expiry is accepted](applied-before-expiry-is-accepted.case.json) | yes | native |
| [every current read branch at either prior expiry is expired](every-current-read-branch-at-either-prior-expiry-is-expired.case.json) | yes | native |
| [exact desired at and after expiry fences](exact-desired-at-and-after-expiry-fences.case.json) | yes | native |
| [exact desired before expiry is accepted](exact-desired-before-expiry-is-accepted.case.json) | yes | native |
| [initial expired candidate never gets authority](initial-expired-candidate-never-gets-authority.case.json) | yes | native |
| [initial no prior valid readback is exempt](initial-no-prior-valid-readback-is-exempt.case.json) | yes | native |
| [intermediate after expiry completion first must fence](intermediate-after-expiry-completion-first-must-fence.case.json) | yes | native |
| [intermediate after expiry timer first stays fenced](intermediate-after-expiry-timer-first-stays-fenced.case.json) | yes | native |
| [intermediate at expiry completion first must fence](intermediate-at-expiry-completion-first-must-fence.case.json) | yes | native |
| [intermediate at expiry timer first stays fenced](intermediate-at-expiry-timer-first-stays-fenced.case.json) | yes | native |
| [intermediate before expiry retains valid proof](intermediate-before-expiry-retains-valid-proof.case.json) | yes | native |
| [intermediate monotonic expiry alone fences](intermediate-monotonic-expiry-alone-fences.case.json) | yes | native |
| [intermediate wall expiry alone fences](intermediate-wall-expiry-alone-fences.case.json) | yes | native |
| [late read and applied after terminal fence are inert](late-read-and-applied-after-terminal-fence-are-inert.case.json) | yes | native |
| [ordinary missing or different generation cannot restore authority](ordinary-missing-or-different-generation-cannot-restore-authority.case.json) | yes | native |
| [pre expiry missing and mismatch keep specific halt reasons](pre-expiry-missing-and-mismatch-keep-specific-halt-reasons.case.json) | yes | native |
| [prior and error reads do not extend expired authority](prior-and-error-reads-do-not-extend-expired-authority.case.json) | yes | native |
| [stale read cannot install its record](stale-read-cannot-install-its-record.case.json) | yes | native |
