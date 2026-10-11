# Case identity and overlap audit

The primary key is now `layer/behaviour/invariant`, with human-readable case
headers next to the relevant feature. All 610 earlier IDs map one-to-one in
`PATH-MIGRATION.json`. Neither source family nor wave contributes to an active
case ID or its placement. The 461 reviewed and 114 excluded corpus identities
remain provenance, allowing the original census to be audited exactly.

Deduplication uses the complete trace and oracle. A helper copied into another
fixture is not another test. `IDENTICAL-SOURCES.json` records eleven groups of
identical imported/adapter source files, their hashes and all origins. One
physical file is retained in the active tree; other required filenames are
relative symlinks. Pre-migration copies remain under the ignored raw migration
artifacts. In particular:

- The base RPC assertions copied into the accessor fixture count once. The
  accessor fixture contributes only its three new getter/receiver/name traces.
- The accepted transient-storage rejection revision replaces R027; its earlier
  body and review history remain source evidence and earn no second case.
- Original workerd globals and the adapter's identical assertion module share
  one source. Each exported assertion runs once per runtime, through its HTTP
  adapter. The original `.wd-test` config is provenance, not another test.
- Original actor KV assertions and the HTTP adapter share one source and one
  case. The selected prefix-list, transaction rollback and SQL cases remain
  distinct: the original operation smoke test does not assert their values.
- Each pinned WPT assertion file and its adapter copy share one source and one
  logical case. Subtest results remain in observations; subtests are not extra
  top-level case credit.
- Repeated deployment frontends, metadata files, HTTP job helpers and inherited
  shell runners are shared support code, not test cases.

Related cases were inspected rather than merged solely by API name. A fetch
counter, a counter after a timer and an RPC counter exercise different dispatch
paths. Receiver visibility, remote error encoding, capability disposal and
process ownership each have distinct traces or oracles, even when a fixture
also performs a common positive-control call. Keeping those cases preserves
coverage. No independently inventoried full trace/oracle was found to be an
exact duplicate. The count remains 610; duplicate source copies add zero.

`verify-inventory.py` rejects duplicate execution contracts (source, adapter
fixture, exact selector/filter, request sequence and mutation), duplicate IDs
or aliases, missing provenance and any imported-byte change. This is a useful
mechanical check, not a claim that hashes prove semantic independence.

Original archive manifests/pins retain their historical relative paths and
wording. `SOURCES.json` and `PATH-MIGRATION.json` resolve those to current paths.
For inspecting an original runner's imports, `lib/materialize-source.py` can
reconstruct an unchanged source tree in a **new** artifact directory. It never
executes historical deployment/cleanup scripts. Those scripts retain their
qualification requirements and do not become runnable by being relocated.

A later read-only audit of fixes-lane `tests-scratch` commit
`aabe1508e18d48f8d0199f8f49b70b3653957d1c` found all 262 vendor files already
migrated byte-for-byte. `SCRATCH-AUDIT.json` maps each to its active source.
They are reused from the existing behaviour tree and add no files or cases.

Phase 2 imports 210 additional primary cases and V216 characterization from
TRANCHE-001 through TRANCHE-007. The cumulative census is 786 designs: 671
primary and 115 characterization. `../phase2/CAMPAIGN.json` maps each imported
identity, all 202 immutable file hashes, tranche/review receipts and identical
ready-functional/bodyfix aliases. Aliases earn no additional case credit.
