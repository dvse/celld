# New ordinary direct celld R2 workflows

I201–I220 are twenty individually authored executable candidates, all NOT_RUN and
pending independent review. No runtime launch, dependency download, build, hosted
bucket access or credential transmission has occurred. Node is syntax-only.

The cases use valid tiny synthetic objects through actual env R2 bindings. They
cover record/body conversion, metadata replacement, independent-reader cleanup,
conditions, ranges, pagination/directory grouping, selective metadata, bucket
isolation, deletion, path encoding, correct checksums, and multipart lifecycle.
Every successful multipart uses one small final part. No minimum nonfinal-part
requirement is bypassed. Same-node resumption remains inside one active Worker
request and uses its own public upload ID, never a retained RPC capability.

## Coverage and oracle boundaries

The restored handcrafted corpus has no R2 public binding wave. Its source example
only demonstrates simple object proxy GET/PUT/DELETE. This wave tests distinct
R2 host/native-storage mechanisms rather than copying KV/D1/DO storage behavior.
The manifests distinguish shared primitives from those independent paths. Each
body and expected-value list is handwritten; metadata generation does not create
new case bodies or expand parameter combinations.

The pinned source's docs/services/r2.md and implementation paths support the
intended behavior. The [Workers API reference](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/)
was consulted on 2026-10-09 for public conditions, ranges and result shapes.
Cases respect documented celld differences: no unique version-per-write claim,
no Cloudflare UTF-8 list-order claim for encoded keys, and no cross-node or restart
multipart resumption. I212 compares child prefixes as a sorted set. I213 explicitly
uses celld's documented source shaping of unrequested metadata as empty maps.
Opaque etags/cursors are captured at their normal API boundary; comparisons test
protocol relationships, not guessed backend-specific strings. Fixed data values,
key suffixes, byte windows and checksum digests are independently authored.

## Deferred deployment contract

R2 operations require an actual fleet bucket, documented by this source. Missing
fleet-bucket support, bindings or object-store features must produce BLOCKED. Do
not replace the bucket with an in-memory fake to make these cases run. This source
package does not provision infrastructure or authorize use of a user's bucket.

A separately authorized reviewed supervisor must:

1. Copy this wave to fresh staging and deploy wrangler.jsonc with exact rebuilt
   direct celld, using a trusted bundler only if needed by that deployment route.
   Read the recovered BUILD_AND_TEST.md and exact binary CLI help. Never use
   workerd, hybrid or a Node API emulation as the SUT.
2. Supply a fresh disposable private fleet-bucket store with two distinct R2
   bucket bindings, no real user objects, loopback-only ingress, and recorded
   executable SHA256/build source/boot/PID/fixture/config identities. No public
   URLs, presigned tokens or access keys appear in these fixtures.
3. Bound concurrency to one case request, process RSS to 1 GiB, logical fixture
   payload per case to 4 KiB, at most eight keys per binding, one upload and one
   part, 80 tracked API calls, 15-second HTTP deadline, 20-second owned-process
   deadline and 450-second whole-wave deadline. Apply a private store quota of
   256 MiB. A missing/unsuitable enforced envelope is BLOCKED for review, never
   silently removed. Runtime/replication bookkeeping may exceed logical bytes.
4. GET /manifest and then each exact GET /case/I201 etc once. A case chooses a
   fresh random prefix and verifies it empty in both buckets. The supervisor
   must witness the actual owned store and runtime; fixture labels alone do not
   prove identity. All bucket IO stays in that private store.
5. Require ASSERTIONS_SATISFIED, traceSettled true, nonempty all-true assertions
   and cleanup COMPLETE, then independently verify process/store teardown.
   A 200 response is only an observation. This fixture never emits runtime PASS.
   Missing APIs, errors, unsettled traces and cleanup failures remain distinct
   FAIL/BLOCKED evidence, and no source/static observation is execution credit.

The fixture races precondition/trace/cleanup against 2/8/3-second timers. Those do
not interrupt wedged native code, so the outer process deadline is mandatory.
Cleanup never races an unsettled trace. After a settled trace it cancels unfinished
unlocked readers, checks finite input closure, aborts uncompleted owned uploads,
deletes registered synthetic keys and verifies both prefixes empty. A native
reader that finished through EOF may retain its runtime-owned lock; no released-
lock or leak-absence claim is made. A still-locked unfinished reader requires
external teardown. The supervisor reaps only owned processes and the entire
fresh private store, including any incomplete-operation residue.

No authentication, replay/forgery, malformed-input, forced process failure,
restricted guarded-core, quota exhaustion, performance, cross-process durability,
provider billing or full-OS claim is part of this source-authoring wave.

## Static checks

`python3 validate_static.py` verifies source hashes, manifest/function identity,
fixed assertion presence and JavaScript syntax without executing case bodies.
Source-root paths are preserved; moving the source requires reviewed relocation,
not regenerating frozen accepted files. Independent review receipts will supply
acceptance without rewriting author status fields.
