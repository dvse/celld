# dynamic-workers-and-tails

13 cases; 13 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [Cancel an observed in-flight loaded fetch and reuse entrypoint](cancel-an-observed-in-flight-loaded-fetch-and-reuse-entrypoint.case.json) | no | topology |
| [Do not share explicit binding authority across two loaded workers](do-not-share-explicit-binding-authority-across-two-loaded-workers.case.json) | no | topology |
| [dynamic worker tails](dynamic-worker-tails.case.json) | yes | example |
| [Grant only explicitly supplied child environment keys](grant-only-explicitly-supplied-child-environment-keys.case.json) | no | topology |
| [Honor verify-before-run without killing a worker after method rejection](honor-verify-before-run-without-killing-a-worker-after-method-rejection.case.json) | no | topology |
| [island lockdown](island-lockdown.case.json) | no | example |
| [Keep an invalid old bundle failed while its syntax-fixed version runs](keep-an-invalid-old-bundle-failed-while-its-syntax-fixed-version-runs.case.json) | no | topology |
| [Keep loaded environment snapshot after caller deletes and adds keys](keep-loaded-environment-snapshot-after-caller-deletes-and-adds-keys.case.json) | no | topology |
| [Recover a missing module dependency with a complete versioned graph](recover-a-missing-module-dependency-with-a-complete-versioned-graph.case.json) | no | topology |
| [Reject all entrypoint uses of a failed module and repair with a new key](reject-all-entrypoint-uses-of-a-failed-module-and-repair-with-a-new-key.case.json) | no | topology |
| [Reject pre-aborted loaded fetch before dispatch then reuse worker](reject-pre-aborted-loaded-fetch-before-dispatch-then-reuse-worker.case.json) | no | topology |
| [Resolve loaded Root class independently from supervisor Root](resolve-loaded-root-class-independently-from-supervisor-root.case.json) | no | topology |
| [Separate same-named Gadget classes from different loaded modules](separate-same-named-gadget-classes-from-different-loaded-modules.case.json) | no | topology |
