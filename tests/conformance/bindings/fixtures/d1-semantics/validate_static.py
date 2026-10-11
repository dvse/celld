#!/usr/bin/env python3
"""Syntax and source integrity only. Never evaluates a Worker or executes SQL."""
import ast, hashlib, json, pathlib, re, subprocess
ROOT=pathlib.Path(__file__).resolve().parent
ARCHIVE=pathlib.Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
checks=[]
def check(name,value):
    if not value: raise AssertionError(name)
    checks.append(name)
def digest(data): return hashlib.sha256(data).hexdigest()
worker=(ROOT/'worker.js').read_text()
syntax=subprocess.run(['node','--input-type=module','--check'],input=worker,text=True,capture_output=True,timeout=10)
check('Worker ES module syntax only',syntax.returncode==0)
for path in ROOT.glob('*.py'): ast.parse(path.read_text(),filename=str(path))
checks.append('Python helper syntax only')
manifest=json.loads((ROOT/'manifest.json').read_text())
expected=[f'E{i}' for i in range(201,221)]
check('20 exact manifest IDs',[c['id'] for c in manifest['cases']]==expected)
check('20 exact executable case definitions',re.findall(r'^  (E\d{3}): \{',worker,re.M)==expected)
check('Zero runtime or accepted credit',manifest['review_accepted_cases']==manifest['runtime_executed_cases']==manifest['runtime_pass_cases']==0)
check('Only requested GET case route',r'^\/case\/' in worker and 'request.method !== "GET"' in worker and '|| url.search' in worker)
check('No private routes mocks runtime imports or independent requests',not re.search(r'/runtime/|/do/|CELLD_TEST_|cloudflare:|\bimport\b|\bfetch\(',worker[:worker.index('export default')]))
check('No timeout race or unbounded loops',not re.search(r'Promise\.race|setTimeout|setInterval|\bwhile\s*\(',worker))
check('Hard public call phase cap','++counts[c.phase] > 32' in worker)
check('Missing deployment binding is BLOCKED','status:"BLOCKED"' in worker and worker.index('status:"BLOCKED"')<worker.index('c.claimed.push'))
config=json.loads((ROOT/'wrangler.jsonc').read_text())
check('Minimal D1-only configuration',set(config)=={'name','main','compatibility_date','d1_databases'} and config['main']=='worker.js')
identities={b['binding']:b.get('database_id',b['database_name']) for b in config['d1_databases']}
check('Exact required binding names',set(identities)=={'DB','ALIAS','OTHER','FALLBACK','FALLBACK_ALIAS','EXPLICIT_NAME'})
check('Explicit same-id alias and separate identity',identities['DB']==identities['ALIAS'] and identities['DB']!=identities['OTHER'])
check('Fallback-to-explicit identity convergence',identities['FALLBACK']==identities['FALLBACK_ALIAS']==identities['EXPLICIT_NAME'])
check('Exactly three physical identities',len(set(identities.values()))==3)
lines=worker.splitlines()
for case in manifest['cases']:
    cid=case['id']; a,b=case['fixture_line_range']; body='\n'.join(lines[a-1:b])+'\n'
    check(cid+' fixture slice hash',digest(body.encode())==case['fixture_slice_sha256'])
    check(cid+' explicit source-only state',case['status']=='NEWLY_AUTHORED_UNREVIEWED_NOT_RUN' and case['runtime_execution_count']==0 and case['review_accepted'] is False)
    count=len(re.findall(r'\bc\.(?:exec|batch|all|run|first|raw)\(',body))
    check(cid+' exact finite dispatch count',count==case['schedule']['main_phase_binding_calls_exact_on_success']==len(case['schedule']['main_phase_dispatch_labels_in_order']) and 1<=count<=6)
    check(cid+' exact assertion count',len(re.findall(r'\bc\.eq\(',body))==case['oracle']['successful_assertion_count']==len(case['oracle']['assertions']) and case['oracle']['successful_assertion_count']>0)
    check(cid+' literal assertion source',[line.strip() for line in body.splitlines() if 'c.eq(' in line]==case['oracle']['executable_assertion_source'])
    check(cid+' source oracle finite trace and distinctness',bool(case['source_refs']) and bool(case['fixed_finite_trace']) and bool(case['distinctness']) and case['oracle']['kind']=='PINNED_DIRECT_CELLD_SOURCE_CONTRACT')
    check(cid+' exact owned-table call counts',case['schedule']['setup_binding_calls_exact_on_success']==len(case['owned_resources']) and case['schedule']['cleanup_binding_calls_exact_on_success']==2*len(case['owned_resources']))
    check(cid+' deterministic owned names',all(r['table']==f'd1_next_{cid.lower()}' and r['database_identity']==identities[r['binding']] for r in case['owned_resources']))
    check(cid+' no duplicate physical ownership',len({(r['database_identity'],r['table']) for r in case['owned_resources']})==len(case['owned_resources']))
    for ref in case['source_refs']:
        source=(ARCHIVE/ref['path']).read_text().splitlines()
        check(cid+' valid source ranges '+ref['key'],all(1<=a<=b<=len(source) for a,b in ref['line_ranges']))
        check(cid+' source slice hashes '+ref['key'],[digest(('\n'.join(source[a-1:b])+'\n').encode()) for a,b in ref['line_ranges']]==ref['slices_sha256'])
for pin in json.loads((ROOT/'source-pins.json').read_text())['pins']:
    data=(ARCHIVE/pin['path']).read_bytes()
    check('Immutable source pin '+pin['path'],digest(data)==pin['sha256'] and len(data)==pin['bytes'])
audit=json.loads((ROOT/'overlap-audit.json').read_text())
sibling=audit['current_sibling_wave_audited']
check('Current sibling overlap source hash',digest((ROOT/sibling['path']).read_bytes())==sibling['sha256'])
check('Explicit closest duplicate-column overlap',audit['current_sibling_wave_audited']['case_comparisons']['E209']['neighbors']==['D213'])
report={'status':'STATIC_CHECKS_PASS','checks':checks,'check_count':len(checks),'worker_evaluated':False,'SQL_executed':False,'sut_launched':False,'sut_built':False,'dependencies_installed':False,'runtime_cases_executed':0,'review_acceptance_claimed':False,'external_runtime_limits_enforced':False,'qualification':'Only artifact syntax and metadata integrity verified; runtime prerequisites remain mandatory.'}
(ROOT/'static-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(f'{len(checks)} static checks passed; zero Worker/SQL/SUT executions.')
