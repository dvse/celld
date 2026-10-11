#!/usr/bin/env python3
"""Static-only checks. Never imports cloudflare:workers or runs any case."""
import ast,collections,hashlib,json,pathlib,re,subprocess
HERE=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((HERE/'manifest.json').read_text());ids=[r['id'] for r in rows]
assert len(ids)==18 and len(set(ids))==18
source=(HERE/'cases.js').read_text();body_ids=re.findall(r'async (Q\d{3})\(s\)',source);assert ids==body_ids
for row in rows:
 assert all(row.get(k) for k in ['intent','title','failure_hypothesis','preconditions','trace','stress','oracle','cleanup','layer','profile','implementation'])
 assert 0<row['stress']['rpc_attempts']<=16
 assert row['stress']['payload_bytes']<=33554432 and row['wall_seconds_max']<=30
 assert row['run'] is False and row['passed'] is False
 if row['id'] in ['Q016','Q017','Q018']:assert row['promotion']=='BLOCKED_UNSUPPORTED_PROTECTION'
# Syntax-check only. The template contents are independently parsed, never evaluated.
checks=[]
for path in sorted(HERE.glob('*.js')):
 p=subprocess.run(['node','--input-type=module','--check'],input=path.read_text(),text=True,capture_output=True,timeout=5);assert p.returncode==0,(path.name,p.stderr);checks.append(path.name)
for name,text in re.findall(r'export const (\w+) = `([\s\S]*?)`;', (HERE/'workers.js').read_text()):
 p=subprocess.run(['node','--input-type=module','--check'],input=text,text=True,capture_output=True,timeout=5);assert p.returncode==0,(name,p.stderr);checks.append('Loader source:'+name)
 assert len(text.encode())<8192
for path in HERE.glob('*.py'):ast.parse(path.read_text());checks.append(path.name)
assert 'while(' not in source and 'while (' not in source
pins=json.loads((HERE/'source-pins.json').read_text());manifest_path=pathlib.Path(pins['runtime_manifest']);assert sha(manifest_path)==pins['runtime_manifest_sha256'];frozen=json.loads(manifest_path.read_text())
for item in pins['sources']:assert sha(pathlib.Path(item['path']))==item['sha256']==frozen['source_hashes'][item['manifest_key']]
assert sha(pathlib.Path(pins['os_context']['path']))==pins['os_context']['sha256']
for r in rows:
 body=source[source.index(' async '+r['id']+'(s)'):];body=body[:body.index('\n async Q') if '\n async Q' in body else body.index('\n};')]
 r['implementation_sha256']=hashlib.sha256(body.encode()).hexdigest()
assert len({r['implementation_sha256'] for r in rows})==18
files={p.name:sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in {'static-evidence.json','inventory.json','review.json','final-evidence.json'}}
evidence={'status':'PASS','meaning':'Static schema, syntax and source pins only; zero runtime cases executed','checks':checks,'files_sha256':files,'case_bodies_sha256':{r['id']:r['implementation_sha256'] for r in rows},'frozen_source_files_verified':len(pins['sources']),'counts':{'authored':18,'reviewed':0,'implemented':18,'executable_with_qualified_adapter':15,'currently_authorized_runtime':0,'run':0,'passed':0},'classifications':dict(collections.Counter(r['classification'] for r in rows))}
(HERE/'static-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n');(HERE/'inventory.json').write_text(json.dumps({**evidence['counts'],'status':'NOT_RUN','unsupported_protection_blocked':['Q016','Q017','Q018'],'runtime_passes':0,'static_evidence_sha256':sha(HERE/'static-evidence.json'),'manifest_sha256':sha(HERE/'manifest.json')},indent=2)+'\n')
print(json.dumps({'static':'PASS','authored':18,'frozen_sources':len(pins['sources']),'run':0,'passed':0}))
