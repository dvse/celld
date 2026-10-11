# celld test suite

Tests are organised by the behaviour they prove. Source project, historical wave
and old case IDs are provenance in each `*.case.json` header and MANIFEST.json;
they are not test categories. The layers follow `docs/testing.md`.

```
tests/
  unit/                       input gates, object identity, event ownership,
                              RPC, store and LTX components
  logic/                      output gates, lease acquisition/continuity,
                              pressure, log recovery, wake recovery,
                              simulation and specification
  conformance/
    fetch-and-http/            requests, bodies, redirects and stream transport
    web-platform/             globals, timers, encoding, URL and promises
    rpc/                      visibility, cloning, ordering and capabilities
    durable-objects/
      lifecycle/              activation, event ownership and replacement
      storage-sql/            SQLite isolation, transactions and recovery
      storage-kv/             key/value persistence, listing and rollback
      alarms/                 scheduling and recovery
      websockets/             socket events, ownership and close
      facets/                 dynamic object identity and storage isolation
      persistent-stubs/       retained capability restoration and disposal
      placement-and-routing/  namespace, environment and process placement
    bindings/                 KV, R2, D1, queues, workflows, assets and containers
    dynamic-workers-and-tails/ loading, module identity and tails
    languages/                Python and WASM
    limits-and-errors/        resource quotas, admission and exhaustion
  faults/                     process failure, lease fencing and store outages
  regressions/<finding-id>/   fix-lane owned; see CONTRACT.md
  hyperbob-expected.json      expected output of each ../tests-hyperbob/ runner
  lib/                        shared runners, fixtures and provenance indexes
  MANIFEST.json               generated aggregate of case headers
  RESULTS.md / RESULTS.json   latest completed profile
  run.sh                      one entry point
```

This public copy omits the lab's qualification evidence, raw run artifacts and review
records (`evidence/`, `artifacts/`, `reviews/`); RESULTS and the indexes still name those
records by path. `$LAB` and `$FLEET_HOME` in provenance stand for the lab workstation's and
the test fleet host's working roots.

The regression layer also runs every `tests-hyperbob/<name>/` shape runner
(`run.sh` or `run.py`) on celld as case `hyperbob/<name>` and matches its output
against `tests/hyperbob-expected.json` (64-hex ids vary per run); a runner
without a recorded expectation is reported not applicable with its reason.

A feature directory contains readable case headers and shared `fixtures/`.
A header names the invariant, all origins/legacy aliases, source, adapter,
request sequence or Rust filter, profiles, and a concrete applicability reason.
Imported assertion bytes are unchanged. Design-only entries use `*.design.json`
and do not earn runnable-case credit. Fixtures shared across features have one
physical home and are referenced from the appropriate case headers.

## Run

```
tests/run.sh --profile quick|full [--layer unit|logic|conformance|faults|regressions]
             [--runtime celld|workerd|both] [--case SUBSTRING]
```

Quick runs locally in minutes. Full runs simulation and live fleet faults on
a fleet host (ssh alias `$CELLD_FLEET_HOST`), using fresh owned directories under `~/celld-tests-20261010`, ports
9800–9899, an exclusive lane lock and at most eight build jobs per source build (16 total). Native checks
and runtime fixtures run serially. No Bazel or workerd builds are used; stock
workerd is a pinned prebuilt npm binary. No paid cloud or credentials are needed.
`--case` accepts a behaviour ID or a legacy ID from the provenance metadata.

Python 3.11+, Rust and Node.js are required locally. Campaign qualification on
the fleet host additionally uses Python with `os.setns`, delegated user cgroups and
unprivileged mount namespaces. Full profiles use the two exact
source builds recorded in the fleet host's `phase2/builds/BUILD-RECEIPTS.json`. Each run
freezes matching crates plus the current suite, and compares against official
stock workerd. The fixed qualification pin and build receipts are in RESULTS.
`tests/lib/provision.sh` reconstructs official checksum-verified tools and
builds celld, esbuild and the WASM tooling from source; it requires the copied
checkpoint inputs documented in [phase2/README](lib/phase2/README.md).
No prebuilt esbuild or checkpoint celld enters the primary matrix. Historical
candidate002 runs only the separately labelled VM gates. `CELLD_BIN`,
`WORKERD_BIN` and `CELLD_ESBUILD` select explicit binaries for focused checks.

Full runs export a fresh snapshot and preserve stopped-node state and prior
attempts. The result export contains reviewable logs/receipts and hashes of
retained remote state; binaries, disks and credentials are excluded.

Every selected case/runtime produces the same JSON schema: `id`, `layer`,
`runtime`, `status` (pass/fail/expected-fail/not-applicable), `reason`,
`duration_ms` and `artifacts`. Original HTTP pairs require identical observations and successful assertions;
a mismatch fails both rows and retains one diff. New authored corpus adapters
report each runtime’s own assertions and retain paired assertion comparisons;
identity/timing witnesses are not compared as payloads. Missing prerequisites never earn a pass. Exit 1 means
at least one failure; complete evidence is still written. A single-runtime run
records assertions/observations without claiming a differential verdict.

## Inventory and provenance

`python3 tests/lib/inventory.py` rebuilds MANIFEST.json from the behaviour
headers. `python3 tests/lib/verify-inventory.py --results` verifies source
hashes, corpus coverage, aliases, behaviour placement and full result coverage.
`python3 tests/lib/import-regressions.py` reads committed sibling `fixes`
regressions without modifying that clone; CONTRACT.md defines their interface.

Counts are logical cases, not assertions, repetitions or seeds. Multiple source
copies of an assertion share a case and list all provenance. Distinct traces
or stronger oracles remain separate even when they concern the same API.
All 671 reviewed corpus identities and 115 non-promoting designs are indexed;
the accepted R027 replacement adds no case. See `lib/provenance/DEDUPLICATION.md`
for the overlap audit. `lib/SOURCES.json` pins imported bytes; provenance indexes
retain the original manifests and qualification notes. VM and five-process harnesses are implemented; remaining WPT, TLA and language/container applicability limits are explicit per case.
