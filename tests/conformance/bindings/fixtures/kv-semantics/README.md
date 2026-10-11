# Newly authored ordinary KV binding cases

K201–K220 are 20 new source-contract candidates for direct celld. They are not
recovered copies of any previously mentioned 24 KV cases, are not counted as
review-accepted here, and have never been run by this authoring task. The restored
K001–K024 IDs actually identify the native wake-recovery-logic family.

## Artifacts

- `worker.js`: one dependency-free Workers module with 20 actual case bodies,
  concrete assertions, bounded operation counters and per-case owned-key cleanup.
- `wrangler.jsonc`: minimal deployment with two distinct public KV bindings.
- `manifest.json`: case intent, application relevance, source references, exact
  finite trace, oracles, distinctness, limits, cleanup and source slice hashes.
- `source-pins.json`: SHA256 pins for the immutable direct source and corpus inputs.
- `overlap-audit.json`: available-corpus audit and its limits.
- `validate_static.py` / `static-validation.json`: syntax and metadata integrity
  checks only. Neither imports/evaluates a case nor runs a KV implementation.
- `SHA256SUMS`: hashes of all delivered files except itself.

## Target and oracle qualification

Use only the restored direct-celld source selected by `source-pins.json`. Source
`kv.js` lines 8–13 says it implements strong reads while deliberately publishing
weaker freshness promises. Consequently every immediate post-write/delete oracle
here is labeled PINNED_DIRECT_CELLD_SOURCE_CONTRACT. This suite is neither a
universal Cloudflare consistency contract nor permission to strengthen celld's
published future compatibility guarantee. No workerd execution, Node KV mock,
extracted cell implementation, or synthetic Map store counts as a runtime pass.

The bindings route through the production bootstrap and `__makeKvNamespace` into
the runtime KV cell. No internal operator endpoint, direct SQL, private hook,
custom test limit or guarded G/N/P/J122 route is used. All values are at most 256
bytes, all metadata JSON at most 256 bytes, and keys at most 128 UTF-8 bytes. No
large-value bucket path, malformed input, authentication test, forced fault,
restart, retained RPC capability, or inter-request stream handle is involved.
K206's two streams live and are consumed within the same active fetch request.

## Required future execution envelope

Authoring did not launch or build anything. A separately reviewed adapter must:

1. Start from a fresh isolated disposable store with no user/application data.
   These configuration IDs are fixture IDs, not production namespace names. Run
   serially with no other writer or concurrent case request. K210 deliberately
   owns three literal names (`__proto__`, `constructor`, `toString`) in KV_A.
2. Record the actual celld executable hash, source selection, deployment/config
   hashes, owned PIDs/process-group IDs, argv, state directory and origin. Verify
   the engine is direct celld; fixture response text cannot prove its provenance.
   Missing target/deployment/resource witnesses are BLOCKED, never PASS.
3. Invoke exactly one GET `/case/K201` through `/case/K220` per case. There is no
   all-cases route, no automatic retry and no pagination-until-success loop.
   `worker.js` checks a hard 64 public binding calls per setup/case/cleanup phase;
   actual successful case traces need 2–12 main-phase calls. K220 alone overlaps
   up to four public calls, in three explicit joined groups.
4. Enforce a strict 30-second total wall deadline per request including cleanup,
   a 700-second wave deadline, 300 CPU seconds for the owned wave process group,
   a 2 GiB aggregate owned-process RSS ceiling, and 256 MiB disposable-state
   disk ceiling. Capture at most 1 MiB of response per case. Provision/enforce
   these limits before running; unsupported limit enforcement is BLOCKED. These
   are safety limits, not performance acceptance targets.
5. Treat HTTP 200 plus matching id, PASS, nonzero expected assertion count and
   cleanup.verified=true as necessary, not sufficient: all provenance and limit
   evidence is also required. A binding/case exception, non-PASS, truncated or
   invalid body is failure; missing prerequisites are BLOCKED. A stall reaching
   the outer deadline is TIMEOUT with cleanup unverified, never a pass or a
   successful empty result. There is deliberately no Promise.race timeout in the
   Worker that would leave a write running while cleanup races it.
6. On a completed request, fixture finally cleanup deletes exact owned keys and
   verifies null reads. On a stall, stop only the adapter-owned invocation and,
   where the request cannot be separately cancelled, its owned celld process
   group. Preserve failure evidence, then discard only its disposable store.
   Do not kill unrelated processes or operate on a shared store.
7. At wave end, stop the owned celld group and discard the disposable store even
   after all logical cleanup checks succeed. K219's temporary put arms an alarm;
   this source's nonexpiring replacement and deletion do not disarm it. Null
   reads prove logical row cleanup only, not absence of scheduled work. A fresh
   store is mandatory for the next independent run.

K219 computes one expiration 3600 seconds ahead solely to check reported units
and clearing on replacement; it never waits for or claims an expiration event.
If the outer deadline is exceeded or the clock jumps unexpectedly, do not retry
within the same case or reinterpret the result as success.

## Syntax-only verification

`python3 validate_static.py` checks Node module syntax, manifests, exact case
IDs, fixture slices and immutable source pins. It does not start a SUT, install
packages, compile celld, execute a Worker case, or award runtime credit.
