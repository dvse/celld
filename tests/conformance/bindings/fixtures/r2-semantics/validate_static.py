#!/usr/bin/env python3
import hashlib,json,pathlib,re,subprocess
H=pathlib.Path(__file__).resolve().parent
m=json.loads((H/'manifest.json').read_text());p=json.loads((H/'source-pins.json').read_text());b=pathlib.Path(p['source_root'])
for name,digest in p['files'].items():assert hashlib.sha256((b/name).read_bytes()).hexdigest()==digest,name
source=(H/'cases.js').read_text();ids=re.findall(r'^export async function (I\d+)\(',source,re.M)
assert ids==[c['id'] for c in m['cases']] and len(ids)==len(set(ids))==20
for c in m['cases']:
 assert c['literal_assertion_call_sites']>=2 and c['runtime_status']=='NOT_RUN' and c['actual_runs']==0 and c['runtime_passes']==0
 assert not c['independently_reviewed'] and c['trace'] and c['distinctness'] and c['oracle']
 for ref in c['source_refs']:
  assert ref['path'] in p['files']
  assert 1<=ref['line_start']<=ref['line_end']<=len((b/ref['path']).read_text().splitlines()),ref
for name in ['cases.js','fixture.js']:subprocess.run(['node','--input-type=module','--check'],input=(H/name).read_bytes(),check=True)
conf=json.loads((H/'wrangler.jsonc').read_text());assert conf['main']=='fixture.js' and len({x['bucket_name'] for x in conf['r2_buckets']})==2
out=dict(kind='STATIC_ONLY',case_functions=20,source_pins_verified=len(p['files']),javascript_syntax_files=2,literal_assertion_call_sites=sum(c['literal_assertion_call_sites'] for c in m['cases']),runtime_executions=0,independent_review='pending')
(H/'static-report.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
