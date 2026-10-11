#!/usr/bin/env python3
"""Author metadata and immutable input hashes only; no JavaScript/SUT execution."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMPAIGN = HERE.parent
BASE = Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
OLD = Path('/workspace/shared/celld-build/candidate-001/source')
REV = Path('/workspace/shared/celld-body-candidate-002/revisions/r002')
AUDIT = Path('/workspace/shared/celld-body-clone-audit-001')
PROFILE = 'direct-celld-response-clone-chunk-semantics-v1'


def pin(path, root=None):
    data = path.read_bytes()
    return {'path': str(path.relative_to(root)) if root else str(path), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}


def write(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2) + '\n')


def main():
    code = (HERE / 'cases.js').read_text()
    assertions = [line.strip() for line in code.splitlines() if re.search(r't\.(equal|deep)\(', line)]
    assert len(assertions) == 11
    norms = [
        {'url': 'https://fetch.spec.whatwg.org/#concept-body-clone', 'consulted_utc': '2026-10-09', 'snapshot': 'https://fetch.spec.whatwg.org/commit-snapshots/e9460d1b22ead1c6a72eeac37fb2ec0dc01aeb1d/#concept-body-clone'},
        {'url': 'https://streams.spec.whatwg.org/#readablestream-tee', 'consulted_utc': '2026-10-09', 'snapshot': 'https://streams.spec.whatwg.org/commit-snapshots/b9ba9f49d95b4280be0dc2372377a006c3a91c18/#readablestream-tee'},
        {'url': 'https://streams.spec.whatwg.org/#readable-stream-default-tee', 'consulted_utc': '2026-10-09', 'snapshot': 'https://streams.spec.whatwg.org/commit-snapshots/b9ba9f49d95b4280be0dc2372377a006c3a91c18/#readable-stream-default-tee'},
    ]
    case = {
        'id': 'Y301', 'title': 'Keep cloned raw body chunks independent after sibling mutation',
        'mechanism': 'Response body clone requests branch-two chunk storage copying before raw-reader mutation',
        'hypothesis': 'A streaming clone implemented with default tee() can return shared raw Uint8Array storage even when final arrayBuffer consumers each return copied bytes.',
        'trace': ['Enqueue one four-byte Uint8Array into an ordinary default ReadableStream and close.', 'Clone the local Response once and acquire both body readers.', 'Join both first reads and assert exact initial bytes.', 'Mutate the original raw chunk; assert its changed bytes, unchanged sibling bytes and distinct backing buffers.', 'Join both EOF reads, join cleanup cancellation operations and release explicit readers.'],
        'distinctness': 'Y220 observes only final copied arrayBuffers; Y215 observes buffered clone output and metadata. This case observes live raw branch chunks after mutation, proving the tee-true selection has an observable effect. One mechanism only; no parameterized variants.',
        'fixed_runtime_assertions': assertions, 'assertion_count': len(assertions),
        'implementation': {'file': 'cases.js', 'symbol': 'Y301', 'start_line': 2, 'end_line': len(code.splitlines()) - 1},
        'runtime_source_refs': [
            {'path': str(REV / 'source/crates/celld/js/harness.js'), 'line_start': 371, 'line_end': 388},
            {'path': str(OLD / 'crates/celld/js/streams.js'), 'line_start': 105, 'line_end': 179},
            {'path': str(OLD / 'crates/celld/js/streams.js'), 'line_start': 456, 'line_end': 537},
        ],
        'primary_contract_refs': [n['url'] for n in norms],
        'application_relevance': 'Worker code can inspect or transform one cloned local binary response body through raw readers without changing its sibling consumer data.',
        'desired_behavior': 'Initial chunks [10,20,30,40] on both branches; after left[0]=99, left [99,20,30,40], right [10,20,30,40], distinct backing ArrayBuffers, then EOF on both.',
        'chunk_partition_contract': 'A deliberately single default-stream chunk, not a byte stream/host body. Default tee forwards one chunk (or structured clone) to each branch, without arbitrary HTTP coalescing assumptions.',
        'source_observation': 'Candidate001 refuses the valid streaming clone. Candidate002 r002 calls existing tee(true), whose default-stream branch copies branch two with structuredClone. This is source evidence only.',
        'static_prediction': 'NO_FAILURE_PREDICTION', 'prediction_is_runtime_evidence': False,
        'entrypoint': {'method': 'GET', 'path': '/case/Y301', 'request_body': None},
        'layer': 'direct-celld-worker-fetch-global-response-local-default-stream',
        'preconditions': ['Independent case/oracle review and separate exact candidate source/build/deployment review.', 'Real celld Response and ReadableStream globals; no imported/extracted SUT or reference runtime.', 'External five-second request and independent suite/cleanup deadlines plus owned teardown and resource controls are verified before entry.'],
        'schedule': {'kind': 'one finite in-request trace', 'ordinal': 1, 'request': 'GET /case/Y301', 'depends_on': [], 'parallelism': 'two branch reads joined at data and EOF phases; all cleanup cancellations started before their join'},
        'limits': {'requests': 1, 'repetitions': 1, 'incoming_body_bytes': 0, 'source_chunks': 1, 'source_bytes': 4, 'response_clones': 1, 'tracked_streams': 3, 'explicit_readers': 2, 'max_reads_per_reader': 2, 'max_explicit_reader_reads': 4, 'max_cleanup_cancel_operations': 3, 'outer_case_seconds': 5, 'response_bytes': 65536, 'timers': 0, 'outbound_fetches': 0, 'durable_writes': 0},
        'cleanup': 'Join all started reads before cleanup; initiate all reader and unlocked-stream cancels before awaiting; release both acquired readers; require terminal evidence for all tracked streams and both-descendant proof for retained source lock. Pending operation at external deadline => UNKNOWN and incomplete local cleanup. Verified external listener closure, whole proven-owned dev/bundler/runtime descendant-tree emptiness across PGIDs, and owned temporary/log/stage/store removal required for acceptance.',
        'success_cleanup_expectations_for_pinned_source': {'joinedReads': 4, 'joinedCancellations': 2, 'cancelledReaders': 2, 'cancelledUnlockedStreams': 0, 'releasedReaders': 2, 'tracked_streams': 3, 'retained_runtime_source_locks': 1, 'source_terminal_proof': 'both-local-clone-descendants-settled'},
        'authored': True, 'independently_reviewed': False, 'review_status': 'UNREVIEWED', 'status': 'NOT_RUN', 'runtime_status': 'UNRUN', 'actual_runtime_executions': 0, 'runtime_pass_claimed': False,
    }
    write('manifest.json', {'schema_version': 1, 'profile': PROFILE, 'source_snapshot': 'celld-direct-source-v0.6.2-8d27-guard-20261009 + candidate002 r002 overlay', 'authored_case_count': 1, 'reviewed_case_count': 0, 'runtime_executions': 0, 'runtime_status': 'UNRUN', 'qualification': 'One handwritten assertion-bearing candidate, source/static evidence only. Independent review receipt determines census credit. Runtime status stays NOT_RUN until separate observed execution.', 'oracle_policy': 'All expected bytes/statuses are fixed literals; snapshots precede later mutation. Source implementation is never the expected-value oracle.', 'ordinary_input_scope': 'One valid local four-byte default-stream Response. No native HTTP body, RPC, remote handle, capability, scheduler, malformed input or security/lifetime reproduction.', 'contract_sources_consulted_utc': '2026-10-09', 'cases': [case]})
    write('schedule.json', {'schema_version': 1, 'profile': PROFILE, 'runtime_status': 'UNRUN', 'execution_authority': 'SEPARATE_PARENT_RUNTIME_ENVELOPE_REQUIRED', 'suite_outer_deadline_seconds': 300, 'preflight_deadline_seconds': 30, 'startup_deadline_seconds': 120, 'cleanup_deadline_seconds': 20, 'request_count': 1, 'concurrency': 1, 'retries': 0,
        'resource_envelope': {'supervisor_enforced': True, 'enforcement_status': 'REQUIRED_NOT_OBSERVED', 'process_group_field_scope': 'Legacy field names cover the whole proven-owned dev/bundler/runtime descendant tree across PGIDs, including all owned temporary/log/stage/store paths.', 'functional_only_envelope_policy': 'Separate functional-only sampled observations cannot claim strict-profile success.', 'runtime_process_group_memory_max_bytes': 1073741824, 'runtime_process_group_cpu_cores': 1, 'v8_heap_limit_mb': 128, 'request_response_max_bytes': 65536, 'owned_filesystem_max_bytes': 268435456},
        'requests': [{'id': 'Y301', 'method': 'GET', 'path': '/case/Y301', 'body': None, 'outer_deadline_seconds': 5, 'repeat': 1, 'response_max_bytes': 65536}],
        'completion_contract': ['All 11 assertions execute and pass.', 'All four successful-trace reads and both reader cancellations settle; both explicit readers release.', 'All tracked streams have terminal proof; retained source lock has both-descendant proof.', 'Exact reviewed source/build/deploy identity plus external listener closure, whole proven-owned dev/bundler/runtime descendant-tree emptiness across all PGIDs, and owned temporary/log/stage/store removal verified.'],
        'stop_conditions': ['Missing precondition => BLOCKED before entry.', 'Witnessed false assertion or API exception => FAIL, with cleanup recorded separately.', 'Unsettled read/cancel or ambiguous outcome at external deadline => UNKNOWN with incomplete local cleanup; never PASS.', 'Stop the entire proven-owned dev/bundler/runtime descendant tree across PGIDs on deadline/resource breach; verify tree emptiness and owned temporary/log/stage/store cleanup without touching unrelated processes.', 'Exactly one request, no retries or parameter variants.']})
    exts = {'.js', '.mjs', '.json', '.py', '.rs'}
    baseline_files = sorted(p for scope in [BASE / 'celld-os-project/tests', BASE / 'celld-os-stress'] for p in scope.rglob('*') if p.is_file() and p.suffix in exts)
    campaign_files = sorted(p for p in CAMPAIGN.rglob('*') if p.is_file() and p.suffix in exts and HERE not in p.parents)
    collisions = []
    for group, root, files in [('baseline', BASE, baseline_files), ('campaign', CAMPAIGN, campaign_files)]:
        for path in files:
            for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
                if re.search(r'\bY301\b', line): collisions.append({'group': group, 'path': str(path.relative_to(root)), 'line': number})
    assert not collisions, collisions
    scope_inventory = {'baseline': [pin(p, BASE) for p in baseline_files], 'campaign': [pin(p, CAMPAIGN) for p in campaign_files]}
    write('overlap-inventory.json', scope_inventory)
    nearby = [
        {'id': 'Y220', 'shared': 'Response.clone and finite local bytes', 'new_boundary': 'Final arrayBuffer output copies hide raw tee chunk aliasing; Y301 mutates one raw chunk while retaining the other.'},
        {'id': 'Y215', 'shared': 'Clone data mutation independence', 'new_boundary': 'Y215 starts with buffered BodyInit and mutates a final arrayBuffer; no raw streaming chunk alias observation.'},
        {'id': 'Y202', 'shared': 'Distinct ArrayBuffer objects and edited bytes', 'new_boundary': 'Repeated Blob.arrayBuffer copies are a different producer/consumer mechanism; no body-clone tee.'},
        {'id': 'V215', 'shared': 'Consumed clone leaves source available', 'new_boundary': 'Cache consumption checks body state, not live raw-clone chunk mutation.'},
        {'id': 'S017-S018', 'shared': 'Two tee branches and terminal handling', 'new_boundary': 'Remote transport equality/cancellation only; no direct Response.clone raw-chunk mutation. No remote case is rerun.'},
        {'id': 'H008', 'shared': 'Cloning a streaming body', 'new_boundary': 'Request.clone with two host uploads; no local Response raw-chunk copy oracle.'},
        {'id': 'stream-backpressure-semantics / pipe-cleanup-semantics', 'shared': 'Finite stream read/cancel/release primitives', 'new_boundary': 'Pressure, pipe and cancellation schedules contain no Response.clone raw-chunk storage mutation case.'},
    ]
    tokens = []
    for path in baseline_files + [p for p in campaign_files if p.name == 'cases.js']:
        if path.suffix not in {'.js', '.mjs'}: continue
        for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
            if re.search(r'\.clone\(|\.tee\(', line): tokens.append({'path': str(path), 'line': number, 'excerpt': line[:400]})
    write('overlap-audit.json', {'schema_version': 1, 'evidence': 'STATIC_SOURCE_INSPECTION_ONLY', 'baseline_file_count': len(baseline_files), 'campaign_file_count': len(campaign_files), 'inventory': pin(HERE / 'overlap-inventory.json', HERE), 'id_collision_audit': {'proposed_id': 'Y301', 'matches': collisions, 'result': 'NO_COLLISION'}, 'clone_tee_callsite_scan': tokens, 'nearby_case_boundaries': nearby, 'claim': 'Author-assessed distinctness pending independent review. One case only; supporting type/payload/EOF/cleanup subchecks earn no separate design credit.'})
    frozen = []
    for wave in ['body-form-semantics', 'url-semantics', 'headers-semantics']:
        for path in sorted((CAMPAIGN / wave).iterdir()):
            if path.is_file(): frozen.append(pin(path, CAMPAIGN))
    write('source-pins.json', {'schema_version': 1, 'candidate': 'celld-body-candidate-002', 'revision': 'r002', 'binary_sha256': None, 'binary_note': 'No binary built, deployed or run by this author. Full virtual source identity is independently reviewed separately.', 'runtime_sources': [pin(OLD / 'crates/celld/js/harness.js'), pin(OLD / 'crates/celld/js/streams.js'), pin(REV / 'source/crates/celld/js/harness.js')], 'source_and_scope_evidence': [pin(REV / p) for p in ['CANDIDATE-MANIFEST.json', 'VIRTUAL-SOURCE-MANIFEST.json', 'CLONE-SCOPE-CLARIFICATION.json', 'candidate.patch']] + [pin(AUDIT / p) for p in ['AUDIT.md', 'CLARIFICATION-v2-TEE-TRUE.md']] + [pin(BASE / p) for p in ['MANIFEST.json', 'SHA256SUMS']], 'normative_sources': norms, 'frozen_57_wave_artifacts': frozen, 'frozen_artifacts_root': str(CAMPAIGN), 'fixture_artifacts': [pin(HERE / p, HERE) for p in ['cases.js', 'fixture.js', 'wrangler.json', 'manifest.json', 'schedule.json', 'overlap-audit.json', 'overlap-inventory.json', 'README.md', 'author_manifest.py', 'validate_static.py']], 'qualification': 'Static hashes and syntax only. Original 57-case wave files are preserved, not re-authored. Separate review receipt needed before one case may enter tranche007.'})


if __name__ == '__main__':
    main()
