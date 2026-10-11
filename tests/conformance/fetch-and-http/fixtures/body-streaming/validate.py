#!/usr/bin/env python3
"""Static syntax/schema/hash census only. Does not execute fixture or adapter calls."""
import ast, collections, hashlib, json, pathlib, re, subprocess
HERE=pathlib.Path(__file__).resolve().parent
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
rows=json.loads((HERE/'manifest.json').read_text());ids=[row['id'] for row in rows]
assert len(ids)==26 and len(set(ids))==26 and ids==['H%03d'%n for n in range(1,27)]
source=(HERE/'cases.js').read_text();definitions=list(re.finditer(r'export async function (H\d{3})\(t\) \{',source))
assert [match.group(1) for match in definitions]==ids
case_hashes={}
for i,match in enumerate(definitions):
 end=definitions[i+1].start() if i+1<len(definitions) else source.index('export const CASES=')
 case_hashes[match.group(1)]=hashlib.sha256(source[match.start():end].encode()).hexdigest()
assert len(set(case_hashes.values()))==26
for row in rows:
 assert all(row.get(key) for key in ['intent','failure_hypothesis','preconditions','trace','stress','oracle','cleanup','distinctness','implementation'])
 assert len(row['trace'])>=3 and len(row['preconditions'])>=6
 assert row['authored'] is True and row['run'] is False and row['passed'] is False and row['status']=='NOT_RUN'
 assert row['stress']['wall_seconds_max']<=30 and row['stress']['coordinator_http_max']==6
 assert row['stress']['logical_payload_bytes_max']==4194304
# Parse only: no cloudflare module resolution, top-level evaluation or case invocation.
checks=[]
for path in sorted(HERE.glob('*.js')):
 result=subprocess.run(['node','--input-type=module','--check'],input=path.read_text(),text=True,capture_output=True,timeout=5)
 assert result.returncode==0,(path.name,result.stderr);checks.append('node-parse:'+path.name)
for path in sorted(HERE.glob('*.py')):ast.parse(path.read_text());checks.append('python-ast:'+path.name)
profile=json.loads((HERE/'profile.json').read_text());wrangler=json.loads((HERE/'wrangler.jsonc').read_text())
assert profile['id']=='http-stream-stress-frozen-v1' and wrangler['main']=='fixture.js'
assert wrangler['vars']['PRIVATE_ORIGIN']==profile['fixed_recipient_origin']=='http://192.168.77.1:18080'
assert profile['limits']['fixture_read_operations_per_body_max']==262144
pins=json.loads((HERE/'source-pins.json').read_text());manifest=pathlib.Path(pins['runtime_manifest'])
assert sha(manifest)==pins['runtime_manifest_sha256'];frozen=json.loads(manifest.read_text());assert pins['binary_sha256']==frozen['binary_sha256']==profile['binary_sha256']
for item in pins['sources']:assert sha(pathlib.Path(item['path']))==item['sha256']==frozen['source_hashes'][item['manifest_key']]
for item in pins['candidate_context']['files']:assert sha(pathlib.Path(item['path']))==item['sha256']
# Scope lexical guards supplement, never replace, independent human/source review.
fixture_text='\n'.join(path.read_text() for path in HERE.glob('*.js'))
assert not re.search(r'new\s+(?:WorkerLoader|WebSocket|RpcTarget)\b|\.waitUntil\(|env\.LOADER|env\.STATELESS',fixture_text)
assert "result.traceEntered=true" in source and source.index('await t.init()')<source.index('result.traceEntered=true')
for old in ['streams.json','rpc.json']:
 assert not set(ids)&{r['id'] for r in json.loads((HERE.parents[1]/'cases'/old).read_text())}
for path in HERE.parent.glob('*/manifest.json'):
 if path.parent!=HERE:assert not set(ids)&{r['id'] for r in json.loads(path.read_text())}
files={path.name:sha(path) for path in sorted(HERE.iterdir()) if path.is_file() and path.name not in ['static-evidence.json','inventory.json','review.json','review-request.json']}
counts={'authored':26,'implemented':26,'reviewed':0,'executable_with_qualified_external_supervisor':26,'currently_authorized_runtime':0,'run':0,'passed':0}
record={'status':'PASS','meaning':'Static syntax/schema/hash checks only, no runtime cases or no-network adapter tests executed','checks':checks,'files_sha256':files,'case_bodies_sha256':case_hashes,'direct_frozen_source_files_verified':len(pins['sources']),'counts':counts,'runtime_launched':False,'adapter_tests_executed':False}
(HERE/'static-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
(HERE/'inventory.json').write_text(json.dumps({**counts,'status':'NOT_RUN','manifest_sha256':sha(HERE/'manifest.json'),'static_evidence_sha256':sha(HERE/'static-evidence.json')},indent=2)+'\n')
print(json.dumps({'static_syntax_schema_hash':'PASS','authored':26,'runtime_executed':0,'runtime_passed':0,'adapter_tests_executed':False}))
