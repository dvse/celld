# Phase 2 test results

Full qualification on the fleet host: **842 cases per source column**, with stock workerd executed independently alongside each. All 786 designs are accounted for: 671 primary and 115 non-promoting characterization designs.

Primary binaries were built here from `def239b8b5bea70bfe8674f3117d6862f140a711` and fixes HEAD snapshot `c877e5523378b189a4dc3e5798572b8d03a81345` (2026-10-10 18:53 AEST). Rust/unit/logic sources match each binary revision. Build/tool receipts and immutable harness hashes are included in the evidence.

Qualified Git trees: baseline `2edc30524c9b73b3405d7bc3938a14e8d0d7deb7`; fixes `48fc7873e7607a1e1ff904778b3ff8aacd7df22c`. The later `ported` branch contains further changes and is outside this frozen qualification; it is the preferred ref for the next source refresh. These results do not claim coverage of its newer tree.

| Layer / runtime | def239b pass | fail | N/A | fixes pass | fail | N/A |
|---|---:|---:|---:|---:|---:|---:|
| unit / celld | 38 | 0 | 1 | 38 | 0 | 1 |
| unit / workerd | 0 | 0 | 39 | 0 | 0 | 39 |
| logic / celld | 153 | 0 | 1 | 153 | 0 | 1 |
| logic / workerd | 0 | 0 | 154 | 0 | 0 | 154 |
| conformance / celld | 527 | 88 | 6 | 532 | 83 | 6 |
| conformance / workerd | 239 | 231 | 151 | 239 | 231 | 151 |
| faults / celld | 5 | 0 | 1 | 5 | 0 | 1 |
| faults / workerd | 0 | 0 | 6 | 0 | 0 | 6 |
| regressions / celld | 1 | 21 | 0 | 21 | 1 | 0 |
| regressions / workerd | 16 | 0 | 6 | 16 | 0 | 6 |
| TOTAL / celld | 724 | 109 | 9 | 749 | 84 | 9 |
| TOTAL / workerd | 255 | 231 | 356 | 255 | 231 | 356 |

Celld has 26 fail-to-pass changes and 1 pass-to-fail changes between these executions. These observations alone do not establish the cause.

- Pass-to-fail: `conformance/rpc/a-saturated-document-lane-wrongly-causes-head-of-line-blocking-for-an-independent-git-lane` — fixture FAIL: Error: document backlog remains: {"actual":["document4","document2","document3","document5"],"expected":["document2","document3","document4","document5"]}

The fixes column passes 21 of 22 finding regressions. Remaining failures: `regressions/R4-05`.

Counts are case/runtime executions, not assertions or seeds. No expected-failure waiver converts a failure into a pass. The source-authored corpus reports each runtime’s assertions independently and records comparisons. Older exact HTTP differential cases mark both rows failed on mismatch; their raw observations remain available. Failure rows include source-fixture BLOCKED/unsupported-API outcomes and assertion failures; an attempted test is not automatically a completed passing trace.

- **def239b**: `{"fail": 340, "not-applicable": 365, "pass": 979}`; run `20261010-213530-AEST-420254`; 435.3 seconds; [def239b evidence](evidence/phase2-full-20261010-213528-AEST-symlink-audit/def239b/RESULTS.json).
- **fixes**: `{"fail": 315, "not-applicable": 365, "pass": 1004}`; run `20261010-214245-AEST-458014`; 434.0 seconds; [fixes evidence](evidence/phase2-full-20261010-213528-AEST-symlink-audit/fixes/RESULTS.json).

Resumed columns retain all unaffected prior outcomes, including failures, after verifying the same source revision and each retained case contract. New or changed contracts and explicit invalidations always execute. All 31 runtime corpus waves were invalidated and executed with independent resource/deadline supervision and the original recovery freshness preconditions. The 16 newer campaign groups were subsequently replaced again under their exact source limits, kernel cgroup controls and an owned quota filesystem; both missing oracle bundle dependencies were repaired and rerun. Three stock namespace-routing groups and the native alarm include were then explicitly invalidated and requalified. Ancestor raw runs, stop times and both harness receipts are retained; the reported wall time is the final segment, with preceding spans in resumption metadata.

All 671 reviewed primary cases were dispatched on celld. Six declared conformance exclusions remain: two external model-service examples, container and sandbox execution requiring host-wide privileged Docker fencing, the missing Python ABI dependency bundle, and the full WPT tree. Stock workerd has additional explicit N/A rows for celld-specific bucket leases/deployment controls and service backends absent from its standalone binary. [Every former N/A disposition](NA-AUDIT.json) is recorded for both columns.

The two-VM shared-store gate passed on both primary builds. **Cold-restart-v1 failed on both**: count 4, celld snapshot durability and owner release passed, but SeaweedFS exceeded the unchanged 45-second TERM limit and required SIGKILL. Generation 2 was not entered. Exact historical candidate002 also passed shared-store and failed this shutdown boundary; it never entered a primary suite column. [All twelve VM attempts](evidence/phase2-vm/README.md) retain their receipts and raw-state hashes. The separate historical graceful-migration gate cannot be reconstructed from the supplied store helper/run records because its supervisor/client/fixture archive is absent.

[Verdict changes between source revisions](STATUS-CHANGES.json) are observations, not an attribution of every change to a production fix. The same file includes oracle variation between runs. Per-case failures, reasons, full traces and comparisons are indexed in each column’s RESULTS.json. [Harness and provenance](lib/phase2/README.md) describes process identity, clocks, fault controls, staging changes and qualification limits.

Campaign runs use kernel memory/swap/CPU/task limits and a bounded private filesystem; process-count, aggregate RSS and CPU-time checks add independent sampling. Every working file is retained and hash-verified before releasing its mount. [Real exhaustion and escaped-child checks](evidence/phase2-campaign-domain/20261010-202403-AEST/RECEIPT.json) verify those controls. Git-codec uses a fresh deployment/process per case and source-built pinned pako.

Three additional native facet-snapshot assertions passed on the exact fixes source; [their independent receipt](evidence/phase2-native-facet/RECEIPT.json) and source hashes are retained without adding logical-case credit.

All raw logs, stores, binaries and guest disks remain under `~/celld-tests-20261010/phase2` on the fleet host. The committed review export omits credentials and storage payloads and hashes retained files. Exploratory/superseded attempts remain separate and earn no final pass credit.

[Final integrity audit](evidence/phase2-full-20261010-213528-AEST-symlink-audit/VERIFICATION.json): PASS. Both complete columns, all 1,894 prior N/A dispositions, 12 VM attempts, 6 selected VM gates, binary/source pins, resource limits and 14,877 exported file hashes were verified. The audit also indexes retained log symlink targets and their content hashes; the earlier export is preserved.

[Terminal-state check](evidence/phase2-full-20261010-213528-AEST-symlink-audit/TERMINAL.json) found no owned processes, running units or listeners on ports 9800–9899.
