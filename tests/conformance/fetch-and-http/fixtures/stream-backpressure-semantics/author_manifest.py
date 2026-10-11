#!/usr/bin/env python3
"""Emit metadata around six handwritten traces; never import or execute JavaScript."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
AUDIT = 'assessments/stream-backpressure-gaps-20261009.json'
PROFILE = 'direct-celld-stream-backpressure-semantics-v1'
SNAPSHOT = 'https://streams.spec.whatwg.org/commit-snapshots/b9ba9f49d95b4280be0dc2372377a006c3a91c18/'
STREAM = 'celld-os-project/celld/crates/celld/js/streams.js'
WRITE = 'celld-os-project/celld/crates/celld/js/writable_stream.js'
HARNESS = 'celld-os-project/celld/crates/celld/js/harness.js'
DEV = 'celld-os-project/celld/crates/celld/dev.rs'
DEPLOY = 'celld-os-project/celld/crates/celld/deploy.rs'
OS_RAW = 'os-source-inventory/historical-4358072/raw/packages/workshop-backend/src/blueprint-archive.ts'


def emit(name, data):
    (HERE / name).write_text(json.dumps(data, indent=2) + '\n')


def pin(root, path):
    raw = (root / path).read_bytes()
    return {'path': path, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def ranges(refs):
    output = []
    for ref in refs:
        for pair in ref['lines'].split(','):
            endpoints = pair.split('-')
            output.append({'path': ref['path'], 'line_start': int(endpoints[0]), 'line_end': int(endpoints[-1]), 'purpose': ref['purpose']})
    return output


audit = json.loads((HERE.parent / AUDIT).read_text())
body = (HERE / 'cases.js').read_text()
extra_contracts = {
    'S301': ['writable-stream-default-controller-process-write', 'blqs-class'],
    'S302': ['set-up-writable-stream-default-writer'],
    'S303': ['writable-stream-default-controller-process-close'],
    'S304': ['initialize-transform-stream', 'transform-stream-default-controller-enqueue'],
    'S305': ['readable-stream-default-controller-close'],
    'S306': ['readable-stream-default-controller-call-pull-if-needed', 'blqs-class'],
}
mechanisms = ['weighted-ready-promise-epochs', 'successful-sink-start-admission', 'close-resolves-pressured-ready', 'transform-readable-demand-gating', 'async-transform-flush-tail-ownership', 'weighted-readable-pull-admission']
limits = [
    {'writes': 3, 'reads': 0, 'closes': 1, 'gates': 6, 'task_fences': 2, 'payload_bytes': 6},
    {'writes': 2, 'reads': 0, 'closes': 1, 'gates': 1, 'task_fences': 1, 'payload_bytes': 2},
    {'writes': 1, 'reads': 0, 'closes': 1, 'gates': 4, 'task_fences': 2, 'payload_bytes': 4},
    {'writes': 2, 'reads': 4, 'closes': 1, 'gates': 1, 'task_fences': 3, 'payload_bytes': 20},
    {'writes': 1, 'reads': 4, 'closes': 1, 'gates': 2, 'task_fences': 1, 'payload_bytes': 22},
    {'writes': 0, 'reads': 4, 'closes': 1, 'gates': 4, 'task_fences': 1, 'payload_bytes': 8},
]
rows = []
for index, proposal in enumerate(audit['proposed_cases']):
    ident = 'S' + str(301 + index)
    match = re.search(r'^  async ' + ident + r'\(t\) \{\n(.*?)^  \},', body, re.M | re.S)
    assertions = [line.strip() for line in match.group(1).splitlines() if re.search(r't\.(equal|same|deep)\(', line)]
    contracts = [url.replace('https://streams.spec.whatwg.org/', SNAPSHOT) for url in proposal['contract_refs']]
    contracts += [SNAPSHOT + '#' + anchor for anchor in extra_contracts[ident]]
    gap = None
    if ident in ['S304', 'S306']:
        gap = {'classification': 'EXPECTED_FAILURE_CANDIDATE', 'evidence_kind': 'STATIC_SOURCE_INFERENCE_ONLY', 'source_evidence': proposal['source_prediction'], 'intended_oracle_unchanged': True, 'observed_runtime_failure': False}
    rows.append({
        'id': ident, 'intent': proposal['title'], 'mechanism': mechanisms[index], 'implementation': 'cases.js:' + ident,
        'entrypoint': {'method': 'GET', 'path': '/case/' + ident, 'request_body': None},
        'classification': 'ordinary-functional-stream-admission', 'primary_candidate': True, 'independently_reviewed': False,
        'status': 'NOT_RUN', 'runtime_status': 'UNRUN', 'actual_runtime_executions': 0,
        'preconditions': ['Exact guarded source, fresh reviewed binary and deployed fixture/config identity verified.', 'Actual direct-celld Worker with its real global stream constructors and strategies.', 'Independent deadline/resource supervisor controls a proven-owned whole-descendant domain covering dev, bundlers and node despite separate PGIDs, plus one quota/cleanup domain for temporary bundles, logs and stores. No single-PGID fallback or substitute/reference execution.'],
        'trace': proposal['trace'], 'intended_oracle': proposal['oracle'], 'fixed_runtime_assertions': assertions, 'assertion_count': len(assertions),
        'finite_normal_trace_limits': limits[index],
        'cleanup': 'Open all callback and milestone gates. Initiate readable cancellation and writable abortion on still-live owners before joining, so missing HWM0 demand cannot strand an in-flight write. Join original API/closed/ready promises and dynamically recorded callback results, then release owners and observe post-release promises. Require zero pending work, timers and public locks; separate owned-process teardown remains mandatory.',
        'runtime_source_refs': ranges(proposal['source_refs']), 'primary_contract_refs': contracts,
        'overlap_delta': proposal['overlap_delta'], 'distinctness': proposal['mechanism'], 'source_predicted_gap': gap,
        'os_relevance': 'Recovered historical blueprint-archive.ts:145-162 constructs an ordinary TransformStream and sequentially pipes archive prefix then content. The raw file was reread and matches the retained historical hash. This supports stream relevance without claiming those callers use custom weights or user flush callbacks, or that any OS workflow or distributed placement ran.',
    })
emit('manifest.json', {'schema_version': 1, 'profile': PROFILE, 'authored_case_count': 6, 'runtime_status': 'UNRUN', 'runtime_executions': 0, 'reviewed_credit': 0, 'review_receipt_required': True, 'fixture': 'fixture.js', 'config': 'wrangler.json', 'cases': rows})

baseline = [entry['path'] for entry in audit['source_files'] if entry['root'] == 'immutable_baseline' and entry['path'] not in [STREAM, WRITE]]
baseline += ['BUILD_AND_TEST.md', 'MANIFEST.json', 'SHA256SUMS']
campaign = [entry['path'] for entry in audit['source_files'] if entry['root'] == 'accepted_additions'] + [AUDIT, AUDIT.replace('.json', '.md')]
campaign.append(OS_RAW)
native_pin_path = 'celld-os-stress/waves/native-transform-stress/source-pins.json'
native_pins = json.loads((ROOT / native_pin_path).read_text())
emit('source-pins.json', {
    'schema_version': 1, 'source_snapshot': ROOT.name, 'source_root_at_authoring': str(ROOT),
    'upstream_commit': '90b43017241f81189453d326d05948f388b34652', 'binary_sha256': None,
    'binary_note': 'No build or runtime execution. Historical unguarded binary evidence does not qualify these new guarded-source cases.',
    'runtime_sources': [pin(ROOT, path) for path in [STREAM, WRITE, HARNESS, DEV, DEPLOY]],
    'baseline_evidence': [pin(ROOT, path) for path in baseline], 'campaign_evidence': [pin(HERE.parent, path) for path in campaign],
    'fixture_artifacts': [pin(HERE, path) for path in ['cases.js', 'fixture.js', 'wrangler.json']],
    'primary_standard': {'url': 'https://streams.spec.whatwg.org/', 'commit_snapshot': SNAPSHOT, 'commit': 'b9ba9f49d95b4280be0dc2372377a006c3a91c18', 'retrieved_date': '2026-10-09', 'method': 'Primary WHATWG pages read with web tool; no shell download or execution.', 'authority': 'Normative stream algorithms checked independently of implementation source; normative-verification.json records the inspected algorithms.'},
    'os_provenance_context': {'status': 'ONE_RECOVERED_HISTORICAL_RAW_FILE_VERIFIED_FULL_OS_CHECKOUT_UNAVAILABLE', 'os_commit': native_pins['os_commit'], 'source_manifest': native_pin_path, 'preserved_records': [item for item in native_pins['sources'] if '/os/' in item['path']], 'recovered_verified_source': {**pin(HERE.parent, OS_RAW), 'line_start': 145, 'line_end': 162, 'historical_retained_hash_match': True, 'purpose': 'Archive prefix/content sequence uses ordinary TransformStream.'}, 'qualification': 'Only the named raw file was reread. Other preserved entries remain metadata-only. The immutable baseline still lacks OS source; full checkout, dependencies and actual OS execution remain unavailable. No OS acceptance claimed.'},
})
emit('overlap-audit.json', {
    'schema_version': 1, 'evidence': 'STATIC_SOURCE_INSPECTION_ONLY', 'input_audit': pin(HERE.parent, AUDIT),
    'baseline_and_accepted_entries_indexed': audit['baseline_cases_indexed'], 'coverage': audit['coverage'],
    'preauthoring_review': audit['review'], 'per_case_distinctness': {row['id']: {'mechanism': row['mechanism'], 'delta': row['overlap_delta']} for row in rows},
    'retired_duplicates': audit['retired_duplicates'], 'deferred': audit['deferred'],
    'counting': 'Six handwritten candidate mechanisms only. FIFO, terminal bytes, EOF and lock cleanup are shared scaffolding, never separately credited. No HWM/payload parameter matrix, writer handoff or bare drain-close addition.',
})
emit('schedule.json', {
    'schema_version': 1, 'profile': PROFILE, 'runtime_status': 'UNRUN', 'suite_outer_deadline_seconds': 180,
    'preflight_deadline_seconds': 30, 'startup_deadline_seconds': 90, 'cleanup_deadline_seconds': 20,
    'concurrency': 1, 'retries': 0, 'request_count': 6,
    'resource_envelope': {'supervisor_enforced': True, 'runtime_descendant_domain_memory_max_bytes': 536870912, 'runtime_descendant_domain_cpu_cores': 1, 'runtime_descendant_domain_pid_max': 128, 'v8_heap_limit_mb': 128, 'request_response_max_bytes': 65536, 'owned_filesystem_max_bytes': 268435456, 'required_scope': 'Proven-owned whole-descendant execution domain covering dev, bundlers and node even across separate PGIDs; for example an already provisioned cgroup.', 'filesystem_scope': 'Temporary bundles, logs and stores all remain inside the same owned quota/cleanup domain.', 'single_pgid_fallback_allowed': False, 'independent_domain_emptiness_verification_required': True, 'privileged_provisioning_performed': False, 'source_evidence': {'path': DEV, 'line_start': 742, 'line_end': 746}},
    'fixture_budgets_per_request': {'tracked_owners_max': 2, 'tracked_promises_max': 192, 'callback_invocations_max': 16, 'gates_max': 16, 'task_fences_max': 12, 'normal_payload_bytes_max': 22, 'normal_reads_max': 4},
    'temporary_artifact_containment': {'future_linux_environment': {'TMPDIR': 'RUN_DIR/tmp, already created inside fresh owned quota'}, 'logs_and_store': 'Fresh paths inside same owned quota/cleanup domain; verify effective paths.', 'source_evidence': {'path': DEPLOY, 'line_start': 2877, 'line_end': 2882}, 'provisioning_or_execution_performed': False},
    'requests': [{'id': row['id'], 'method': 'GET', 'path': '/case/' + row['id'], 'body': None, 'outer_deadline_seconds': 5, 'repeat': 1, 'response_max_bytes': 65536} for row in rows],
    'completion_contract': ['HTTP 200, exact profile and id, traceEntered true, exact manifest assertion count, all passed, null error.', 'All original operations, ready/closed and callback promises joined; local cleanup COMPLETE with zero pending work, public locks and timers.', 'Exact direct-celld source/build/deployment witnesses verified independently.', 'Independently verify the proven-owned whole-descendant domain is empty, including dev, bundlers and node; remove all disposable bundles, logs and stores inside the owned quota/cleanup domain before acceptance.'],
    'stop_conditions': ['Prerequisite missing before trace entry, including proven whole-descendant containment or owned filesystem quota => BLOCKED/NOT_RUN. No single-PGID fallback.', 'Witnessed entered-case timeout/resource breach => FAIL; uncertain entry or receipt => UNKNOWN. Never report source inference as an observed failure.', 'External timeout teardown only affects the recorded proven-owned whole-descendant domain, with independent emptiness verification; timeout is not a stimulus or pass oracle.', 'Stop after one serial request per case and verified teardown; no retries, multiplication or silent envelope increase.'],
})
