#!/usr/bin/env python3
"""Pure static authoring validation. No Guest, runtime, build, fault or workload."""
import ast,collections,datetime,hashlib,json,pathlib,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent;PROJECT=pathlib.Path('/workspace/shared/celld-os-project')
rows=json.loads((HERE/'manifest.json').read_text());ids=[x['id'] for x in rows]
assert ids==[f'U{i:03}' for i in range(1,29)] and len(set(ids))==28
required={'intent','preconditions','trace','stress','oracle','cleanup','initial_state','bounds','test_function','implementation','classification'}
for row in rows:
 assert required.issubset(row) and all(row[key] for key in required)
 assert row['implementation']['function']==row['test_function']==row['id'] and row['implementation']['file']=='cases.py'
 assert row['status']=='NOT_RUN' and not row['run'] and not row['passed'] and not row['reviewed']
 assert row['bounds']['guest_workload_pids_max']==128 and row['bounds']['max_http_jobs_simultaneous']==16
for path in HERE.glob('*.py'):compile(ast.parse(path.read_text(),filename=path.name),path.name,'exec')
source=(HERE/'cases.py').read_text();tree=ast.parse(source);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
fingerprints=[ast.dump(ast.Module(body=functions[x].body,type_ignores=[])) for x in ids];assert len(set(fingerprints))==28
assert all(len(list(ast.walk(functions[x])))>=90 for x in ids)
fixture=(HERE/'fixture-body.js').read_text();assert 'env.LOADER' not in fixture and 'STATELESS' not in fixture and 'new RpcTarget' not in fixture
assert 'transactionSync' in fixture and 'setAlarm' in fixture and 'storage.sync' in fixture
pins=json.loads((HERE/'source-pins.json').read_text());frozen=json.loads((PROJECT/'deliverable/package/reports/final/runtime-manifest.json').read_text());assert frozen['binary_sha256']==pins['binary_sha256']
for pin in pins['sources']:
 assert hashlib.sha256((PROJECT/pin['path']).read_bytes()).hexdigest()==pin['sha256'],pin['path']
 if pin['path'].startswith('deliverable/patch-check-final/'):
  key='celld/'+pin['path'].removeprefix('deliverable/patch-check-final/');assert frozen['source_hashes'][key]==pin['sha256'],key
checks=[]
command=[sys.executable,'-m','unittest','-v','test_preflight.py'];p=subprocess.run(command,cwd=HERE,text=True,capture_output=True,timeout=20)
checks.append({'command':command,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr});assert p.returncode==0,checks[-1]
for path in sorted((HERE/'versions').glob('*/fixture.js')):
 p=subprocess.run(['node','--input-type=module','--check'],input=path.read_text(),text=True,capture_output=True,timeout=10)
 intentional=path.parent.name=='bad-syntax';assert (p.returncode!=0)==intentional,(str(path),p.stderr)
 checks.append({'file':str(path.relative_to(HERE)),'parser_exit':p.returncode,'intentional_invalid_fixture':intentional,'expected_result_observed':True})
source=(HERE/'driver.py').read_text();assert (HERE/'operator_methods.inc').read_text()==source[source.index('    def response('):source.index('    def cleanup(')]
skip={'static-evidence.json','inventory.json','review.json','readiness.json'}
hashes={str(p.relative_to(HERE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(HERE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name not in skip}
record={'status':'STATIC_CHECKS_PASS','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authored':28,'reviewed':0,'executable_source_implementations':28,'runtime_cases_run':0,'runtime_cases_passed':0,'classification_counts':dict(collections.Counter(x['classification'] for x in rows)),'characterization':sum(x['characterization'] for x in rows),'checks':checks,'hashes':hashes,'scope':'Syntax, source pins and pure helper/guard checks only; no runtime, guest, build, staging, workload or fault execution'}
(HERE/'static-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('status','authored','reviewed','executable_source_implementations','runtime_cases_run','runtime_cases_passed','classification_counts','characterization')}))
