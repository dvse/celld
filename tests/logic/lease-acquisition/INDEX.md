# lease-acquisition

34 cases; 34 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [Ambiguous takeover preserves displaced owner on readback](ambiguous-takeover-preserves-displaced-owner-on-readback.case.json) | yes | native |
| [Cancelled capacity claim yields freed residency to survivor](cancelled-capacity-claim-yields-freed-residency-to-survivor.case.json) | yes | native |
| [Cancelled live join restores ownership-only landing](cancelled-live-join-restores-ownership-only-landing.case.json) | yes | native |
| [Cancelled queue generation cannot expire rejoined demand](cancelled-queue-generation-cannot-expire-rejoined-demand.case.json) | yes | native |
| [Cancelled queued restore retains acquired epoch dormant](cancelled-queued-restore-retains-acquired-epoch-dormant.case.json) | yes | native |
| [Cancelled recovery backoff cannot resurrect demand](cancelled-recovery-backoff-cannot-resurrect-demand.case.json) | yes | native |
| [Capacity refusal survives equal sample and resets on newer sample](capacity-refusal-survives-equal-sample-and-resets-on-newer-sample.case.json) | yes | native |
| [Claim cohort survives initiator cancellation](claim-cohort-survives-initiator-cancellation.case.json) | yes | native |
| [Concurrent equal capacity samples compose their reservations](concurrent-equal-capacity-samples-compose-their-reservations.case.json) | yes | native |
| [Conflict consumes newer released epoch and rejects late old CAS](conflict-consumes-newer-released-epoch-and-rejects-late-old-cas.case.json) | yes | native |
| [Dead-owner backoff yields admission then rechecks changed owner](dead-owner-backoff-yields-admission-then-rechecks-changed-owner.case.json) | yes | native |
| [Definite acquire failure releases next-cell admission](definite-acquire-failure-releases-next-cell-admission.case.json) | yes | native |
| [Different self epoch after ambiguous CAS requires new claim](different-self-epoch-after-ambiguous-cas-requires-new-claim.case.json) | yes | native |
| [Expired middle waiter cannot strand its successor](expired-middle-waiter-cannot-strand-its-successor.case.json) | yes | native |
| [Foreign lease read failure never authorizes takeover](foreign-lease-read-failure-never-authorizes-takeover.case.json) | yes | native |
| [Incompatible live owner cannot be seized and later recovers](incompatible-live-owner-cannot-be-seized-and-later-recovers.case.json) | yes | native |
| [Last owner-read waiter cancellation suppresses unnecessary claim](last-owner-read-waiter-cancellation-suppresses-unnecessary-claim.case.json) | yes | native |
| [Live join of dormant claim waits for actual capacity release](live-join-of-dormant-claim-waits-for-actual-capacity-release.case.json) | yes | native |
| [Monotonic expiry rejects a rolled-back wall observation](monotonic-expiry-rejects-a-rolled-back-wall-observation.case.json) | yes | native |
| [Old epoch failure cannot invalidate newer owner route](old-epoch-failure-cannot-invalidate-newer-owner-route.case.json) | yes | native |
| [Old node failure cannot invalidate same-epoch capacity route](old-node-failure-cannot-invalidate-same-epoch-capacity-route.case.json) | yes | native |
| [Ownership-only handoff can acquire above residency cap](ownership-only-handoff-can-acquire-above-residency-cap.case.json) | yes | native |
| [Parallel claims finish in reverse order](parallel-claims-finish-in-reverse-order.case.json) | yes | native |
| [Partial cancellation retains one queued route](partial-cancellation-retains-one-queued-route.case.json) | yes | native |
| [Persistent ambiguous acquisitions terminate and later recover](persistent-ambiguous-acquisitions-terminate-and-later-recover.case.json) | yes | native |
| [Publish failure holds joiners through cleanup before retry](publish-failure-holds-joiners-through-cleanup-before-retry.case.json) | yes | native |
| [Reconcile-read timeout releases unrelated activation](reconcile-read-timeout-releases-unrelated-activation.case.json) | yes | native |
| [Recovery budget exhaustion does not poison a later sealed-owner acquisition](recovery-budget-exhaustion-does-not-poison-a-later-sealed-owner-acquisition.case.json) | yes | native |
| [Recovery completion retains old CAS guard under ownership race](recovery-completion-retains-old-cas-guard-under-ownership-race.case.json) | yes | native |
| [Rejected claim follows remote winner for all waiters](rejected-claim-follows-remote-winner-for-all-waiters.case.json) | yes | native |
| [Stale capacity handoff refuses only its own caller](stale-capacity-handoff-refuses-only-its-own-caller.case.json) | yes | native |
| [Timed-out owner read cannot settle replacement attempt](timed-out-owner-read-cannot-settle-replacement-attempt.case.json) | yes | native |
| [Timed-out runtime startup retains exclusive ownership until completion](timed-out-runtime-startup-retains-exclusive-ownership-until-completion.case.json) | yes | native |
| [Unknown capacity preserves idle incumbent through waiter timeout](unknown-capacity-preserves-idle-incumbent-through-waiter-timeout.case.json) | yes | native |
