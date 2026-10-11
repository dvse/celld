#!/usr/bin/env python3
"""Static inventory only. Does not load or execute the Workers fixture."""
import hashlib, json, pathlib, re, subprocess
HERE = pathlib.Path(__file__).resolve().parent
PROJECT = pathlib.Path('/workspace/shared/celld-os-project')
FILES = ('fixture.js', 'cases.js', 'entry.js', 'cases.json', 'wrangler.jsonc', 'README.md', 'run.py', 'validate.py', 'test_preflight.py')
PINS = {
    'celld/crates/celld/js/harness.js': '9d31b01bd4d1a6b136cfbc02bcb26a47deba29f27066009fc3f3b9c6d8d9c407',
    'celld/crates/celld/lib.rs': '24efebb359d84402f4996adebdb80f5fe963044657fbaa47f450e15e99637faf',
}
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    rows = json.loads((HERE / 'cases.json').read_text())
    required = {'id', 'intent', 'preconditions', 'trace', 'failure_schedule', 'stress', 'oracle', 'cleanup', 'layer', 'gate', 'source_contracts', 'profile', 'outer_wall_seconds'}
    ids = [row['id'] for row in rows]
    assert len(ids) == len(set(ids)) == 36
    assert all(required <= row.keys() and len(row['trace']) >= 3 for row in rows)
    assert all(row['layer'] == 'real-process-RPC' and row['outer_wall_seconds'] == 30 for row in rows)
    assert all(row['gate'] in {'promotion', 'characterization'} for row in rows)
    source = (HERE / 'cases.js').read_text()
    traces = re.findall(r'^  async (O\d{3})\(s\) \{\n(.*?)(?=\n  \},|\n  \}\n)', source, re.M | re.S)
    assert len(traces) == len(ids) and {id for id, _ in traces} == set(ids), 'literal trace/manifest mismatch'
    # Reject byte-identical bodies and simple quote/label-only clones. This supplements,
    # never substitutes for, independent semantic distinctness review.
    shapes = {}
    for id, body in traces:
        shape = re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", 'STRING', body)
        shape = re.sub(r'\s+', '', shape)
        assert shape not in shapes, ('label-only trace duplicate', id, shapes.get(shape))
        shapes[shape] = id
    for name in ('fixture.js', 'cases.js', 'entry.js'):
        subprocess.run(['node', '--input-type=module', '--check'], input=(HERE / name).read_text(), text=True, check=True, capture_output=True)
    for name in ('run.py', 'validate.py', 'test_preflight.py'): compile((HERE / name).read_text(), name, 'exec')
    config = json.loads((HERE / 'wrangler.jsonc').read_text())
    assert config['compatibility_date'] == '2026-09-04'
    assert config['compatibility_flags'] == ['rpc_params_dup_stubs']
    contracts = set(re.findall(r'- (SC-[A-Z]+):', (HERE / 'README.md').read_text()))
    assert all(set(row['source_contracts']) <= contracts for row in rows)
    for name in ('fixture.js', 'cases.js', 'entry.js'):
        assert '__celld$' not in (HERE / name).read_text(), 'internal transport marker in fixture'
    for relative, digest in PINS.items(): assert sha(PROJECT / relative) == digest, ('frozen source changed', relative)
    review = HERE / 'review.json'; accepted = []
    if review.exists():
        record = json.loads(review.read_text())
        for filename, expected in record['reviewed_sha256'].items(): assert sha(HERE / filename) == expected, ('stale review', filename)
        accepted = record['accepted_promotion_candidate_ids']
        assert len(accepted) == len(set(accepted)) and set(accepted) <= {r['id'] for r in rows if r['gate'] == 'promotion'}
    return {
        'status': 'NOT_RUN', 'authored': len(rows), 'implemented_assertion_traces': len(traces),
        'independently_reviewed': len(accepted), 'independently_reviewed_ids': accepted,
        'runnable_with_verified_adapter': 0, 'run': 0, 'passed': 0,
        'promotion_candidates': sum(r['gate'] == 'promotion' for r in rows),
        'characterization_cases': sum(r['gate'] == 'characterization' for r in rows),
        'source_predicted_api_blocked_ids': ['O033', 'O034', 'O035', 'O036'],
        'case_ids': ids, 'files_sha256': {name: sha(HERE / name) for name in FILES},
        'source_sha256': PINS, 'target_binary_sha256': '62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e',
        'review_record_sha256': sha(review) if review.exists() else None,
        'notes': 'Static syntax, profile, registry and quote-normalized body uniqueness checks only. No Workers module executed, no runtime/guest launched, no real-process adapter qualified, no system-under-test trace entered.'
    }
if __name__ == '__main__': print(json.dumps(main(), indent=2))
