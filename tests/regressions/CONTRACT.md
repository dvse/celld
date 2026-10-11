# Regression contract (published 2026-10-10 AEST)

The fixes lane owns `tests/regressions/<finding-id>/`. The tests lane imports
committed files from its local `fixes` branch without modifying them. The tests
lane owns this contract and discovery in `tests/lib/`.

Preferred interface: put a `case.json` in the finding directory:

```json
{
  "id": "R1-example",
  "description": "The invariant and a concrete reproducer",
  "command": ["python3", "run.py"],
  "runtimes": ["celld"],
  "profiles": ["quick", "full"],
  "timeout_seconds": 120,
  "expected_failure": null
}
```

Commands run in the finding directory. They must use only owned fresh state,
loopback ports 9800–9899 supplied by `CELLD_TEST_PORT_BASE`, and supplied binaries
`CELLD_BIN` / `WORKERD_BIN`. `CELLD_TEST_ARTIFACTS` names a fresh output directory.
`CELLD_TEST_RUNTIME` is `celld` or `workerd`; `CELLD_TEST_PROFILE` is quick/full.
Use exit 0 for pass, 1 for assertion failure, 77 for an unavailable prerequisite
(with a concrete explanation on stdout). The outer runner emits the common JSON
result and retains stdout/stderr. Optional `result.json` may give a reason and
additional artifact paths. Do not print account credentials. Use public dummy
store identities only. No paid cloud, git changes, or external state deletion.

Fixtures may instead provide `run.py` or `run.sh`; the harness discovers these
with a bounded 120-second timeout. Cargo/Rust regression sources without a
runner are inventoried with their concrete build requirement. Existing fix-lane
formats will be adapted in the shared harness, without rewriting owned tests.

Store assertions, fixtures, source pin, expected pre-fix failure, and post-fix
validation together. A finding ID alone is not permission to swallow arbitrary
failures: expected failure is applied only to its documented assertion.

Imports record the fixes commit and imported file hashes. New imports do not
overwrite changed evidence: prior imported versions are retained in provenance.

## Behaviour index and HTTP adapter

Finding directories remain owned and named by the fixes lane. The aggregate
manifest provides their behaviour labels and descriptions; see INDEX.md.
A command of `python3 ../http_case.py` with `expected.json` is recognised by
the shared harness. Its unchanged HTTP fixture and exact expected JSON are
executed through the suite's deploy/node launcher, keeping all listeners within
9800–9899. The original launcher hash, source hashes, actual/expected JSON and
a mismatch diff are retained. This replaces transport setup only.

R4-08 declares two compatibility fixtures. The shared adapter runs both unchanged
fixtures, preserves separate actual/expected observations and diffs, and requires
both to pass for its single case result. The original run.py and helper hashes
remain recorded.

R4-04 supplies native.rs to include in js/ownership_tests.rs. The adapter copies
this branch's workspace into an isolated artifact build directory and includes
the unchanged snippet there. Production source in the checkout is untouched;
all original crate hashes, staged module hash and snippet hash are recorded.
Cargo uses four jobs and this lane's dependency cache. The selected binary must
list exactly the named test, then execute it with --exact; zero matching tests
is a failure. The original run.py's bare Cargo substring filter alone would not
prove execution on a baseline missing that inclusion. This assertion tests the
injected 901-second deadline, not the full production retry ceiling.

R4-10 uses the same multi-fixture adapter for disabled/enabled compatibility
flags. Both exact JSON controls must pass. Its finding was disputed and the
control is expected to pass on both baseline celld and stock workerd; importing
a finding directory does not automatically make it an expected failure.

R4-02 combines an injected-failure command (celld only) with an HTTP reference
control (both runtimes). The shared adapter runs each applicable part unchanged,
even if the first part fails, and records parts.json plus separate observations.
All applicable parts must pass for the single case to pass. This also records
the positive HTTP control on baseline celld, which run.py would skip after its
first failed assertion. The HTTP transport uses assigned ports throughout.

The R4-05 contract declares an open expected failure. The aggregate retains its
observed mismatch as fail and preserves the declaration in manifest/import
metadata. No broad finding-ID waiver suppresses setup or output failures.
