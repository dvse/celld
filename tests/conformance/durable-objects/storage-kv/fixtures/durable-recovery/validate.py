#!/usr/bin/env python3
"""Static checks only. Never imports or calls case functions or launches the SUT."""
import ast,datetime,hashlib,json,pathlib,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent
rows=json.loads((HERE/'manifest.json').read_text());ids=[row['id'] for row in rows]
assert len(rows)==22 and len(set(ids))==22 and ids==[f'D{i:03}' for i in range(1,23)]
required={'intent','trace','stress','oracle','test_function','failure_hypothesis','initial_state','overlap_barrier','ordered_trace','safety_oracle','liveness_oracle','cleanup','bounds','implementation','profile'}
for row in rows:
 assert required.issubset(row) and all(row[key] for key in required)
 assert row['status']=='NOT_RUN' and row['authored'] and not row['run'] and not row['passed'] and not row['reviewed']
 assert row['bounds']['max_http_jobs_simultaneous']==16 and row['bounds']['guest_workload_pids_max']==128
 assert row['implementation']['function']==row['id']==row['test_function']
python_files=sorted(HERE.glob('*.py'))
for path in python_files:compile(ast.parse(path.read_text(),filename=path.name),path.name,'exec')
module=ast.parse((HERE/'cases.py').read_text());functions={node.name:node for node in module.body if isinstance(node,ast.FunctionDef)}
assert set(ids).issubset(functions)
fingerprints=[]
for ident in ids:
 node=functions[ident];assert len(list(ast.walk(node)))>60,ident+' lacks a substantive executable schedule'
 fingerprints.append(ast.dump(ast.Module(body=node.body,type_ignores=[])))
assert len(set(fingerprints))==22,'duplicate case body'
fixture=(HERE/'fixture.js').read_text()
assert 'env.LOADER' not in fixture and 'new RpcTarget' not in fixture and 'STATELESS.get' not in fixture
assert 'ctx.storage.transactionSync' in fixture and 'ctx.storage.setAlarm' in fixture and 'DRS_READ ' in fixture
fleet=json.loads((HERE/'fleet-profile.json').read_text());assert fleet['status']=='BLOCKED' and not fleet['counted_case_ids'] and not fleet['executable_case_ids']
checks=[]
for command in ([sys.executable,'-m','unittest','-v','test_preflight.py'],['node','--input-type=module','--check']):
 process=subprocess.run(command,cwd=HERE,input=fixture if command[0]=='node' else None,text=True,capture_output=True,timeout=20)
 checks.append({'command':command,'exit_code':process.returncode,'stdout':process.stdout,'stderr':process.stderr})
 assert process.returncode==0,checks[-1]
hashes={path.name:hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(HERE.iterdir()) if path.is_file() and path.name not in ('static-evidence.json','inventory.json','readiness.json','review.json')}
record={'status':'STATIC_CHECKS_PASS','timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'authored':22,'reviewed':0,'executable_source_implementations':22,'runtime_cases_run':0,'runtime_cases_passed':0,'python_ast_files':[x.name for x in python_files],'unique_named_case_bodies':22,'checks':checks,'hashes':hashes,'scope':'Static syntax/manifest/pure guard validation only; no guest, runtime, build, client workload or fault launched'}
(HERE/'static-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({key:record[key] for key in ('status','authored','reviewed','executable_source_implementations','runtime_cases_run','runtime_cases_passed')}))
