#!/usr/bin/env python3
"""Static integrity checks. No Worker evaluation and no SUT execution."""
import ast
import hashlib
import json
import pathlib
import re
import subprocess

ROOT=pathlib.Path(__file__).resolve().parent
ARCHIVE=pathlib.Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
checks=[]
def check(name, condition):
    if not condition: raise AssertionError(name)
    checks.append(name)
worker=(ROOT/'worker.js').read_text()
syntax=subprocess.run(['node','--input-type=module','--check'],input=worker,text=True,capture_output=True,timeout=10)
check('Worker ES-module syntax only',syntax.returncode==0)
for path in ROOT.glob('*.py'): ast.parse(path.read_text(),filename=str(path))
checks.append('Python helper syntax only')
manifest=json.loads((ROOT/'manifest.json').read_text())
expected=[f'K{i}' for i in range(201,221)]
check('20 exact manifest IDs', [c['id'] for c in manifest['cases']]==expected)
check('20 exact executable case definitions', re.findall(r'^  (K\d{3}): \{',worker,re.M)==expected)
check('No accepted or executed count implied',manifest['review_accepted_cases']==manifest['runtime_executed_cases']==manifest['runtime_pass_cases']==0)
check('Route is /case only',r'^\/case\/' in worker)
check('No private route, test knobs, or runtime import',not re.search(r'/runtime/|CELLD_TEST_|cloudflare:|fetch\(',worker[:worker.index('export default')]))
config=json.loads((ROOT/'wrangler.jsonc').read_text())
check('Minimal KV binding configuration',config['main']=='worker.js' and [k['binding'] for k in config['kv_namespaces']]==['KV_A','KV_B'])
check('Distinct namespace identities', len(set(k['id'] for k in config['kv_namespaces']))==2)
lines=worker.splitlines()
for case in manifest['cases']:
    a,b=case['fixture_line_range']; body='\n'.join(lines[a-1:b])+'\n'
    check(case['id']+' source slice hash',hashlib.sha256(body.encode()).hexdigest()==case['fixture_slice_sha256'])
    check(case['id']+' explicit source-only status',case['status']=='NEWLY_AUTHORED_UNREVIEWED_NOT_RUN' and case['runtime_execution_count']==0 and not case['review_accepted'])
    check(case['id']+' source-backed finite contract',bool(case['source_refs']) and bool(case['fixed_finite_trace']) and case['schedule']['main_phase_binding_calls_exact_on_success']<=12 and case['oracle']['successful_assertion_count']>0)
    for ref in case['source_refs']:
        source_lines=(ARCHIVE/ref['path']).read_text().splitlines()
        check(case['id']+' source range '+ref['key'],all(1<=a<=b<=len(source_lines) for a,b in ref['line_ranges']))
for pin in json.loads((ROOT/'source-pins.json').read_text())['pins']:
    check('Source pin '+pin['path'],hashlib.sha256((ARCHIVE/pin['path']).read_bytes()).hexdigest()==pin['sha256'])
report={'status':'STATIC_CHECKS_PASS','checks':checks,'check_count':len(checks),'worker_evaluated':False,'sut_launched':False,'sut_built':False,'dependencies_installed':False,'runtime_cases_executed':0,'review_acceptance_claimed':False}
(ROOT/'static-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(checks)} static checks passed; zero Worker/SUT executions.')
