#!/usr/bin/env python3
"""Read-only syntax/provenance/metadata checks. Never execute or import fixtures."""
import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
EXPECTED = ['S' + str(i) for i in range(301, 307)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    checks = []
    for path in sorted(HERE.glob('*.json')):
        if path.name == 'static-validation.json':
            continue
        json.loads(path.read_text())
        checks.append({'check': 'json-parse', 'file': path.name, 'status': 'PASS'})
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_text(), filename=path.name)
        checks.append({'check': 'python-ast-only', 'file': path.name, 'status': 'PASS'})
    manifest = json.loads((HERE / 'manifest.json').read_text())
    pins = json.loads((HERE / 'source-pins.json').read_text())
    schedule = json.loads((HERE / 'schedule.json').read_text())
    normative = json.loads((HERE / 'normative-verification.json').read_text())
    assert [row['id'] for row in manifest['cases']] == EXPECTED
    assert manifest['authored_case_count'] == 6 and manifest['runtime_executions'] == 0 and manifest['runtime_status'] == 'UNRUN'
    assert manifest['reviewed_credit'] == 0 and manifest['review_receipt_required'] is True
    assert len({row['mechanism'] for row in manifest['cases']}) == 6
    assert [row['id'] for row in manifest['cases'] if row['source_predicted_gap']] == ['S304', 'S306']
    body = (HERE / 'cases.js').read_text()
    fixture = (HERE / 'fixture.js').read_text()
    assert re.findall(r'^  async (S\d{3})\(t\) \{', body, re.M) == EXPECTED
    assertions = 0
    for row in manifest['cases']:
        match = re.search(r'^  async ' + row['id'] + r'\(t\) \{\n(.*?)^  \},', body, re.M | re.S)
        case = match.group(1)
        declared = [line.strip() for line in case.splitlines() if re.search(r't\.(equal|same|deep)\(', line)]
        assert declared == row['fixed_runtime_assertions']
        assert len(declared) == row['assertion_count'] and len(declared) >= 10
        assertions += len(declared)
        assert row['status'] == 'NOT_RUN' and row['runtime_status'] == 'UNRUN' and row['actual_runtime_executions'] == 0
        assert row['independently_reviewed'] is False and row['primary_candidate'] is True
        assert row['entrypoint'] == {'method': 'GET', 'path': '/case/' + row['id'], 'request_body': None}
        assert row['overlap_delta'] and row['primary_contract_refs']
        assert all(url.startswith(normative['snapshot'] + '#') for url in row['primary_contract_refs'])
        assert normative['cases'][row['id']]['algorithms']
        bounds = row['finite_normal_trace_limits']
        for call, key in [('write', 'writes'), ('read', 'reads'), ('gate', 'gates'), ('checkpoint', 'task_fences')]:
            assert len(re.findall(r't\.' + call + r'\(', case)) == bounds[key], (row['id'], key)
        assert bounds['reads'] <= 4 and bounds['payload_bytes'] <= 22
        for ref in row['runtime_source_refs']:
            assert ref['path'] in {entry['path'] for entry in pins['runtime_sources']}
            assert 1 <= ref['line_start'] <= ref['line_end'] <= len((args.source_root / ref['path']).read_text().splitlines())
    assert assertions == 84
    checks.append({'check': 'case-manifest-correspondence-and-finite-traces', 'cases': 6, 'assertions': assertions, 'status': 'PASS'})
    assert [row['id'] for row in schedule['requests']] == EXPECTED
    assert schedule['concurrency'] == 1 and schedule['retries'] == 0 and schedule['request_count'] == 6
    assert all(row['outer_deadline_seconds'] == 5 and row['repeat'] == 1 and row['body'] is None and row['path'] == '/case/' + row['id'] and row['method'] == 'GET' for row in schedule['requests'])
    assert schedule['suite_outer_deadline_seconds'] == 180 and schedule['resource_envelope']['supervisor_enforced'] is True
    assert schedule['resource_envelope']['single_pgid_fallback_allowed'] is False
    assert schedule['resource_envelope']['independent_domain_emptiness_verification_required'] is True
    assert schedule['resource_envelope']['runtime_descendant_domain_memory_max_bytes'] == 536870912
    assert schedule['resource_envelope']['runtime_descendant_domain_cpu_cores'] == 1
    assert schedule['resource_envelope']['runtime_descendant_domain_pid_max'] == 128
    assert schedule['resource_envelope']['owned_filesystem_max_bytes'] == 268435456
    assert schedule['preflight_deadline_seconds'] + schedule['startup_deadline_seconds'] + schedule['cleanup_deadline_seconds'] + 30 <= 180
    config = json.loads((HERE / 'wrangler.json').read_text())
    assert config['main'] == 'fixture.js' and set(config) == {'name', 'main', 'compatibility_date'}
    checks.append({'check': 'serial-bounded-schedule-and-minimal-config', 'status': 'PASS'})
    for collection, root in [('runtime_sources', args.source_root), ('baseline_evidence', args.source_root), ('campaign_evidence', HERE.parent), ('fixture_artifacts', HERE)]:
        for pin in pins[collection]:
            raw = (root / pin['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == pin['sha256'] and len(raw) == pin['bytes'], pin['path']
        checks.append({'check': 'sha256-' + collection, 'files': len(pins[collection]), 'status': 'PASS'})
    baseline_manifest = json.loads((args.source_root / 'MANIFEST.json').read_text())
    baseline_index = {entry['path']: entry for entry in baseline_manifest['files']}
    for pin in pins['runtime_sources'] + pins['baseline_evidence']:
        if pin['path'] in ['MANIFEST.json', 'SHA256SUMS']:
            continue
        assert baseline_index[pin['path']]['sha256'] == pin['sha256']
    assert pins['binary_sha256'] is None
    assert pins['os_provenance_context']['recovered_verified_source']['sha256'] == '3169045728d1eb6a9de86afa08b1eddf8c14766affda28e8e95f1d01a2a846c1'
    checks.append({'check': 'immutable-baseline-and-recovered-os-provenance', 'status': 'PASS'})
    for filename in ['cases.js', 'fixture.js']:
        result = subprocess.run(['node', '--input-type=module', '--check'], input=(HERE / filename).read_bytes(), capture_output=True, timeout=5, check=False)
        assert result.returncode == 0, result.stderr.decode()
        checks.append({'check': 'node-syntax-only', 'file': filename, 'status': 'PASS'})
    assert 'for (const gate of gates) gate.open();' in fixture
    assert "for (const kind of ['reader', 'writer'])" in fixture
    assert fixture.index('await Promise.all(stops.map(state => state.promise));') < fixture.index('const terminalProofs = owners.map')
    assert 'while (joined < observations.length)' in fixture
    assert "import { cases } from './cases.js';" in fixture
    assert all(token in body for token in ['await t.value(started); await t.checkpoint();', "const prefixRead = t.read(reader, 'flush-prefix-read');", 'firstGate.open(); await t.value(firstSettlement); await t.checkpoint();'])
    assert body.index("const prefixRead = t.read(reader, 'flush-prefix-read');") < body.index("const prefixWrite = t.write(writer, 'fixed', 'flush-prefix-write');")
    assert not re.search(r'\b(fetch|eval|setTimeout|setInterval|setImmediate)\(', body)
    assert not re.search(r'\bprocess\s*\.|\brequire\s*\(|\b(WebSocket|DurableObject|WorkerEntrypoint)\b', body)
    assert not re.search(r'node:|https?://|globalThis\s*\.', body)
    assert not re.search(r'\._[A-Za-z]', body)
    assert 'Promise.race' not in body + fixture
    checks.append({'check': 'static-real-globals-scope-settlement-and-cleanup-structure', 'status': 'PASS'})
    print(json.dumps({'status': 'STATIC_ONLY', 'checks': checks, 'authored_cases': 6, 'assertions': assertions, 'source_predicted_gap_ids': ['S304', 'S306'], 'runtime_status': 'UNRUN', 'runtime_executions': 0, 'independent_review_claimed': False, 'limitations': ['Syntax and structural checks do not execute JavaScript or establish runtime outcomes.', 'External exact-source deployment, request deadlines, process limits and teardown remain required.']}, indent=2))


if __name__ == '__main__':
    main()
