# Direct celld URL semantics candidates

20 handwritten, assertion-bearing ordinary API cases, U201–U220. Entry points are
GET /case/U201 through GET /case/U220 on the deployed Worker. No other endpoint
executes a case. The fixture imports only the sibling handwritten case bodies and
uses celld's installed globals without shims or implementation-source extraction.

## Evidence and classification

- Authored cases: 20. Runtime executions: 0. Runtime status: UNRUN / NOT_RUN.
- Independent review was pending at author delivery; this directory does not
  award reviewed census credit. An external review receipt can supersede that
  review status without turning static evidence into runtime evidence.
- Static checks cover syntax, metadata consistency, and exact file identity.
  Node is used only with --check. No fixture, reference runtime, celld process,
  build, dependency installer, or networked test was run during authoring.
- U202–U205, U207, U208, U214, and U215 are explicitly classified as
  EXPECTED_FAILURE_CANDIDATE from source inspection. Their desired API contracts
  remain the pass oracle. These predictions are not observed failures.
- Restored source is the immutable v0.6.2 + extensions + 12-line lease guard cut.
  Historical unguarded binary 8d27 results are not evidence for these cases or
  for a rebuilt guarded runtime. No binary identity is supplied here.

The manifest separates desired behavior, fixed runtime assertions, and observed
source structure. The assertions use literal oracles, never output obtained by
running the implementation under test. Each design has a mechanism, application
purpose, finite trace, exact assertion count, source locations, primary contract
references, distinctness rationale, limits, and cleanup.

## Direct-celld deployment and invocation contract

The following is a future-run contract, not an executed launcher. A reviewed
external supervisor must already provide an independently identified direct
celld binary built from the complete pinned source, an installed trusted esbuild,
isolated disposable local storage, and the limits in schedule.json. If any are
missing, record BLOCKED before case entry. Do not substitute Node, a mock,
workerd, an OS wrapper, or copied polyfill code for direct celld.

1. Verify source-pins.json and SHA256SUMS. Review all cases before promoting them.
2. Create a fresh owned deployment directory; copy only fixture.js, cases.js,
   and wrangler.json into it. No .env, .env.local, .dev.vars, shared bindings,
   production credentials, external bucket, or previous .celld data is needed.
3. Record source cut, full source-manifest digest, exact binary digest/build
   receipt, bundler digest, deployed file digests, and config digest. Record real
   supervisor/child PIDs, owned cgroup or equivalent memory/CPU envelope, the
   fresh store path, and the actual loopback Worker listener.
4. Under that supervisor, the source-documented CLI is:

   CELLD dev RUN_DIR/wrangler.json --host 127.0.0.1 --port PORT --no-watch

   CELLD is the reviewed absolute binary path; RUN_DIR and PORT are the fresh
   supervisor-owned directory and reserved loopback port. The pinned dev.rs and
   docs/README.md establish that dev performs real deployment and runs a celld
   node with a local store. Do not run in the immutable source or this authored
   directory. No --clean is needed for a fresh directory.
5. Wait for the actual deployment/listener witness within the 120-second startup
   deadline. Do not use a case as a readiness probe. Start one ordinary GET per
   case, serially, in the exact schedule order. No query, body, auth header,
   retries, parallelism, or alternate route is part of these traces.
6. Each request has an independently enforced five-second outer deadline and
   64-KiB response cap. For illustration, a provisioned HTTP client would request
   http://127.0.0.1:PORT/case/U201 with --max-time 5 and save the complete response.
   This illustration does not replace the response cap or owned-process bounds.
   A Worker cannot interrupt a stuck synchronous API with an in-isolate timer;
   the outer deadline is mandatory.
7. A runtime PASS requires HTTP 200, matching profile/id, traceEntered true,
   exactly the manifest's assertion count, every assertion passed, null error,
   and COMPLETE cleanup, plus the external runtime/deployment witnesses.
   HTTP 500 with an assertion or unexpected exception is FAIL. A known started
   case that misses its deadline is a timeout failure when externally witnessed;
   missing execution/outcome evidence is UNKNOWN. A missing prerequisite or
   unverifiable runtime before entry is BLOCKED. No status may be promoted from
   syntax checks or from an unverified server response.
8. After receipts are captured, terminate only the supervisor-owned process group
   and verify all owned children exit within the 20-second cleanup phase. Remove
   only that fresh deployment/store directory. Preserve bounded receipts and
   provenance without copying the runtime store. Incomplete cleanup is reported
   explicitly and prevents suite acceptance.

Overall supervisor deadline: 300 seconds, including at most 30 seconds preflight,
120 seconds startup, 100 seconds for twenty five-second requests, and 20 seconds
cleanup. Runtime cgroup limit: 1 GiB memory, one CPU; isolate heap: 128 MiB.
If the reviewed runtime cannot operate within these limits, record BLOCKED and
seek an explicitly reviewed profile revision rather than silently increasing
resources. No run, build, or download is authorized by these instructions alone.

## Scope and distinctness

- U201–U208: base-relative parsing, path encoding, IDNA host replacement, IPv6
  authority parsing, numeric port conversion, href/query-view rebinding,
  empty-present delimiters, and opaque blob URL serialization.
- U209–U216: form decoding, form encoding, duplicate coalescing, selective removal,
  stable UTF-16 sorting, live iterator state, detached iterator arrays, and
  iterable constructor snapshots.
- U217–U220: URLPattern relative/base canonicalization, optional capture/result
  shape, ignoreCase propagation, and custom regexp/component conjunction.

The paired inputs inside one design are controls and transitions within one
case. They do not receive separate case credit. URLs are inert ordinary data:
there is no DNS, fetch, Blob URL allocation, durable object, capability retention,
fault injection, malformed input, authentication, forgery, or replay operation.
Valid nonmatching URLs exercise ordinary URLPattern boolean/null outcomes.
No old G/N/P/J122 guarded paths are used.

overlap-audit.json records the baseline corpus scope, source inventories and
literal API-name search. Existing URL uses in dispatch, redirect-client helpers,
and WebSocket query routing are incidental; they do not assert these mechanisms.
The restored examples/webapi Worker exposes a basic URL read but has no competing
assertion-bearing semantic cases. We make no novelty claim about unpublished
upstream WPT or private conformance suites absent from this archive.

## Static validation only

Run from this directory:

    python3 validate_static.py --source-root /absolute/path/to/restored-cut

It parses Python/JSON, checks pin hashes, source locations, IDs, entry routes,
assertion counts and copied assertion declarations, and invokes node --check on
the two JS files. It never imports or executes the fixture. Its report is labeled
STATIC_ONLY with runtime_status UNRUN. author_manifest.py only regenerates
metadata around the handwritten bodies; it is not a test-case generator.

Primary API contracts: [URL Standard](https://url.spec.whatwg.org/),
[URLPattern Standard](https://urlpattern.spec.whatwg.org/), and
[Web IDL pair iteration](https://webidl.spec.whatwg.org/#es-iterable-iterator-prototype-object).
U214 follows Web IDL's list recheck after an earlier done result; a completed
JavaScript generator is deliberately not used as its behavioral oracle.
