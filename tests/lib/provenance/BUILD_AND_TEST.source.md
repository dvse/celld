# Build and test guide

## 1. Verify before building

From this archive's root:

```sh
sha256sum -c SHA256SUMS
python3 tools/verify-source.py
```

This verifies the exported direct source against the cut manifest. It launches no
runtime. `MANIFEST.json` describes every included file and its export hash.

To reconstruct independently, check out upstream commit
`90b43017241f81189453d326d05948f388b34652` from
https://github.com/denoland/celld and apply `patches/01-*.patch` through
`patches/04-*.patch` in order using `patch -p1` in that checkout. Then use:

```sh
python3 tools/verify-source.py /absolute/path/to/reconstructed/celld
```

The packaging pass performed that reconstruction against the locally verified
upstream baseline and matched every exported source byte.

## 2. Full runtime build: external prerequisites

The source pins Rust 1.98.1 in its Dockerfile. Supply an appropriate Linux Rust
toolchain, Cargo, native compiler/linker/build utilities and the dependency
downloads required by Cargo.lock (including the V8-related dependencies). Network
access and a substantial build disk/memory budget are external prerequisites.
No Cargo registry, V8 artifact, toolchain or compiled output is in this archive.
The upstream Dockerfile is also included; its test stage needs sqlite3 and Clippy.

With those prerequisites installed, an intended local build is:

```sh
cd celld-os-project/celld
CARGO_INCREMENTAL=0 CARGO_BUILD_JOBS=2 CARGO_PROFILE_DEV_DEBUG=0 cargo build --locked -p celld
```

The historical wrapper `celld-os-project/scripts/cargo.sh` instead assumes
toolchains at `celld-os-project/.toolchains/install` and a Cargo cache at
`celld-os-project/.toolchains/cargo`. Both locations are absent. Use your installed
toolchain directly or deliberately recreate that layout.

Historical default workspace test/Clippy/formatting passes concern 8d27 before
the guard. Full build, default tests, Clippy and formatting have **not** been rerun
for the final guarded archive. Intended commands after provisioning are:

```sh
cargo test --locked
cargo clippy --all-targets --locked -- -D warnings
cargo fmt --check
```

These commands are not a claim that optional/internal test configurations or the
handcrafted runtime corpus have executed. Custom CELLD_CONFORMANCE_* and
CELLD_INTERNAL_* cfgs can reference private include files absent from the source
snapshot and are outside default test scope; do not enable them for a standalone
archive build. Normal build version metadata comes from Cargo.toml; no .git
directory is required. Docker version/revision labels default to unknown unless
explicitly supplied.

## 3. Direct local-process regression suite

The `celld-os-project/tests` directory contains actual fixtures, assertions and
orchestration for distributed RPC, ordering, disposal, retained callbacks,
duplicate DO names, foreign classes, streams and controlled recovery. Read its
README and ACCEPTANCE contract for exact scope.

Supply a rebuilt celld, Python 3.11+ (3.12 used by the source workflow), Node.js
with the APIs used by the fixtures/clients, and esbuild on PATH. The local adapter
also probes the historical `os/node_modules/.pnpm` location, which is absent;
putting the required esbuild binary on PATH avoids that optional lookup. No OS
checkout or node_modules is bundled. Linux `/proc`, loopback networking and
owned child-process cleanup are required. The adapter writes fresh disposable
stores beneath `tests/runs`; use only isolated local test data.

Example intended functional profile, from `celld-os-project`:

```sh
export ACCEPTANCE_CELLD="$PWD/celld/target/debug/celld"
export ACCEPTANCE_DURABILITY=bucket
python3 tests/run_distributed.py --functional-only --adapter 'python3 tests/local_adapter.py' --report tests/distributed-report.json
```

Missing full-OS or fault-injection prerequisites correctly produce BLOCKED or
NOT_RUN. A profile pass is not the full distributed acceptance gate. Authentication,
forgery, malformed-wire and restricted stateless-lifetime diagnostics remain
NOT_RUN in this delivery. Do not infer they ran from their source being present.
Standalone `run_reply_loss.py` has a `--reliability-only` profile; its default
also includes authentication probes and is not the intended limited profile.

Interop fixture sources are included but their generated bundle is not. The
preserved builder/client require Cap'n Web 0.12.0 and esbuild under the historical
`celld-os-project/os/node_modules/.pnpm` layout; provisioning those dependencies
or a separately hashed path-adapted build/client is necessary. No OS dependency
lockfile/node_modules is included, so that historical entry point is not turnkey.

The retiring-capability regression uses `--expect callback-success` with a
candidate binary; its historical result predates this guarded source cut.
The `returned-capability` fixture is retained as source for an unresolved route,
not a passing lifetime result.

## 4. Nineteen lease-continuity component tests

`tests/lease-continuity/lease_continuity.rs` preserves all original 15 test bodies;
`guard_predicate.rs` adds four. Their source-pin manifest lists exact filters.
They exercise the real celld-logic State and require no network/runtime process.
The portable `run_offline.py` export preserves the original limits, exact test
filters, pin checks and owned cleanup. It resolves the archive source path and
RUSTC, removes unavailable scheduling metadata and the unused frozen-binary
presence check, and has **not** been re-executed. Original/export hashes are in
`manifests/export-transformations.json`. After verifying the archive, use
`python3 celld-os-project/tests/lease-continuity/run_offline.py --run-label YOUR_FRESH_LABEL --expected-pins-sha256 HASH`,
where HASH is the SHA256 of that directory's `source-pins.json`, and set RUSTC to
your compiler if needed. Provision an isolated resource envelope first.

The following explicit commands also illustrate a fresh local build. They were
**not executed against the archive** and are not a replacement for the historical
bounded-run evidence.

