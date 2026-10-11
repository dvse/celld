#!/usr/bin/env python3
"""Read-only metadata/hash/parser checks; never execute the fixture or SUT."""
import argparse,ast,hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
DEFAULT_ROOT=Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--source-root',type=Path,default=DEFAULT_ROOT);args=parser.parse_args()
 checks=[]
 for path in sorted(HERE.glob('*.json')):
  if path.name=='static-validation.json':continue
  json.loads(path.read_text());checks.append({'check':'json-parse','file':path.name,'status':'PASS'})
 for path in sorted(HERE.glob('*.py')):
  ast.parse(path.read_text(),filename=path.name);checks.append({'check':'python-ast-only','file':path.name,'status':'PASS'})
 manifest=json.loads((HERE/'manifest.json').read_text());pins=json.loads((HERE/'source-pins.json').read_text())
 expected=['Z'+str(x) for x in range(201,220) if x!=214]
 assert [c['id'] for c in manifest['cases']]==expected
 assert manifest['authored_case_count']==18 and manifest['runtime_status']=='UNRUN' and manifest['runtime_executions']==0
 assert manifest['retired_noncounted_ids']==['Z214'] and not manifest['actual_os_checkout_available']
 body=(HERE/'cases.js').read_text();assert re.findall(r'^  async (Z\d{3})\(s, t\) \{',body,re.M)==expected
 total=0
 for c in manifest['cases']:
  match=re.search(r'^  async '+c['id']+r'\(s, t\) \{\n(.*?)^  \},',body,re.M|re.S);assert match
  assertions=[x.strip() for x in match.group(1).splitlines() if re.search(r'\bt\.(same|deep|ok)\(',x)]
  assert assertions==c['fixed_runtime_assertions'] and len(assertions)==c['assertion_count'] and len(assertions)>0
  total+=len(assertions)
  assert c['runtime_status']=='UNRUN' and c['actual_runtime_executions']==0 and c['independently_reviewed'] is False
  assert c['trace'] and c['oracle'] and c['distinctness'] and c['os_relevance']['label']
  for ref in c['runtime_source_refs']:
   assert ref['path'] in {p['path'] for p in pins['runtime_sources']}
   assert 1<=ref['line_start']<=ref['line_end']<=len((args.source_root/ref['path']).read_text().splitlines())
 assert len({c['mechanism'] for c in manifest['cases']})==18
 checks.append({'check':'case-manifest-fixed-assertion-correspondence','cases':18,'assertions':total,'status':'PASS'})
 cfg=json.loads((HERE/'wrangler.json').read_text())
 assert cfg['main']=='fixture.js' and cfg['compatibility_date']=='2026-09-04' and cfg['compatibility_flags']==['js_rpc']
 assert cfg['migrations']==[{'tag':'v1','new_sqlite_classes':['Root']}]
 assert cfg['worker_loaders']==[{'binding':'LOADER'}]
 assert cfg['durable_objects']=={'bindings':[{'name':'ROOT','class_name':'Root'}]}
 schedule=json.loads((HERE/'schedule.json').read_text())
 assert [x['id'] for x in schedule['requests']]==expected and schedule['max_parallel_case_requests']==1
 assert schedule['suite_outer_deadline_seconds']==420 and not schedule['launches_runtime']
 assert all(x['outer_deadline_seconds']==12 and x['process_deadline_seconds']==20 for x in schedule['requests'])
 checks.append({'check':'config-and-finite-schedule','status':'PASS'})
 wrapper=(HERE/'sources.js').read_text();source=json.loads(wrapper.split('export const LOADED_SOURCE = ',1)[1].rstrip().removesuffix(';'))
 assert source==(HERE/'facets.js').read_text() and len(source.encode())<=16384
 checks.append({'check':'exact-loaded-source-mirror','sha256':hashlib.sha256(source.encode()).hexdigest(),'status':'PASS'})
 for collection,root in [('runtime_sources',args.source_root),('baseline_evidence',args.source_root),('campaign_evidence',HERE.parent),('fixture_artifacts',HERE)]:
  for pin in pins[collection]:assert hashlib.sha256((root/pin['path']).read_bytes()).hexdigest()==pin['sha256'],str(root/pin['path'])
  checks.append({'check':'sha256-'+collection,'files':len(pins[collection]),'status':'PASS'})
 for path in sorted(HERE.glob('*.js')):
  result=subprocess.run(['node','--input-type=module','--check'],input=path.read_bytes(),capture_output=True,timeout=5,check=False)
  assert result.returncode==0,result.stderr.decode()
  checks.append({'check':'node-syntax-only','file':path.name,'status':'PASS'})
 forbidden=[r'\bRpcTarget\b',r'\brestore\b',r'\.abort\s*\(',r'WebSocket',r'__facet_',r'__cell']
 runtime='\n'.join((HERE/p).read_text() for p in ['facets.js','fixture.js','cases.js'])
 assert not any(re.search(p,runtime) for p in forbidden)
 print(json.dumps({'status':'STATIC_ONLY','runtime_status':'UNRUN','runtime_executions':0,'authored_cases':18,'fixed_assertions':total,'independent_review_claimed':False,'checks':checks},indent=2))
if __name__=='__main__':main()
