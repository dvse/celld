# rpc

96 cases; 96 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [A bodyless Response keeps a null body through host marker revival rather than acquiring a stream](a-bodyless-response-keeps-a-null-body-through-host-marker-revival-rather-than-acquiring-a-stream.case.json) | no | topology |
| [A callback rejection contaminates five pending siblings or poisons the next broadcast.](a-callback-rejection-contaminates-five-pending-siblings-or-poisons-the-next-broadcast.case.json) | no | topology |
| [A capability returned from a reverse callback must outlive both callback parameter scope and parent](a-capability-returned-from-a-reverse-callback-must-outlive-both-callback-parameter-scope-and-parent.case.json) | no | topology |
| [A lifted sparse array preserves holes and trailing length rather than densifying or truncating](a-lifted-sparse-array-preserves-holes-and-trailing-length-rather-than-densifying-or-truncating.case.json) | no | topology |
| [A parameter retained without dup must become unusable after its call returns](a-parameter-retained-without-dup-must-become-unusable-after-its-call-returns.case.json) | no | topology |
| [A pending asynchronous rejection must not serialize unrelated invocation completion on that lane](a-pending-asynchronous-rejection-must-not-serialize-unrelated-invocation-completion-on-that-lane.case.json) | no | topology |
| [A rejected retained callback must stay registered for later successful calls](a-rejected-retained-callback-must-stay-registered-for-later-successful-calls.case.json) | no | topology |
| [A rejecting admitted callback prevents queued work from using its freed slot while another slot remains occupied.](a-rejecting-admitted-callback-prevents-queued-work-from-using-its-freed-slot-while-another-slot-rema.case.json) | no | topology |
| [A remote retained duplicate of a result child must survive result-group disposal](a-remote-retained-duplicate-of-a-result-child-must-survive-result-group-disposal.case.json) | no | topology |
| [A saturated document lane wrongly causes head-of-line blocking for an independent Git lane.](a-saturated-document-lane-wrongly-causes-head-of-line-blocking-for-an-independent-git-lane.case.json) | no | topology |
| [A synchronous target exception must advance the invocation lane exactly once](a-synchronous-target-exception-must-advance-the-invocation-lane-exactly-once.case.json) | no | topology |
| [A throwing argument getter aborts projection before later getters or receiver side effects](a-throwing-argument-getter-aborts-projection-before-later-getters-or-receiver-side-effects.case.json) | no | topology |
| [A throwing property resolution must release ordered dispatch for the following method](a-throwing-property-resolution-must-release-ordered-dispatch-for-the-following-method.case.json) | no | topology |
| [Aliased references in one result group must not over-release an explicit survivor duplicate](aliased-references-in-one-result-group-must-not-over-release-an-explicit-survivor-duplicate.case.json) | no | topology |
| [Argument projection snapshots enumerable getters only once before fallback capability lifting](argument-projection-snapshots-enumerable-getters-only-once-before-fallback-capability-lifting.case.json) | no | topology |
| [Binding a prototype method onto an own field must not expose that field](binding-a-prototype-method-onto-an-own-field-must-not-expose-that-field.case.json) | no | topology |
| [bindings](bindings.case.json) | no | example |
| [Blob serialization respects typed-array source view boundaries and pre-construction copying](blob-serialization-respects-typed-array-source-view-boundaries-and-pre-construction-copying.case.json) | no | topology |
| [Buffered Request transport preserves HTTP metadata and binary body when consumed only by the RPC recipient](buffered-request-transport-preserves-http-metadata-and-binary-body-when-consumed-only-by-the-rpc-rec.case.json) | no | topology |
| [callback continuation](callback-continuation.case.json) | no | http |
| [Callee rejection before callback use must release its borrowed handle without revoking original](callee-rejection-before-callback-use-must-release-its-borrowed-handle-without-revoking-original.case.json) | no | topology |
| [Cancelling middle queued requests leaks an application admission slot or dispatches cancelled effects.](cancelling-middle-queued-requests-leaks-an-application-admission-slot-or-dispatches-cancelled-effect.case.json) | no | topology |
| [Child capability returned by a target owns an independent lifetime from its parent](child-capability-returned-by-a-target-owns-an-independent-lifetime-from-its-parent.case.json) | no | topology |
| [Clone Headers with merged ordinary entries and separate Set-Cookie entries as a detached snapshot](clone-headers-with-merged-ordinary-entries-and-separate-set-cookie-entries-as-a-detached-snapshot.case.json) | no | topology |
| [Completed observer replacement must release the old route and never call it again](completed-observer-replacement-must-release-the-old-route-and-never-call-it-again.case.json) | no | topology |
| [cross cell continuation](cross-cell-continuation.case.json) | no | http |
| [Disposing a child then its containing result must be idempotent and preserve its sibling](disposing-a-child-then-its-containing-result-must-be-idempotent-and-preserve-its-sibling.case.json) | no | topology |
| [DO lifecycle handlers are not ordinary callable RPC methods](do-lifecycle-handlers-are-not-ordinary-callable-rpc-methods.case.json) | no | topology |
| [do property](do-property.case.json) | no | http |
| [dup lifetime](dup-lifetime.case.json) | no | example |
| [Duplicate-of-duplicate must remain owned after both ancestor handles are released](duplicate-of-duplicate-must-remain-owned-after-both-ancestor-handles-are-released.case.json) | no | topology |
| [Explicit getter grants access without exposing own instance data](explicit-getter-grants-access-without-exposing-own-instance-data.case.json) | no | topology |
| [File revival keeps File subtype, Unicode name and an explicit zero lastModified](file-revival-keeps-file-subtype-unicode-name-and-an-explicit-zero-last-modified.case.json) | no | topology |
| [Fire-and-forget notification rejection must neither reorder nor evict a retained observer](fire-and-forget-notification-rejection-must-neither-reorder-nor-evict-a-retained-observer.case.json) | no | topology |
| [Getter exception crosses RPC once without duplicate evaluation](getter-exception-crosses-rpc-once-without-duplicate-evaluation.case.json) | no | topology |
| [Ignore non-enumerable and symbol-keyed data during projection even when hidden fields would throw or fail cloning](ignore-non-enumerable-and-symbol-keyed-data-during-projection-even-when-hidden-fields-would-throw-or.case.json) | no | topology |
| [Increment and read object state through RPC methods](increment-and-read-object-state-through-rpc-methods.case.json) | yes | http |
| [Inherited application prototype methods remain callable](inherited-application-prototype-methods-remain-callable.case.json) | no | topology |
| [Keep concurrent successful clone results and an exception attached to their own calls](keep-concurrent-successful-clone-results-and-an-exception-attached-to-their-own-calls.case.json) | no | topology |
| [Keep cyclic mixed container topology intact when a returned RpcTarget forces the lifted envelope](keep-cyclic-mixed-container-topology-intact-when-a-returned-rpc-target-forces-the-lifted-envelope.case.json) | no | topology |
| [Local argument-encoding refusal must not leave a sender-lane sequence gap](local-argument-encoding-refusal-must-not-leave-a-sender-lane-sequence-gap.case.json) | no | topology |
| [Nested capability forwarding under modern parameter duplication must preserve both caller handles](nested-capability-forwarding-under-modern-parameter-duplication-must-preserve-both-caller-handles.case.json) | no | topology |
| [Nested returned capability preserves recipient provenance inside arrays](nested-returned-capability-preserves-recipient-provenance-inside-arrays.case.json) | no | topology |
| [Non-RpcTarget class instance cannot silently clone private-looking fields](non-rpc-target-class-instance-cannot-silently-clone-private-looking-fields.case.json) | no | topology |
| [One capability waiting at an application barrier must not globally block another target](one-capability-waiting-at-an-application-barrier-must-not-globally-block-another-target.case.json) | no | topology |
| [One detached callback failure blocks unrelated foreground traffic or hides failed background work.](one-detached-callback-failure-blocks-unrelated-foreground-traffic-or-hides-failed-background-work.case.json) | no | topology |
| [One failing concurrent borrow must not dispose another in-flight borrow of the same callback](one-failing-concurrent-borrow-must-not-dispose-another-in-flight-borrow-of-the-same-callback.case.json) | no | topology |
| [One held callback incorrectly stalls five independent notifications and metadata RPC.](one-held-callback-incorrectly-stalls-five-independent-notifications-and-metadata-rpc.case.json) | no | topology |
| [Ordinary DO RPC must not expose an instance arrow field](ordinary-do-rpc-must-not-expose-an-instance-arrow-field.case.json) | no | topology |
| [Ordinary own __proto__ data survives lifting without altering the cloned object's prototype](ordinary-own-proto-data-survives-lifting-without-altering-the-cloned-object-s-prototype.case.json) | no | topology |
| [Ordinary RPC clones ArrayBuffer-backed arguments without detaching or sharing the caller's buffer](ordinary-rpc-clones-array-buffer-backed-arguments-without-detaching-or-sharing-the-caller-s-buffer.case.json) | no | topology |
| [Own function properties remain accessible on a callable RPC capability](own-function-properties-remain-accessible-on-a-callable-rpc-capability.case.json) | no | topology |
| [Permit inherited prototype accessor returning callable while preserving method receiver](permit-inherited-prototype-accessor-returning-callable-while-preserving-method-receiver.case.json) | no | topology |
| [Permit ordinary DO scheduled method because pinned workerd does not reserve that name](permit-ordinary-do-scheduled-method-because-pinned-workerd-does-not-reserve-that-name.case.json) | no | topology |
| [Pipelined function under a getter retains its intended receiver](pipelined-function-under-a-getter-retains-its-intended-receiver.case.json) | no | topology |
| [Pipelined getter path reaches only its granted nested child](pipelined-getter-path-reaches-only-its-granted-nested-child.case.json) | no | topology |
| [Plain result object is a detached by-value snapshot](plain-result-object-is-a-detached-by-value-snapshot.case.json) | no | topology |
| [Preserve cyclic by-value graph identity across object, array, Map keys and Set membership without sharing caller memory](preserve-cyclic-by-value-graph-identity-across-object-array-map-keys-and-set-membership-without-shar.case.json) | no | topology |
| [Preserve Date/RegExp native clone behavior instead of traversing their properties during capability lift](preserve-date-reg-exp-native-clone-behavior-instead-of-traversing-their-properties-during-capability.case.json) | no | topology |
| [Preserve non-JSON numeric representations and explicit undefined slots within a capability-bearing envelope](preserve-non-json-numeric-representations-and-explicit-undefined-slots-within-a-capability-bearing-e.case.json) | no | topology |
| [Private slot does not collide with public method containing hash character](private-slot-does-not-collide-with-public-method-containing-hash-character.case.json) | no | topology |
| [Propagate an asynchronous callee rejection after one completed reverse callback without replaying the callback](propagate-an-asynchronous-callee-rejection-after-one-completed-reverse-callback-without-replaying-th.case.json) | no | topology |
| [Public DO prototype getter is available as asynchronous property](public-do-prototype-getter-is-available-as-asynchronous-property.case.json) | no | topology |
| [Reject a lazy RpcProperty embedded as data without consuming the property's later ordinary fetch](reject-a-lazy-rpc-property-embedded-as-data-without-consuming-the-property-s-later-ordinary-fetch.case.json) | no | topology |
| [Reject a non-cloneable Set member atomically after traversing a Set self-cycle](reject-a-non-cloneable-set-member-atomically-after-traversing-a-set-self-cycle.case.json) | no | topology |
| [Reject an own callable accessor before invoking its getter](reject-an-own-callable-accessor-before-invoking-its-getter.case.json) | no | topology |
| [Reject an unresolved RpcPromise embedded as argument data while preserving its original awaitability](reject-an-unresolved-rpc-promise-embedded-as-argument-data-while-preserving-its-original-awaitabilit.case.json) | no | topology |
| [Reject native Promise values nested in arguments without treating them as top-level return thenables](reject-native-promise-values-nested-in-arguments-without-treating-them-as-top-level-return-thenables.case.json) | no | topology |
| [Reject nested null-prototype objects before ordinary structured clone can erase their unsupported prototype](reject-nested-null-prototype-objects-before-ordinary-structured-clone-can-erase-their-unsupported-pr.case.json) | no | topology |
| [Repeated disposal of the same handle must not re-enter the target or release twice](repeated-disposal-of-the-same-handle-must-not-re-enter-the-target-or-release-twice.case.json) | no | topology |
| [Repeated same-handle parameters must not consume original ownership twice](repeated-same-handle-parameters-must-not-consume-original-ownership-twice.case.json) | no | topology |
| [Retain a thrown DOMException's semantic name instead of reducing every exception to Error](retain-a-thrown-domexception-s-semantic-name-instead-of-reducing-every-exception-to-error.case.json) | no | topology |
| [Retain backing-buffer aliasing, view types and offsets when binary leaves share a result with a capability](retain-backing-buffer-aliasing-view-types-and-offsets-when-binary-leaves-share-a-result-with-a-capab.case.json) | no | topology |
| [Retaining a duplicate before throwing must preserve the retained lease past exceptional return](retaining-a-duplicate-before-throwing-must-preserve-the-retained-lease-past-exceptional-return.case.json) | no | topology |
| [Returned bound function retains private-field receiver](returned-bound-function-retains-private-field-receiver.case.json) | no | topology |
| [Returning a background dispatch loses borrowed callback authority or strands its outstanding jobs.](returning-a-background-dispatch-loses-borrowed-callback-authority-or-strands-its-outstanding-jobs.case.json) | no | topology |
| [Reverse callback failure must clean each borrowed invocation independently](reverse-callback-failure-must-clean-each-borrowed-invocation-independently.case.json) | no | topology |
| [Reverse callback reentry into the exact pending capability must not deadlock](reverse-callback-reentry-into-the-exact-pending-capability-must-not-deadlock.case.json) | no | topology |
| [Route an explicit service binding with bound caller context](route-an-explicit-service-binding-with-bound-caller-context.case.json) | no | topology |
| [router](router.case.json) | yes | example |
| [rpc dispose](rpc-dispose.case.json) | no | example |
| [rpc errors](rpc-errors.case.json) | no | http |
| [RPC property handle stays lazy and refetches on each await](rpc-property-handle-stays-lazy-and-refetches-on-each-await.case.json) | no | topology |
| [rpc surface](rpc-surface.case.json) | no | http |
| [RpcTarget arrow fields stay hidden despite being callable values](rpc-target-arrow-fields-stay-hidden-despite-being-callable-values.case.json) | no | topology |
| [RpcTarget permits lifecycle names that DO reserves](rpc-target-permits-lifecycle-names-that-do-reserves.case.json) | no | topology |
| [self forward](self-forward.case.json) | no | example |
| [Separate exports of the same raw RpcTarget create independent disposal cohorts](separate-exports-of-the-same-raw-rpc-target-create-independent-disposal-cohorts.case.json) | no | topology |
| [Snapshot provider result getters once per call even when each result also mints a capability](snapshot-provider-result-getters-once-per-call-even-when-each-result-also-mints-a-capability.case.json) | no | topology |
| [stateless continuation](stateless-continuation.case.json) | no | http |
| [Successful parameter auto-release must preserve the modern caller-owned handle](successful-parameter-auto-release-must-preserve-the-modern-caller-owned-handle.case.json) | no | topology |
| [Taking a retained callback into a returned result must transfer its surviving lease](taking-a-retained-callback-into-a-returned-result-must-transfer-its-surviving-lease.case.json) | no | topology |
| [Three callback-to-owner reentries deadlock behind three unrelated slow subscribers.](three-callback-to-owner-reentries-deadlock-behind-three-unrelated-slow-subscribers.case.json) | no | topology |
| [Treat an Error nested in a successful result as data rather than a remote exception envelope](treat-an-error-nested-in-a-successful-result-as-data-rather-than-a-remote-exception-envelope.case.json) | no | topology |
| [Two retained slots duplicating one native callback must release independently](two-retained-slots-duplicating-one-native-callback-must-release-independently.case.json) | no | topology |
| [Validate custom prototypes in Map keys as well as Map values before dispatch](validate-custom-prototypes-in-map-keys-as-well-as-map-values-before-dispatch.case.json) | no | topology |
