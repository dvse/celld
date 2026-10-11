# Direct celld handcrafted test sources

This source-only corpus contains 575 individually specified designs: 461 reviewed assertion-bearing candidates and 114 separately classified characterizations. Characterizations contribute zero toward the 2,000-case completion target. The target is unfinished.

Runtime evidence covers 19 confirmed executions across 11 IDs: 14 pass executions and 5 failures, plus 24 blocked attempts and one unknown attempted outcome. The repeated H001 failures remain failures. Separately, 122 native-component traces ran: 112 invariant passes and 10 observations. These are not equivalent to 122 network/runtime tests. See COUNTS.json.

All files in SOURCE-FILES.json preserve their original bytes and hashes. Base R027 has a reviewed replacement at revisions/r027-v2/rpc.js; it is one revised case, not added case credit. The original base fixture is retained to preserve historical source identity. DO visibility supplements contain copied base fixtures; copied case bodies do not add distinct tests.

## Build and execution prerequisites

JavaScript fixtures require direct celld with the supplied worker configuration, the relevant APIs, and a trusted bundler. Native Rust tests require the exact compatible celld-logic source and Cargo dependencies. Cargo source paths and fixture imports are preserved as authored and may require relocation in a separately reviewed build adapter.

This is a test-source export, not a turnkey VM launcher. Generic assertion adapters and runners are included; see RUNNERS.md. Guest provisioning supervisors, private execution-control records, credential provisioning, runtime binaries, toolchains, images, stores and raw logs are excluded. Some Python case functions expect a Driver supplied by an external fleet supervisor; they must not be treated as executable standalone. Manifests describe exact preconditions, finite schedules, assertions and cleanup. Referenced operational evidence paths are historical provenance, not included runtime inputs.

Before running, supply an independently reviewed bounded adapter with actual process/resource/placement witnesses, owned cleanup, fresh fixture identities and an isolated private test store. Unsupported prerequisites must be BLOCKED, never reported as passes. Current candidate attribution is 8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f where explicitly selected; original baseline is 62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e. Source-only patches do not change those historical binary identities.

Most authored runtime families remain unexecuted. This corpus does not establish production performance, hostile-tenant containment, full OS workflow acceptance, or general restart/fleet durability. Alarm/event A001–A028 are reviewed source designs and have not run. Valid active-request fixtures do not authorize excluded authentication, malformed-wire or retained stateless-capability lifetime probes.
