#!/usr/bin/env python3
"""Metadata, pin, and syntax checks only. Never execute a Worker or URL API."""
import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_ROOT = Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    checks = []
    for path in sorted(HERE.glob('*.json')):
        if path.name == 'static-validation.json':
            continue  # This command's report may be the stdout redirection target.
        json.loads(path.read_text())
        checks.append({'check': 'json-parse', 'file': path.name, 'status': 'PASS'})
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_text(), filename=path.name)
        checks.append({'check': 'python-ast-only', 'file': path.name, 'status': 'PASS'})

    manifest = json.loads((HERE / 'manifest.json').read_text())
    pins = json.loads((HERE / 'source-pins.json').read_text())
    expected = ['Y' + str(i) for i in range(201, 221)]
    assert [case['id'] for case in manifest['cases']] == expected
    assert manifest['runtime_executions'] == 0 and manifest['runtime_status'] == 'UNRUN'
    assert manifest['authored_case_count'] == 20
    body = (HERE / 'cases.js').read_text()
    assert re.findall(r'^  async (Y\d{3})\(t\) \{', body, re.M) == expected
    source_pin_paths = {pin['path'] for pin in pins['runtime_sources']}
    assertion_total = 0
    for case in manifest['cases']:
        case_id = case['id']
        match = re.search(r'^  async ' + case_id + r'\(t\) \{\n(.*?)^  \},', body, re.M | re.S)
        assert match
        assertions = [line.strip() for line in match.group(1).splitlines() if re.search(r't\.(equal|deep)\(', line)]
        assert assertions == case['fixed_runtime_assertions']
        assert len(assertions) == case['assertion_count'] and 1 <= len(assertions) <= 16
        assertion_total += len(assertions)
        assert case['entrypoint'] == {'method': 'GET', 'path': '/case/' + case_id, 'request_body': None}
        assert case['runtime_status'] == 'UNRUN' and case['actual_runtime_executions'] == 0
        assert case['independently_reviewed'] is False
        assert case['primary_contract_refs'] and case['distinctness'] and case['trace']
        for ref in case['runtime_source_refs']:
            assert ref['path'] in source_pin_paths
            lines = (args.source_root / ref['path']).read_text().splitlines()
            assert 1 <= ref['line_start'] <= ref['line_end'] <= len(lines)
    assert len({case['mechanism'] for case in manifest['cases']}) == 20
    checks.append({'check': 'case-manifest-correspondence', 'cases': 20, 'assertions': assertion_total, 'status': 'PASS'})

    schedule = json.loads((HERE / 'schedule.json').read_text())
    assert [entry['id'] for entry in schedule['requests']] == expected
    assert [entry['path'] for entry in schedule['requests']] == ['/case/' + case_id for case_id in expected]
    assert schedule['suite_outer_deadline_seconds'] == 300
    assert all(entry['outer_deadline_seconds'] == 5 for entry in schedule['requests'])
    config = json.loads((HERE / 'wrangler.json').read_text())
    assert config['main'] == 'fixture.js' and config['compatibility_date'] == '2026-09-04'
    assert set(config) == {'name', 'main', 'compatibility_date'}

    for collection, root in [('runtime_sources', args.source_root), ('baseline_evidence', args.source_root), ('campaign_evidence', HERE.parent), ('fixture_artifacts', HERE)]:
        for pin in pins[collection]:
            path = root / pin['path']
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == pin['sha256'], f'pin mismatch: {path}'
        checks.append({'check': 'sha256-' + collection, 'files': len(pins[collection]), 'status': 'PASS'})

    for filename in ['cases.js', 'fixture.js']:
        result = subprocess.run(['node', '--input-type=module', '--check'], input=(HERE / filename).read_bytes(), capture_output=True, timeout=5, check=False)
        assert result.returncode == 0, result.stderr.decode()
        checks.append({'check': 'node-syntax-only', 'file': filename, 'command': 'node --input-type=module --check < ' + filename, 'status': 'PASS'})

    print(json.dumps({'status': 'STATIC_ONLY', 'checks': checks, 'authored_cases': 20, 'assertions': assertion_total, 'runtime_status': 'UNRUN', 'runtime_executions': 0, 'independent_review_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
