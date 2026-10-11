# Direct celld stress adapters and runners

This export includes 78 actual runner, adapter, validator, support-test and source-pin files. RUNNER-SOURCES.json records their hashes. All executable code is byte-identical; one module docstring has a documented wording-only transformation.

Wave run.py/private_driver.py adapters execute case fixtures through a supplied private origin or guarded owned-fleet setup. Recovery/alarm/deployment driver.py adapters require actual owned Guest objects and verified resource/process/storage evidence; they do not provision the fleet or deploy the initial fixture. http_jobs.py and deploy_job.py are finite helpers. Validation scripts/support tests are source checks, not runtime qualification.

Some exact-pin checks reference historical sources, external supervisors and original manifests. Missing prerequisites must reject execution, never become unconditional success. For a portable run, supply a reviewed bounded adapter, matching source/binary/profile manifest and owned cleanup. Do not fabricate evidence.

Fifteen operational native qualification files were omitted because they depend on unavailable execution-control records and toolchain installations. Their file identities and reasons are listed in RUNNER-SOURCES.json. All native assertion sources remain included. The archive build guide describes native compilation, and the separately labeled portable lease-continuity runner retains its bounds and original assertions. That transformed runner has not been re-executed.

No actual process reports, release requests, credentials, raw logs, stores, images, binaries or toolchains are included. Literal test-only access/secret strings in simulated-store adapters are public dummy fixture constants, not account credentials. URL password/user fields occur in rejection checks. Never substitute production credentials.

Run supported cases in isolated finite shards, and record PASS/FAIL/BLOCKED/UNKNOWN separately. A source-only export is not a complete VM provisioning bundle.