Run in an isolated build directory with a reviewed memory/CPU/wall-time envelope.
Historical limits were 1 GiB address space, serial compilation, 90-second total
build wall time, 60 CPU seconds per compiler, 10 seconds/10 CPU seconds per exact
test, and 270 seconds overall, with owned process-group cleanup. A linker
supporting `--threads=1` was used. Do not remove safety bounds merely to obtain a
pass.

```sh
# From the archive root; choose a fresh disposable directory yourself.
ROOT="$PWD"
BUILD="$(mktemp -d)"
cat "$ROOT/celld-os-project/tests/lease-continuity/lease_continuity.rs" > "$BUILD/suite.rs"
printf '\n' >> "$BUILD/suite.rs"
cat "$ROOT/celld-os-project/tests/lease-continuity/guard_predicate.rs" >> "$BUILD/suite.rs"
rustc --crate-name celld_logic --crate-type rlib --edition=2021 -C debuginfo=0 -C codegen-units=1 "$ROOT/celld-os-project/celld/crates/logic/lib.rs" -o "$BUILD/libcelld_logic.rlib"
rustc --test --edition=2021 -C debuginfo=0 -C codegen-units=1 -C link-arg=-Wl,--threads=1 "$BUILD/suite.rs" --extern "celld_logic=$BUILD/libcelld_logic.rlib" -o "$BUILD/lease_tests"
"$BUILD/lease_tests" --list
# Execute each exact filter listed in source-pins.json under the stated limits:
# "$BUILD/lease_tests" FILTER --exact --test-threads=1 --nocapture
```

The 19-test historical pass is native-component evidence. Do not add these 19
tests to the handcrafted census or claim a guarded full-runtime pass.

## 5. Handcrafted corpus and native suites

`celld-os-stress/SOURCE-FILES.json` inventories preserved case bodies;
`RUNNER-SOURCES.json` inventories actual runners, preflight helpers and adapters.
Read `celld-os-stress/README.md` and `RUNNERS.md`. The target count is 461 reviewed
assertion-bearing candidates, not all 575 designs. Repeated runs, copied base
fixtures and characterizations earn no additional distinct case credit.

### Selecting the reviewed R027 replacement

The preserved `fixture/index.js` imports `./rpc.js`, so the unmodified base fixture
still selects historical R027. The accepted current R027 body is in
`revisions/r027-v2/rpc.js`; it replaces one case and adds no authored credit.
Prepare a fresh deployment copy without editing either preserved source:

```sh
# From celld-os-stress; choose a fresh disposable deployment directory.
DEST="$(mktemp -d)"
cp -R fixture "$DEST/fixture"
cp revisions/r027-v2/rpc.js "$DEST/fixture/rpc.js"
sha256sum "$DEST/fixture/rpc.js"
# Pass this fresh fixture directory to the reviewed deployment adapter.
```

The old fixture rpc.js SHA256 is `8e478959461178f2dd1b83040177232581f7f1543f51d83fa4fe585ab4fb22b5`.
The selected replacement SHA256 must be `9072e9b02913a4e0b73721eaecc7f4fa62529638e358d186c0c38c6c9674e425`.
Record this replacement hash and the complete deployed fixture manifest for the
new run. Do not reuse old base-fixture receipts or call the new deployment a
byte-identical replay. This selection workflow is documented, not executed by
packaging; its required topology and assertions remain unchanged.

Five native Cargo manifests retain their original absolute dependency path:
`/workspace/shared/celld-os-project/celld/crates/logic`. The families are output
gate, routing/acquisition, pressure/recovery, log recovery and wake/recovery.
To run elsewhere, prepare a separate local build manifest that points to this
archive's `celld-os-project/celld/crates/logic` and the original test source;
record the new manifest hash. Do not silently alter the shipped manifest or
claim its original hash for a relocated copy. The wake suite has not executed.
Historical pins can refer to unguarded logic; a mismatch against this guarded
cut is expected and must be explicitly reviewed before a new run.

Wave `run.py`/`private_driver.py` and recovery/deployment/alarm `driver.py` files
contain real assertion orchestration. Some expect an already provisioned private
origin or Guest/Driver interface, exact resource/process/placement witnesses,
reviewed pins, deployment helper and simulated object-store configuration.
They do not constitute a VM provisioning bundle. Missing prerequisites should
remain a typed BLOCKED result. Public literal `test-only` values in isolated
simulated-store code are dummy fixture constants, never production credentials.

## 6. VM sources and missing operational inputs

The historical direct recovery sources under
`tests/emulated-network/publishable/source` use two independent guests and require
external QEMU binaries/libraries, guest kernel/initramfs, readonly stage content,
celld/workerd, an isolated object store, Python guest runtime, fresh deployments,
cgroup configuration and a matching VM supervisor. Their original launch paths
expect `stage`, `images`, `qemu` and `logs` beside the testbed runner. They are
absent. The hook's `full.py` and `delegation.py` references correspond to the
published `broad-run.py` and `corrected-delegation.py`; prepare explicit wrapper
aliases in a new run directory and record that adaptation. The publication hook
already removed two synthetic credential assignments; original and published
hashes are recorded separately.

No VM images/stages, opaque deployment objects, actual databases, session keys,
raw logs, private execution-control requests or internal reports are shipped.
They cannot be reconstructed simply by treating a source hash as an executable.
Exact historical binary hashes identify evidence and are not promises of a
byte-identical build with another toolchain/path. The complete VM/full-OS stress
suite is therefore not one-command runnable from this ZIP.

`manifests/nonportable-references.json` lists the remaining absolute filesystem
references found in packaged source/config/docs. Generic runtime paths such as
`/proc` and `/tmp` are part of the expected Linux/guest environment.
