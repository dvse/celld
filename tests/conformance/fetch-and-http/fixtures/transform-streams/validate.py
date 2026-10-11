#!/usr/bin/env python3
"""Read-only source checking, plus static evidence output. Never loads a JS case."""
import ast,datetime,hashlib,json,pathlib,re,subprocess
HERE=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((HERE/'manifest.json').read_text());expected=[f'X{i:03}' for i in range(1,25) if i!=17]
assert [r['id'] for r in rows]==expected
required={'id','intent','preconditions','trace','stress','oracle','cleanup','implementation','test_function','layer','classification','promotion'}
for r in rows:
 assert required<=r.keys() and isinstance(r['implementation'],str) and r['implementation']=='operations.js:'+r['id']
 assert isinstance(r['trace'],list) and len(r['trace'])==3 and len(r['preconditions'])==4
 assert r['test_function']==r['id'] and r['status']=='NOT_RUN' and r['promotion'] is True
assert len({r['intent'] for r in rows})==23 and len({r['hold_label'] for r in rows})==23
source=(HERE/'operations.js').read_text();assert re.findall(r' async (X\d{3})\(c\)',source)==expected
pieces=re.split(r' async X\d{3}\(c\)\{',source)[1:];assert len({hashlib.sha256(x.encode()).hexdigest() for x in pieces})==23
fixture=(HERE/'fixture.js').read_text()
for r in rows:assert r["id"]+":['"+r['hold_label']+"','"+r['peer_operation']+"']" in fixture
javascript=[]
for path in sorted(HERE.glob('*.js')):
 subprocess.run(['node','--input-type=module','--check'],input=path.read_bytes(),check=True,capture_output=True);javascript.append(path.name)
for path in sorted(HERE.glob('*.mjs')):subprocess.run(['node','--check',str(path)],check=True,capture_output=True)
python=[]
for path in sorted(HERE.glob('*.py')):ast.parse(path.read_text(),filename=str(path));python.append(path.name)
pins=json.loads((HERE/'source-pins.json').read_text());assert sha(pathlib.Path(pins['runtime_manifest']))==pins['runtime_manifest_sha256'];runtime=json.loads(pathlib.Path(pins['runtime_manifest']).read_text());assert runtime['binary_sha256']==pins['binary_sha256']
for item in pins['sources']:
 assert sha(pathlib.Path(item['path']))==item['sha256']
 if item['manifest_key']:assert runtime['source_hashes'][item['manifest_key']]==item['sha256']
profile=json.loads((HERE/'profile.json').read_text());limits=profile['required_limits'];assert limits['case_wall_seconds']==30 and limits['memory_mib']==512 and limits['pids']==128 and limits['vcpus']==1 and limits['native_operations_max']==4 and limits['operation_output_bytes_max']==262144 and limits['total_fixture_bytes_max']==4194304
assert profile['enforced_here'] is False
files=[p for p in HERE.iterdir() if p.is_file() and p.name not in {'static-evidence.json','inventory.json','review.json','review-request.json','review-notes.md'}]
hashes={p.name:sha(p) for p in sorted(files)}
record={'status':'PASS_STATIC_ONLY','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'case_count':23,'javascript_parsed_not_evaluated':javascript,'python_ast_parsed':python,'source_files_verified':len(pins['sources']),'artifact_hashes':hashes,'sut_runs':0,'sut_passes':0,'network_requests':0,'builds':0,'vm_launches':0}
(HERE/'static-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
(HERE/'inventory.json').write_text(json.dumps({'wave':'native-transform-stress','ids':expected,'authored':23,'executable_assertion_bodies':23,'request_only_adapter_present':True,'integration_ready':False,'independently_reviewed':0,'run':0,'passed':0,'classification_counts':{k:sum(r['classification']==k for r in rows) for k in sorted({r['classification'] for r in rows})},'implementation_hashes':hashes,'status':'PENDING_REVISION_REVIEW_NOT_RUN','removed_duplicate_ids':['X017'],'historical_review_snapshot':'history/review-8085e883'},indent=2)+'\n')
print(json.dumps({k:record[k] for k in ['status','case_count','source_files_verified','sut_runs','network_requests']}))
