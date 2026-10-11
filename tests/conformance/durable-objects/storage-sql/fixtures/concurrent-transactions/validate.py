#!/usr/bin/env python3
"""Static parsing/manifests/source-digest checks; never evaluates fixture JavaScript."""
import ast,datetime,hashlib,json,pathlib,re,subprocess
HERE=pathlib.Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
rows=json.loads((HERE/'manifest.json').read_text());expected=[f'T{n:03}' for n in range(1,33)];assert [row['id'] for row in rows]==expected
required={'id','intent','preconditions','trace','stress','oracle','cleanup','implementation','test_function','layer','classification','promotion','characterization'}
for row in rows:
 assert required<=row.keys() and isinstance(row['implementation'],str) and isinstance(row['trace'],list) and len(row['trace'])>=3
 assert row['test_function']==row['id'] and row['status']=='NOT_RUN'
 assert isinstance(row['characterization'],bool)
assert len({row['intent'] for row in rows})==32
body=(HERE/'cell-cases.js').read_text();driver=(HERE/'cases.js').read_text();assert re.findall(r' async (T\d{3})\(',body)==expected
assert sorted(re.findall(r'(T\d{3})(?::async|\(s\))',driver))==expected
assert len({sha_part:=hashlib.sha256(line.split('(c)',1)[1].encode()).hexdigest() for line in body.splitlines() if re.match(r' async T\d{3}',line)})==32
javascript=[]
for path in sorted(HERE.glob('*.js')):
 subprocess.run(['node','--input-type=module','--check'],input=path.read_bytes(),check=True,capture_output=True);javascript.append(path.name)
subprocess.run(['node','--check',str(HERE/'test_helpers.mjs')],check=True,capture_output=True)
python=[]
for path in sorted(HERE.glob('*.py')):ast.parse(path.read_text(),filename=str(path));python.append(path.name)
pins=json.loads((HERE/'source-pins.json').read_text());assert sha(pathlib.Path(pins['runtime_manifest']))==pins['runtime_manifest_sha256'];runtime=json.loads(pathlib.Path(pins['runtime_manifest']).read_text());assert runtime['binary_sha256']==pins['binary_sha256']
for source in pins['sources']:
 assert sha(pathlib.Path(source['path']))==source['sha256']
 if source['manifest_key']:assert runtime['source_hashes'][source['manifest_key']]==source['sha256']
profile=json.loads((HERE/'profile.json').read_text());assert profile['required_limits']['memory_mib']==512 and profile['required_limits']['vcpus']==1 and profile['enforced_here'] is False
files=[p for p in HERE.iterdir() if p.is_file() and p.name not in {'static-evidence.json','inventory.json','review-request.json','review.json'}]
hashes={p.name:sha(p) for p in sorted(files)}
report={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS_STATIC_ONLY','javascript_parsed_not_evaluated':javascript,'python_ast_parsed':python,'case_count':32,'source_files_verified':len(pins['sources']),'artifact_hashes':hashes,'sut_runs':0,'sut_passes':0,'network_requests':0,'builds':0,'vm_launches':0}
(HERE/'static-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
inventory={'wave':'sqlite-concurrency','ids':expected,'authored':32,'executable_assertion_bodies':32,'request_only_adapter_present':True,'integration_ready':False,'external_supervisor_required':True,'independently_reviewed':0,'run':0,'passed':0,'characterization_ids':['T014','T021','T029'],'classification_counts':{kind:sum(row['classification']==kind for row in rows) for kind in sorted({row['classification'] for row in rows})},'implementation_hashes':hashes,'source_pins_sha256':sha(HERE/'source-pins.json'),'status':'PENDING_INDEPENDENT_REVIEW_NOT_RUN'}
(HERE/'inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['status','case_count','source_files_verified','sut_runs','network_requests']}))
