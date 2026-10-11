# durable-objects/lifecycle

34 cases; 34 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [actor io](actor-io.case.json) | no | example |
| [Added class namespace stays distinct across cold upgrade](added-class-namespace-stays-distinct-across-cold-upgrade.case.json) | no | deployment |
| [Additive schema survives replacement and cold restore](additive-schema-survives-replacement-and-cold-restore.case.json) | no | deployment |
| [Alarm dedup ledger survives handler replacement](alarm-dedup-ledger-survives-handler-replacement.case.json) | no | deployment |
| [Binding rename preserves original class namespace](binding-rename-preserves-original-class-namespace.case.json) | no | deployment |
| [Cold startup selects published replacement before any reload](cold-startup-selects-published-replacement-before-any-reload.case.json) | no | deployment |
| [Compatible rollback preserves extension data](compatible-rollback-preserves-extension-data.case.json) | no | deployment |
| [Concurrent upgrade migrations apply once](concurrent-upgrade-migrations-apply-once.case.json) | no | deployment |
| [context ownership](context-ownership.case.json) | no | http |
| [DDL migration abort rolls back copy and drop](ddl-migration-abort-rolls-back-copy-and-drop.case.json) | no | deployment |
| [Deferred alarm sees replacement schema after recovery](deferred-alarm-sees-replacement-schema-after-recovery.case.json) | no | deployment |
| [Entered old calls finish consistently during live generation flip](entered-old-calls-finish-consistently-during-live-generation-flip.case.json) | no | deployment |
| [Failed manifest upload retains old selector and permits retry](failed-manifest-upload-retains-old-selector-and-permits-retry.case.json) | no | deployment |
| [Failed unique index backfill remains retryable](failed-unique-index-backfill-remains-retryable.case.json) | no | deployment |
| [Future alarm executes replacement handler after cold boot](future-alarm-executes-replacement-handler-after-cold-boot.case.json) | no | deployment |
| [Readdress one named object through valid public helpers](identity-admission-a201.case.json) | no | http |
| [Reopen isolated unique IDs from serialized addresses](identity-admission-a202.case.json) | no | http |
| [Preserve full routing past the name metadata boundary](identity-admission-a203.case.json) | no | http |
| [Admit first requests after successful constructor initialization](identity-admission-a204.case.json) | no | http |
| [Gate one live root while its same-class peer progresses](identity-admission-a205.case.json) | no | http |
| [Interrupted module upload cannot select partial version](interrupted-module-upload-cannot-select-partial-version.case.json) | no | deployment |
| [Interrupted named pointer publish preserves prepublication state](interrupted-named-pointer-publish-preserves-prepublication-state.case.json) | no | deployment |
| [Invalid replacement parser failure preserves serving generation](invalid-replacement-parser-failure-preserves-serving-generation.case.json) | no | deployment |
| [Lost deployment acknowledgement keeps committed replacement recoverable](lost-deployment-acknowledgement-keeps-committed-replacement-recoverable.case.json) | no | deployment |
| [mailbox ownership](mailbox-ownership.case.json) | no | example |
| [Missing static dependency fails adoption and valid graph repairs](missing-static-dependency-fails-adoption-and-valid-graph-repairs.case.json) | no | deployment |
| [Mixed lazy schema population stays object-local](mixed-lazy-schema-population-stays-object-local.case.json) | no | deployment |
| [Old generation output proof survives replacement adoption](old-generation-output-proof-survives-replacement-adoption.case.json) | no | deployment |
| [Replacement cancellation survives cold startup](replacement-cancellation-survives-cold-startup.case.json) | no | deployment |
| [Resume a timer before reading and writing object storage](resume-a-timer-before-reading-and-writing-object-storage.case.json) | yes | http |
| [Script rename creates fresh namespace and original remains recoverable](script-rename-creates-fresh-namespace-and-original-remains-recoverable.case.json) | no | deployment |
| [Static named entrypoint switch preserves backend durable state](static-named-entrypoint-switch-preserves-backend-durable-state.case.json) | no | deployment |
| [Transform table units atomically across versions](transform-table-units-atomically-across-versions.case.json) | no | deployment |
| [Unsupported rename fails without disturbing live calls](unsupported-rename-fails-without-disturbing-live-calls.case.json) | no | deployment |
