#!/usr/bin/env python3
"""Static inventory only: parse source/manifests; never execute the Workers fixture."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = Path('/workspace/shared/celld-os-project')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = json.loads((ROOT / 'cases.json').read_text())
    required = {'id', 'intent', 'preconditions', 'trace', 'stress', 'oracle', 'cleanup', 'layer', 'gate', 'source_contracts'}
    ids = [row['id'] for row in rows]
    assert len(ids) == len(set(ids)) == 40
    for row in rows:
        assert required <= row.keys(), (row['id'], 'missing required fields')
        assert all(row[field] for field in required), (row['id'], 'empty required field')
        assert isinstance(row['trace'], list) and len(row['trace']) >= 3
        assert row['gate'] in {'promotion', 'characterization'}
        assert row['layer'] == 'real-process-RPC'
    source = (ROOT / 'codec.js').read_text()
    implemented = re.findall(r'async (C\d{3})\(', source)
    assert len(implemented) == len(set(implemented)), 'duplicate literal implementation'
    assert set(implemented) == set(ids), 'manifest/implementation mismatch'
    assert '__celld$' not in source, 'raw marker namespace unexpectedly present'
    for name in ('codec.js', 'entry.js'):
        subprocess.run(['node', '--input-type=module', '--check'], input=(ROOT / name).read_text(), text=True, capture_output=True, check=True)
    json.loads((ROOT / 'wrangler.jsonc').read_text())
    contracts = set(re.findall(r'- (SC-[A-Z-]+):', (ROOT / 'README.md').read_text()))
    for row in rows:
        assert set(row['source_contracts']) <= contracts, (row['id'], 'undefined source contract')
    review_path = ROOT / 'review.json'
    accepted = []
    if review_path.exists():
        review = json.loads(review_path.read_text())
        for name, expected in review['reviewed_sha256'].items():
            assert sha(ROOT / name) == expected, ('independent review stale', name)
        accepted = review['accepted_promotion_candidate_ids']
        assert len(accepted) == len(set(accepted))
        assert set(accepted) <= {row['id'] for row in rows if row['gate'] == 'promotion'}
    report = {
        'status': 'NOT_RUN', 'authored': len(rows), 'independently_reviewed': len(accepted),
        'independently_reviewed_ids': accepted,
        'independent_review_scope': 'Static distinctness/oracle acceptance of listed promotion candidates only; characterization remains pending promotion',
        'review_record_sha256': sha(review_path) if review_path.exists() else None,
        'implemented_assertion_traces': len(implemented), 'standalone_entry_syntax_checked': True,
        'runnable_with_verified_adapter': 0, 'run': 0, 'passed': 0,
        'promotion_candidates': sum(row['gate'] == 'promotion' for row in rows),
        'characterization_cases': sum(row['gate'] == 'characterization' for row in rows),
        'fresh_owned_fixture_required': [row['id'] for row in rows if row.get('isolation') == 'fresh-owned-fixture-required'],
        'case_ids': ids,
        'files_sha256': {name: sha(ROOT / name) for name in ('codec.js', 'cases.json', 'entry.js', 'wrangler.jsonc', 'README.md', 'validate.py')},
        'dependency_sha256': {str(path.relative_to(PROJECT)): sha(path) for path in [PROJECT / 'celld/crates/celld/js/harness.js', PROJECT / 'celld/crates/celld/js/storage_ops.rs', PROJECT / 'celld/crates/celld/lib.rs']},
        'existing_fixture_dependency_sha256': {name: sha(ROOT.parent.parent / 'fixture' / name) for name in ('index.js', 'rpc.js')},
        'target_binary_sha256': '62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e',
        'notes': 'Syntax/registry checks plus hash-validated independent static review record when present. No runtime execution or adapter qualification. Parent integration and bounded adapter required.'
    }
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
