#!/usr/bin/env python3
"""Static parsing and inventory only. Never executes the Workers fixture or sends traffic."""
import hashlib,json,pathlib,re,subprocess
HERE=pathlib.Path(__file__).resolve().parent
PROJECT=pathlib.Path('/workspace/shared/celld-os-project')
FILES=('fixture.js','cases.js','entry.js','workers.js','manifest.json','source-pins.json','wrangler.jsonc','run.py','README.md','author_manifest.py','test_preflight.py','validate.py')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 rows=json.loads((HERE/'manifest.json').read_text());ids=[r['id'] for r in rows]
 assert ids==[f'B{i:03d}' for i in range(1,25)],'literal manifest inventory'
 required={'id','intent','preconditions','ordered_trace','stress_dimension','safety_oracle','liveness_oracle','cleanup','source_contracts','bounds','implementation','classification','layer','qualification_gate','identity_assumption'}
 assert all(required<=row.keys() for row in rows)
 assert len({row['intent'] for row in rows})==24
 for row in rows:
  assert len(row['ordered_trace'])>=4 and len(row['safety_oracle'])>=2 and len(row['cleanup'])>=4
  assert row['classification']=='bounded-concurrent-stress' and row['layer']=='real-process-RPC'
  assert row['bounds']['case_wall_seconds']<=30 and row['bounds']['logical_payload_bytes_max']<=2097152
  assert row['bounds']['read_operations_per_stream_max']==65536
 text=(HERE/'cases.js').read_text();bodies=re.findall(r'^  async (B\d{3})\(s\)\{\n(.*?)(?=\n  \},|\n  \}\n)',text,re.M|re.S)
 assert [i for i,_ in bodies]==ids,'manifest and assertion body IDs differ'
 shapes={}
 for id,body in bodies:
  shape=re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"",'STRING',body);shape=re.sub(r'\s+','',shape)
  assert shape not in shapes,('label-only duplicate',id,shapes.get(shape));shapes[shape]=id
  assert 'await ' in body and ('eq(' in body or 'ok(' in body)
 for name in ('fixture.js','cases.js','entry.js','workers.js'):
  value=(HERE/name).read_text();assert '__celld$' not in value
  subprocess.run(['node','--input-type=module','--check'],input=value,text=True,capture_output=True,check=True)
 modules=re.findall(r'export const (?:CODE|ZLIB_CODE) = `\n(.*?)\n`;', (HERE/'workers.js').read_text(),re.S)
 assert len(modules)==2
 for source in modules:subprocess.run(['node','--input-type=module','--check'],input=source,text=True,capture_output=True,check=True)
 for name in ('run.py','author_manifest.py','validate.py','test_preflight.py'):compile((HERE/name).read_text(),name,'exec')
 profile=json.loads((HERE/'wrangler.jsonc').read_text());assert profile['compatibility_date']=='2026-09-04';assert profile['compatibility_flags']==['rpc_params_dup_stubs','nodejs_compat']
 pins=json.loads((HERE/'source-pins.json').read_text());assert pins['runtime_sha256']=='62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
 for name,pin in pins['sources'].items():assert sha(PROJECT/pin['path'])==pin['sha256'],('source changed',name,pin['path'])
 assert pins['sources']['native-transport']['sha256']=='9d31b01bd4d1a6b136cfbc02bcb26a47deba29f27066009fc3f3b9c6d8d9c407'
 assert all(set(x['key'] for x in row['source_contracts'])<=pins['sources'].keys() for row in rows)
 result={'status':'NOT_RUN','authored':24,'implemented_assertion_traces':24,'classification':'bounded-concurrent-stress','independently_reviewed':0,'executable_implementations_with_request_adapter':24,'qualified_deployed_adapter':False,'explicit_execution_blocked_ids':[f'B{i:03d}' for i in range(17,25)],'run':0,'passed':0,'promotion_candidates':16,'pinned_native_characterization_candidates':8,'case_ids':ids,'files_sha256':{name:sha(HERE/name) for name in FILES},'binary_sha256':pins['runtime_sha256'],'frozen_harness_sha256':pins['sources']['native-transport']['sha256'],'checks':['literal manifest registry','quote-normalized body uniqueness','four fixture modules syntax','two embedded loaded-worker module syntaxes','Python compilation','compatibility profile','frozen source hashes'],'limitations':['No Workers module executed; no runtime/guest launched; no network request made.','Static checks do not qualify semantic distinctness, SUT passes or enforced resource bounds.','B017-B024 cannot execute through this adapter pending explicit owner overlap/authorization review; no separately restricted lifetime scenario may be rerouted here.','Independent review counters must be taken from matching review artifacts, not inferred from this static inventory.']}
 (HERE/'inventory.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':print(json.dumps(main(),indent=2))
