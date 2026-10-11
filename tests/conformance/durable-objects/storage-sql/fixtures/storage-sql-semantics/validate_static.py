#!/usr/bin/env python3
import hashlib,json,pathlib,re,subprocess
H=pathlib.Path(__file__).resolve().parent
m=json.loads((H/'manifest.json').read_text()); pins=json.loads((H/'source-pins.json').read_text()); root=pathlib.Path(pins['source_root'])
for p,v in pins['files'].items(): assert hashlib.sha256((root/p).read_bytes()).hexdigest()==v,p
s=(H/'cases.js').read_text(); funcs=re.findall(r'^export (?:async )?function (D\d+)\(',s,re.M)
assert funcs==[c['id'] for c in m['cases']] and len(funcs)==20 and len(set(funcs))==20
for c in m['cases']:
 assert c['literal_assertion_call_sites']>=2 and c['runtime_status']=='NOT_RUN' and c['actual_runs']==0
 assert not c['independently_reviewed']
 for r in c['source_refs']:
  assert r['path'] in pins['files']; assert 1<=r['line_start']<=r['line_end']<=len((root/r['path']).read_text().splitlines())
for f in ('cases.js','fixture.js'): subprocess.run(['node','--input-type=module','--check'],input=(H/f).read_bytes(),check=True)
assert json.loads((H/'wrangler.jsonc').read_text())['main']=='fixture.js'
r=dict(kind='STATIC_ONLY',source_pins_verified=3,case_functions=20,literal_assertion_call_sites=sum(c['literal_assertion_call_sites'] for c in m['cases']),syntax_files=2,runtime_executions=0,independent_review='pending')
(H/'static-report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
