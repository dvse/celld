#!/usr/bin/env python3
"""Static JSON/AST/hash/JavaScript-parser checks; never evaluate JS or run celld."""
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    checks = []
    for path in sorted(HERE.glob('*.json')):
        if path.name != 'static-validation.json':
            json.loads(path.read_text())
            checks.append({'check': 'json-parse', 'file': path.name, 'status': 'PASS'})
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_text(), filename=path.name)
        checks.append({'check': 'python-ast-only', 'file': path.name, 'status': 'PASS'})
    manifest = json.loads((HERE / 'manifest.json').read_text())
    schedule = json.loads((HERE / 'schedule.json').read_text())
    pins = json.loads((HERE / 'source-pins.json').read_text())
    code = (HERE / 'cases.js').read_text()
    assert re.findall(r'^  async (Y\d{3})\(t\) \{', code, re.M) == ['Y301']
    assert manifest['authored_case_count'] == 1 and manifest['reviewed_case_count'] == 0
    assert manifest['runtime_status'] == 'UNRUN' and manifest['runtime_executions'] == 0
    assert len(manifest['cases']) == 1
    case = manifest['cases'][0]
    assert case['id'] == 'Y301' and case['status'] == 'NOT_RUN' and case['actual_runtime_executions'] == 0
    assert case['review_status'] == 'UNREVIEWED' and case['independently_reviewed'] is False
    fixed = [line.strip() for line in code.splitlines() if re.search(r't\.(equal|deep)\(', line)]
    assert fixed == case['fixed_runtime_assertions'] and len(fixed) == case['assertion_count'] == 11
    assert code.count('controller.enqueue(') == 1 and code.count('t.clone(') == 1
    assert code.count('t.read(') == 4 and code.count('Promise.allSettled(') == 2
    assert 'left[0] = 99;' in code and 'left.buffer === right.buffer, false' in code
    assert case['entrypoint'] == {'method': 'GET', 'path': '/case/Y301', 'request_body': None}
    assert [entry['id'] for entry in schedule['requests']] == ['Y301']
    assert schedule['request_count'] == 1 and schedule['concurrency'] == 1 and schedule['retries'] == 0
    assert schedule['requests'][0]['outer_deadline_seconds'] == 5
    config = json.loads((HERE / 'wrangler.json').read_text())
    assert config['main'] == 'fixture.js' and config['compatibility_date'] == '2026-09-04'
    assert set(config) == {'name', 'main', 'compatibility_date'}
    checks.append({'check': 'case-manifest-schedule-bijection-and-fixed-oracle', 'cases': 1, 'assertions': 11, 'status': 'PASS'})
    source_paths = {pin['path'] for pin in pins['runtime_sources']}
    for ref in case['runtime_source_refs']:
        assert ref['path'] in source_paths
        assert 1 <= ref['line_start'] <= ref['line_end'] <= len(Path(ref['path']).read_text().splitlines())
    for collection, root in [('runtime_sources', None), ('source_and_scope_evidence', None), ('frozen_57_wave_artifacts', Path(pins['frozen_artifacts_root'])), ('fixture_artifacts', HERE)]:
        for pin in pins[collection]:
            path = root / pin['path'] if root else Path(pin['path'])
            data = path.read_bytes()
            assert hashlib.sha256(data).hexdigest() == pin['sha256'] and len(data) == pin['bytes'], str(path)
        checks.append({'check': 'sha256-' + collection, 'files': len(pins[collection]), 'status': 'PASS'})
    overlap = json.loads((HERE / 'overlap-audit.json').read_text())
    assert overlap['id_collision_audit']['matches'] == []
    assert overlap['id_collision_audit']['result'] == 'NO_COLLISION'
    for filename in ['cases.js', 'fixture.js']:
        result = subprocess.run(['node', '--input-type=module', '--check'], input=(HERE / filename).read_bytes(), capture_output=True, timeout=5, check=False)
        assert result.returncode == 0, result.stderr.decode()
        checks.append({'check': 'node-parser-only-no-evaluation', 'file': filename, 'command': 'node --input-type=module --check < ' + filename, 'status': 'PASS'})
    print(json.dumps({'status': 'STATIC_ONLY', 'checks': checks, 'authored_cases': 1, 'assertions': 11, 'status_of_case': 'NOT_RUN', 'runtime_status': 'UNRUN', 'runtime_executions': 0, 'javascript_evaluation': False, 'independent_review_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
