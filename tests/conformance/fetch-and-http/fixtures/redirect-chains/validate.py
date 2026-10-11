"""Parser, manifest and provenance checks only; never imports or executes a fixture/case."""
import ast,hashlib,json,pathlib,re,subprocess
HERE=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((HERE/'manifest.json').read_text());ids=[x['id'] for x in rows]
assert ids==['F%03d'%i for i in range(1,13)]
source=(HERE/'cases.js').read_text();definitions=list(re.finditer(r'export async function (F\d{3})\(t\) \{',source));assert [m[1] for m in definitions]==ids
case_hashes={}
for i,m in enumerate(definitions):
 end=definitions[i+1].start() if i+1<len(definitions) else source.index('export const CASES=')
 case_hashes[m[1]]=hashlib.sha256(source[m.start():end].encode()).hexdigest()
assert len(set(case_hashes.values()))==12
for row in rows:
 assert all(row.get(k) for k in ['intent','failure_hypothesis','preconditions','trace','stress','oracle','cleanup','distinctness','os_call_sites'])
 assert len(row['preconditions'])>=6 and len(row['trace'])>=4
 assert row['status']=='NOT_RUN' and row['run'] is False and row['passed'] is False and row['reviewed'] is False and row['promotion_candidate'] is True
 assert row['stress']['redirect_edges_per_graph_max']==3 and row['stress']['wall_seconds_max']==30
checks=[]
for p in sorted(HERE.glob('*.js'))+sorted(HERE.glob('*.mjs')):
 r=subprocess.run(['node','--check',str(p)],capture_output=True,text=True,timeout=5);assert r.returncode==0,(p.name,r.stderr);checks.append('node-parse:'+p.name)
for p in sorted(HERE.glob('*.py')):ast.parse(p.read_text());checks.append('python-ast:'+p.name)
pins=json.loads((HERE/'source-pins.json').read_text());manifest=pathlib.Path(pins['runtime_manifest']);assert sha(manifest)==pins['runtime_manifest_sha256'];runtime=json.loads(manifest.read_text())
profile=json.loads((HERE/'profile.json').read_text());wrangler=json.loads((HERE/'wrangler.jsonc').read_text())
assert profile['binary_sha256']==pins['binary_sha256']==runtime['binary_sha256']=='8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f'
assert profile['id']=='fetch-redirect-stress-candidate8d27-v1' and wrangler['vars']['PRIVATE_ORIGIN']==profile['fixed_recipient_origin']=='http://192.168.77.1:18080'
for p in pins['sources']:
 assert sha(HERE/p['path'])==p['sha256']
 if p['role']=='candidate-direct':assert p['sha256']==runtime['source_hashes'][p['manifest_key']]
 if p['role']=='upstream-primary-reference':assert p['commit']==pins['upstream_commit']=='9f247e0d5feae1f98ffcee5c9f44a0ded87bb334'
fixture='\n'.join(p.read_text() for p in HERE.glob('*.js'))
assert not re.search(r'new\s+(?:WorkerLoader|WebSocket|RpcTarget)\b|\.waitUntil\(|env\.LOADER|env\.STATELESS',fixture)
assert 'result.traceEntered=true' in source and source.index('await t.init()')<source.index('result.traceEntered=true')
duplicates={}
for rel in ['cases/streams.json','waves/bounded-load/manifest.json','waves/http-stream-stress/manifest.json','waves/native-transform-stress/manifest.json','waves/module-graph-stress/manifest.json']:
 p=HERE.parents[1]/rel;old=json.loads(p.read_text());assert not set(ids)&{x['id'] for x in old};duplicates[rel]=sha(p)
for p in HERE.parent.glob('*/manifest.json'):
 if p.parent!=HERE:
  other=json.loads(p.read_text());assert not set(ids)&{x['id'] for x in other},str(p)
files={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in ['static-evidence.json','inventory.json','review.json','review-request.json','support-checks.json']}
digest=hashlib.sha256(json.dumps(files,sort_keys=True,separators=(',',':')).encode()).hexdigest()
counts={'authored':12,'implemented_assertion_traces':12,'independently_reviewed':0,'correctness_stress_candidates':12,'characterization_candidates':0,'runtime_integration_qualified':0,'actual_sut_runs':0,'actual_passes':0}
record={'status':'PASS','meaning':'Static parser/schema/hash checks only. No SUT, network, deployment, compiler or guest work.','implementation_digest':digest,'checks':checks,'files_sha256':files,'case_bodies_sha256':case_hashes,'duplicate_inventory_sha256':duplicates,'source_files_verified':len(pins['sources']),'counts':counts}
(HERE/'static-evidence.json').write_text(json.dumps(record,indent=2)+'\n')
(HERE/'inventory.json').write_text(json.dumps({**counts,'status':'NOT_RUN','implementation_digest':digest,'manifest_sha256':sha(HERE/'manifest.json'),'static_evidence_sha256':sha(HERE/'static-evidence.json')},indent=2)+'\n')
request={**counts,'status':'READY_FOR_INDEPENDENT_SOURCE_REVIEW','implementation_digest':digest,'artifact_hashes':files,'semantic_review_pending':True,'known_source_hypothesis':'F012 asserts final URL/redirected contract; candidate source appears to retain original metadata, but has not been run.','source_provenance':'source-pins.json','support_checks':'support-checks.json'}
(HERE/'review-request.json').write_text(json.dumps(request,indent=2)+'\n')
print(json.dumps({'static_parse_schema_hash':'PASS',**counts,'implementation_digest':digest}))
