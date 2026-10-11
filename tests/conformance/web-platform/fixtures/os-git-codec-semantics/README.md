# Actual OS Git codec, valid-input wave

Six proposed primary cases X201–X206. All are NOT_RUN, independently unreviewed as authored, with zero runtime executions/passes. These are actual imported Cloudflare OS component fixtures, not a full OS execution or a distributed, authorization, security, performance or durability claim.

The immutable production source and Apache-2.0 LICENSE are copied byte-for-byte under vendor/cloudflare-os from official commit 4358072f8cb1bc9ddfb6ee11122e194c76cd71e0. Production module SHA-256: 56814f3f0608c88e6e83ba08e43f5af87ed4fabf972554e696c390809e9e1538. No source rewriting, copied codec implementation or runtime substitution is used.

- X201: canonical loose-object header/OID plus native zlib encoding/decoding
- X202: canonical tree byte ordering and all five valid modes
- X203: canonical commit metadata and ordinary continued custom headers
- X204: valid copy/insert delta with legal 64KiB copy sentinel
- X205: full four-type pack encoder checks and independent golden decoding
- X206: full valid OFS→REF base-resolution chain

The finite fixture is an ordinary fetch handler, with no DO, RPC, gatekeeper, storage service, external network fixture, stateless capability, scheduler, or retained cross-request object. Exactly one case is accepted per fresh owned deployment/process. This does not resume any paused setup or test path.

## Dependency and future-run contract

All cases import the whole production module. Its unconditional runtime imports are node:zlib and pako. Exact historical pnpm-lock.yaml identifies the workshop-backend direct pako dependency as 3.0.2, with the exact integrity string in dependency-lock.json; isomorphic-git's transitive pako 1.0.11 must not be substituted. The package.json is a declaration, not evidence of an installed or verified package. The two production `import type` statements must be erased by a separately authorized trusted TypeScript bundler; no workspace package or worktree-binding runtime adapter is needed. Preserve the original source bytes and using/Symbol.dispose behavior during bundling.

Static native-module check: modules.rs maps node:zlib, and harness.js exposes genuine native-backed deflateSync/inflateSync. The pinned harness lacks constants.Z_BEST_SPEED and ignores sync compression options. These valid-byte tests therefore cannot certify the OS caller’s requested compression level or performance; no shim or source fix is supplied.

Future execution requires a separately authorized direct celld build and owned supervisor, nodejs_compat, genuine node:zlib, the exact integrity-verified pako dependency graph, crypto.subtle, crypto.DigestStream, byte/BYOB streams, TextEncoder/Decoder, String.isWellFormed and Symbol.dispose. Dependency acquisition, installation, bundling, production evaluation, celld launch and runtime tests were not performed or authorized here. Missing prerequisites leave the cases UNRUN/setup-blocked, never passed and never replaced with another codec.

## Schedule and cleanup

Use the exact GET /case/X20n route once in each fresh process; no request body, no external service, and no generated user data. Manifest and schedule bound each payload, source/read count, logical operation, assertion, response, process/RSS/writable-domain and wall clock. The decoded/logical-byte estimate is not a JS-heap or native-allocation claim: strings, temporaries, pako/native state and allocator overhead are bounded only by the mandatory 512 MiB owned-domain RSS ceiling. The five-second in-fixture timer cannot preempt synchronous work; the external fifteen-second process deadline is mandatory.

Pack sources are bounded native byte streams. On normal completion each source closes once and the decoder reaches verified EOF. A finally block always calls generator.return(), invoking the production using/dispose cancellation on early exit. The production PackReader owns private BYOB-reader and digest resources and does not expose lock release; this fixture does not modify that implementation or claim cancellation proves reclamation. All outcomes require the supervisor to terminate and reap the entire proven-owned runtime/dev/bundler descendant domain, including descendants in other process groups, then remove only that domain's staging, temporary, log, bundle and private-store files. A timeout or cleanup refusal cannot earn a PASS. No teardown may race an unsettled trace except this externally supervised owned-process termination.

## Static verification

`python3 validate_static.py` reads hashes/source/JSON, checks manual vectors with Python standard-library operations, and invokes Node --check only for authored wrapper/data JS. It never imports/evaluates source JS/TS or runs a SUT. The independent format reasoning is in ORACLES.md; exact baseline/supporting source hashes and closest-case decisions are in overlap-audit.json/source-pins.json.

No accepted prior tranche, source inventory, source file or baseline was modified. Reviewer acceptance belongs in a separate receipt; author counters stay unreviewed until a separately authored acceptance record supplies credit.
