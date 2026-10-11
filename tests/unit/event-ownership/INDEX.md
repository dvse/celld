# event-ownership

11 cases; 11 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [a granted waiter dropped before it runs passes the turn on](a-granted-waiter-dropped-before-it-runs-passes-the-turn-on.case.json) | no | cargo |
| [a waiter dropped before its grant is skipped](a-waiter-dropped-before-its-grant-is-skipped.case.json) | no | cargo |
| [actor context is shared until incarnation release](actor-context-is-shared-until-incarnation-release.case.json) | no | cargo |
| [actor resource preserves event driver during foreign turn](actor-resource-preserves-event-driver-during-foreign-turn.case.json) | no | cargo |
| [adopted resource does not retain unrelated native ops](adopted-resource-does-not-retain-unrelated-native-ops.case.json) | no | cargo |
| [cancellation drains accepted ownership before filtering](cancellation-drains-accepted-ownership-before-filtering.case.json) | no | cargo |
| [capability continuations drain without reopening invalidated heaps](capability-continuations-drain-without-reopening-invalidated-heaps.case.json) | no | cargo |
| [critical section cannot borrow driver after retirement](critical-section-cannot-borrow-driver-after-retirement.case.json) | no | cargo |
| [dead reaction cannot borrow running context](dead-reaction-cannot-borrow-running-context.case.json) | no | cargo |
| [shutdown abandons even accepted adopted work](shutdown-abandons-even-accepted-adopted-work.case.json) | no | cargo |
| [stateless retirement drains before abandoning](stateless-retirement-drains-before-abandoning.case.json) | no | cargo |
