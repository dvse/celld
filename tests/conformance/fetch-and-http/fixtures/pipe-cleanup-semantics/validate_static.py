#!/usr/bin/env python3
"""Syntax, source-pin and metadata checks only; no Worker/reference execution."""
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
    parser.add_argument('--source-root',type=Path,default=DEFAULT_ROOT)
    args = parser.parse_args()
    checks = []
    for path in sorted(HERE.glob('*.json')):
        if path.name == 'static-validation.json': continue
        json.loads(path.read_text())
        checks.append({'check':'json-parse','file':path.name,'status':'PASS'})
    for path in sorted(HERE.glob('*.py')):
        ast.parse(path.read_text(),filename=path.name)
        checks.append({'check':'python-ast-only','file':path.name,'status':'PASS'})
    manifest=json.loads((HERE/'manifest.json').read_text())
    pins=json.loads((HERE/'source-pins.json').read_text())
    schedule=json.loads((HERE/'schedule.json').read_text())
    expected=['S'+str(i) for i in range(201,210)]
    assert [row['id'] for row in manifest['cases']]==expected
    assert manifest['authored_case_count']==9 and manifest['runtime_executions']==0 and manifest['runtime_status']=='UNRUN'
    assert manifest['reviewed_credit']==0 and manifest['review_receipt_required'] is True
    body=(HERE/'cases.js').read_text()
    assert re.findall(r'^  async (S\d{3})\(t\) \{',body,re.M)==expected
    assertions=0
    for row in manifest['cases']:
        match=re.search(r'^  async '+row['id']+r'\(t\) \{\n(.*?)^  \},',body,re.M|re.S)
        declared=[line.strip() for line in match.group(1).splitlines() if re.search(r't\.(equal|same|deep|before|locked|unlocked)\(',line)]
        assert declared==row['fixed_runtime_assertions']
        assert len(declared)==row['assertion_count'] and len(declared)>=6
        assertions+=len(declared)
        assert row['status']=='NOT_RUN' and row['runtime_status']=='UNRUN' and row['actual_runtime_executions']==0
        assert row['independently_reviewed'] is False and row['primary_candidate'] is True
        assert row['entrypoint']=={'method':'GET','path':'/case/'+row['id'],'request_body':None}
        assert row['primary_contract_refs']==['https://streams.spec.whatwg.org/#readable-stream-pipe-to']
        for ref in row['runtime_source_refs']:
            assert ref['path'] in {p['path'] for p in pins['runtime_sources']}
            assert 1<=ref['line_start']<=ref['line_end']<=len((args.source_root/ref['path']).read_text().splitlines())
    assert len({row['mechanism'] for row in manifest['cases']})==9
    assert [row['id'] for row in manifest['cases'] if row['source_predicted_gap']]==['S207','S208','S209']
    checks.append({'check':'case-manifest-correspondence','cases':9,'assertions':assertions,'status':'PASS'})
    assert [row['id'] for row in schedule['requests']]==expected
    assert schedule['concurrency']==1 and schedule['retries']==0
    assert all(row['outer_deadline_seconds']==5 and row['repeat']==1 for row in schedule['requests'])
    assert schedule['suite_outer_deadline_seconds']==180 and schedule['resource_envelope']['supervisor_enforced'] is True
    config=json.loads((HERE/'wrangler.json').read_text())
    assert config['main']=='fixture.js' and set(config)=={'name','main','compatibility_date'}
    checks.append({'check':'bounded-request-schedule-and-config','status':'PASS'})
    for collection,root in [('runtime_sources',args.source_root),('baseline_evidence',args.source_root),('campaign_evidence',HERE.parent),('fixture_artifacts',HERE)]:
        for pin in pins[collection]:
            raw=(root/pin['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==pin['sha256'] and len(raw)==pin['bytes'], pin['path']
        checks.append({'check':'sha256-'+collection,'files':len(pins[collection]),'status':'PASS'})
    for filename in ['cases.js','fixture.js']:
        raw=(HERE/filename).read_bytes()
        result=subprocess.run(['node','--input-type=module','--check'],input=raw,capture_output=True,timeout=5,check=False)
        assert result.returncode==0,result.stderr.decode()
        checks.append({'check':'node-syntax-only','file':filename,'status':'PASS'})
    fixture=(HERE/'fixture.js').read_text()
    assert 'Promise.all(pipes.map(pipe => pipe.promise))' in fixture
    assert 'for (const gate of gates) gate.open();' in fixture
    assert not re.search(r'\b(fetch|eval)\(',body)
    assert not re.search(r'\b(process|require|WebSocket|DurableObject|WorkerEntrypoint)\b',body)
    assert not re.search(r'node:|https?://',body)
    checks.append({'check':'static-scope-and-cleanup-structure','status':'PASS'})
    print(json.dumps({'status':'STATIC_ONLY','checks':checks,'authored_cases':9,'assertions':assertions,'runtime_status':'UNRUN','runtime_executions':0,'independent_review_claimed':False},indent=2))

if __name__=='__main__': main()
