# Shared harness

`common.py`: bounded owned process groups, ports, credential-free child environments,
result writing and cleanup. `result.schema.json`: the only result format.
`native.py` / `cargo.py`: real Rust components and exact crate filters.
`runtime.py`: fresh deployment, fixed listeners and binary/source hashes.
`s3_store.py`: append-only local S3-compatible storage with fault controls.
`conformance.py`: deterministic observations, strict comparison and diff artifacts.
`inventory.py`: reviewed census and applicability; `verify-inventory.py`: hash
and result-coverage checks. `remote.py` / `full-remote.sh`: isolated the fleet host snapshots,
source-matched builds, exclusive port ownership, and collected evidence.

Final runtime launches use explicit `celld deploy` + `celld --listen` with a local
S3 store. They do not use `celld dev`, whose internal listener is hard-coded to
an ephemeral port. Conformance listeners are 9810–9812; fleet is 9800–9807;
store-contract check is 9838; imported regressions receive base port 9840.
