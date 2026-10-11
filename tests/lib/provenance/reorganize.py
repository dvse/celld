#!/usr/bin/env python3
"""One-time, lossless migration recorded for audit; do not rerun on a migrated tree."""
import collections,hashlib,json,os,re,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];T=ROOT/'tests';P=T/'lib/provenance'
def read(p):return json.loads(p.read_text())
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
old=read(T/'MANIFEST.json');imports=read(T/'lib/SOURCES.json');moves={}
# Capture design intent/oracles before relocating their unchanged manifests.
designs={};counts=read(T/'conformance/corpus/COUNTS.json')
for g in counts['groups']:
 w=g['wave'];folder=T/('logic/unit/'+w if w.endswith('-logic') else 'conformance/corpus/'+('base/cases' if w=='base' else w))
 for f in sorted(folder.glob('*.json')):
  d=read(f);rows=d if isinstance(d,list) else d.get('cases',[]) if isinstance(d,dict) else []
  for item in rows:
   if isinstance(item,dict) and item.get('id') in g['case_ids']:designs[(w,item['id'])]=item
assert len(designs)==575,len(designs)
def move(src,dst):
 a=T/src;b=T/dst;assert a.exists() or a.is_symlink(),a;assert not b.exists(),b
 if a.is_dir() and not a.is_symlink():
  for f in a.rglob('*'):
   if f.is_file() or f.is_symlink():moves[str(f.relative_to(ROOT))]=str((b/f.relative_to(a)).relative_to(ROOT))
 else:moves[str(a.relative_to(ROOT))]=str(b.relative_to(ROOT))
 # Include directory paths for fixture references.
 moves[str(a.relative_to(ROOT))]=str(b.relative_to(ROOT));b.parent.mkdir(parents=True,exist_ok=True);a.rename(b)
ex={
 'hello':('fetch-and-http','request-echo'), 'body':('fetch-and-http','json-body-counter'),
 'counter':('durable-objects/storage-kv','fetch-counter'),'async':('durable-objects/lifecycle','timer-before-storage'),
 'rpc':('rpc','method-counter'),'webapi':('web-platform','url-encoding-headers'),
 'alarm':('durable-objects/alarms','scheduled-counter'),'cron':('bindings','scheduled-events'),
 'container':('bindings','container-binding'),'d1':('bindings','d1-database'),'dynamic-worker-tails':('dynamic-workers-and-tails','tail-events'),
 'facets':('durable-objects/facets','facet-counter'),'kv':('bindings','kv-namespace'),
 'opencode':('bindings','coding-model-client'),'pi':('bindings','agent-model-client'),
 'python':('languages','python-worker'),'queues':('bindings','queue-consumer'),'r2':('bindings','r2-bucket'),
 'router':('rpc','service-router'),'sandbox':('bindings','container-sandbox'),'static-assets':('bindings','static-assets'),
 'vectordb':('bindings','vector-database'),'wasm':('languages','wasm-worker'),'workflow':('bindings','workflow-execution'),
 'wsclient':('durable-objects/websockets','outbound-client'),'wsecho':('durable-objects/websockets','echo-server')}
hy={
 'actor-io':('durable-objects/lifecycle','actor-io'), 'bindings':('rpc','bound-context'),
 'callback-continuation':('rpc','callback-continuation'), 'context-ownership':('durable-objects/lifecycle','context-ownership'),
 'core-fidelity':('durable-objects/facets','binding-fidelity'), 'cross-cell-continuation':('rpc','cross-cell-continuation'),
 'do-environment':('durable-objects/placement-and-routing','environment-selection'), 'do-property':('rpc','object-properties'),
 'dup-lifetime':('rpc','duplicate-lifetime'),'event-limits':('limits-and-errors','event-limits'),
 'facet-clone':('durable-objects/facets','clone-barrier'),'island-lockdown':('dynamic-workers-and-tails','module-lockdown'),
 'mailbox-ownership':('durable-objects/lifecycle','mailbox-ownership'),'persistent-dup':('durable-objects/persistent-stubs','duplicate-restore'),
 'placement':('durable-objects/placement-and-routing','process-placement'), 'restore-disposer':('durable-objects/persistent-stubs','restore-disposal'),
 'rpc-dispose':('rpc','handle-disposal'),'rpc-errors':('rpc','error-propagation'),'rpc-surface':('rpc','receiver-visibility'),
 'self-forward':('rpc','self-forwarding'),'stateless-continuation':('rpc','stateless-continuation'),
 'turn-queue-facet':('durable-objects/facets','turn-queue'),'webidl-accessors':('web-platform','abort-accessors'),
 'ws-relay':('durable-objects/websockets','frame-relay'),'ws-session-loop':('durable-objects/websockets','session-loop')}
for origin,listing in [('examples',ex),('hyperbob',hy)]:
 for name,(area,label) in listing.items():move('conformance/'+origin+'/'+name,'conformance/'+area+'/fixtures/'+label)
 # Preserve overview prose as provenance, not a test category.
 src=T/'conformance'/origin
 if (src/'README.md').exists():move('conformance/'+origin+'/README.md','lib/provenance/'+origin+'-overview.source.md')
 if src.exists():move('conformance/'+origin,'artifacts/layout-before-behaviour/'+origin+'-empty')
wave_locations={
 'base':'rpc/fixtures/object-capabilities',
 'active-websocket-stress':'durable-objects/websockets/fixtures/event-traces',
 'alarm-event-stress':'durable-objects/alarms/fixtures/recovery-traces',
 'bounded-load':'limits-and-errors/fixtures/admission-and-progress',
 'bounded-resource':'limits-and-errors/fixtures/invocation-quotas',
 'capability-order':'rpc/fixtures/ordering-and-lifetime',
 'deployment-recovery':'durable-objects/lifecycle/fixtures/deployment-generations',
 'do-visibility-regression':'rpc/fixtures/accessor-visibility',
 'durable-recovery-stress':'durable-objects/storage-kv/fixtures/durable-recovery',
 'fetch-redirect-stress':'fetch-and-http/fixtures/redirect-chains',
 'http-stream-stress':'fetch-and-http/fixtures/body-streaming',
 'loader-props':'dynamic-workers-and-tails/fixtures/loading-and-environment',
 'module-graph-stress':'dynamic-workers-and-tails/fixtures/module-graphs',
 'native-transform-stress':'fetch-and-http/fixtures/transform-streams',
 'rpc-codec':'rpc/fixtures/value-codec',
 'sqlite-concurrency':'durable-objects/storage-sql/fixtures/concurrent-transactions'}
logic_locations={'output-gate-logic':'output-gates','routing-acquisition-logic':'lease-acquisition','pressure-recovery-logic':'pressure','log-recovery-logic':'log-recovery','wake-recovery-logic':'wake-recovery'}
for w,dst in wave_locations.items():move('conformance/corpus/'+w,'conformance/'+dst)
for w,area in logic_locations.items():move('logic/unit/'+w,'logic/'+area+'/fixtures/decision-cases')
move('conformance/corpus/revisions/r027-v2','durable-revision-placeholder')
move('durable-revision-placeholder','conformance/durable-objects/persistent-stubs/fixtures/transient-storage-rejection')
move('conformance/corpus/runners','lib/qualification')
for f in sorted((T/'conformance/corpus').iterdir()):
 if f.is_symlink() or f.is_dir():move(str(f.relative_to(T)),'artifacts/layout-before-behaviour/'+f.name)
 else:move(str(f.relative_to(T)),'lib/provenance/'+f.name)
move('conformance/corpus','artifacts/layout-before-behaviour/corpus-empty')
move('logic/unit','artifacts/layout-before-behaviour/logic-unit-empty')
move('conformance/workerd-ported/globals','conformance/web-platform/fixtures/global-contracts')
move('conformance/workerd-ported/actor-kv','conformance/durable-objects/storage-kv/fixtures/operation-contracts')
move('conformance/workerd-ported/durable-object','conformance/durable-objects/storage-kv/fixtures/object-contracts')
for f in sorted((T/'conformance/workerd-ported/upstream').iterdir()):
 area='web-platform' if f.name.startswith('global-') else 'durable-objects/placement-and-routing' if f.name.startswith('actor-stub') else 'durable-objects/storage-kv'
 dest='lib/provenance/workerd-LICENSE' if f.name=='LICENSE' else 'conformance/'+area+'/fixtures/reference-contracts/'+f.name
 move(str(f.relative_to(T)),dest)
for f in (T/'conformance/workerd-ported').glob('*.md'):move(str(f.relative_to(T)),'lib/provenance/workerd-'+f.name)
move('conformance/workerd-ported','artifacts/layout-before-behaviour/workerd-empty')
move('conformance/wpt/upstream-harness','lib/web-platform-harness')
for f in sorted((T/'conformance/wpt').glob('portable-*')):move(str(f.relative_to(T)),'conformance/web-platform/fixtures/'+f.name[9:])
move('conformance/wpt/selected','conformance/web-platform/fixtures/standard-reference')
for f in (T/'conformance/wpt').glob('*.md'):move(str(f.relative_to(T)),'lib/provenance/wpt-'+f.name)
move('conformance/wpt','artifacts/layout-before-behaviour/wpt-empty')
move('unit/input_gate.rs','unit/input-gates/input_gate.rs');move('unit/store_contract.py','unit/store/store_contract.py');move('unit/celld-tests.json','lib/native-filters.json')
move('faults/fleet.py','lib/fleet.py');move('faults/fixture','faults/process-failure/fixtures/ledger')
# Map original source paths by longest directory prefix, resolving intermediate moves.
def relocated(path):
 for _ in range(4):
  match=next((k for k in sorted(moves,key=len,reverse=True) if path==k or path.startswith(k+'/')),None)
  if match is None:break
  path=moves[match]+path[len(match):]
 return path
for f in imports['files']:f['path']=relocated(f['path'])
# Collapse identical imported assertion copies to a single physical source with
# compatibility symlinks. No assertion body is rewritten or discarded.
by_hash=collections.defaultdict(list)
for f in imports['files']:by_hash[f['sha256']].append(f)
dedup=[]
for digest,files in by_hash.items():
 paths=sorted({f['path'] for f in files})
 if len(paths)<2:continue
 canonical=ROOT/paths[0]
 for name in paths[1:]:
  f=ROOT/name
  if f.is_symlink():continue
  saved=T/'artifacts/layout-before-behaviour/identical-imports'/name
  saved.parent.mkdir(parents=True,exist_ok=True);f.rename(saved);f.symlink_to(os.path.relpath(canonical,f.parent))
 dedup.append({'sha256':digest,'canonical':paths[0],'paths':paths,'origins':sorted({f['origin'] for f in files})})
write(T/'lib/SOURCES.json',imports)

def slug(s):
 s=re.sub(r'([a-z])([A-Z])',r'\1-\2',s).lower();s=re.sub('[^a-z0-9]+','-',s).strip('-');return s[:100].rstrip('-')
def corpus_area(w,i,record):
 if w in logic_locations:return logic_locations[w]
 if w=='base':
  if i.startswith('S'):return 'fetch-and-http'
  if i=='R027':return 'durable-objects/persistent-stubs'
  return 'rpc'
 if w=='loader-props':
  if 24<=int(i[1:])<=30:return 'durable-objects/facets'
  if i=='L019':return 'rpc'
  return 'dynamic-workers-and-tails'
 if w=='bounded-load':return 'fetch-and-http' if 9<=int(i[1:])<=16 else 'rpc'
 return wave_locations[w].split('/fixtures/')[0]
def area_for(c):
 id=c['id'];layer=c['layer']
 if c.get('corpus_wave'):return corpus_area(c['corpus_wave'],c['corpus_id'],designs[(c['corpus_wave'],c['corpus_id'])])
 if id.startswith('examples/'):return ex[id.split('/')[1]][0]
 if id.startswith('hyperbob/'):return hy[id.split('/')[1]][0]
 if id.startswith(('workerd/globals/','wpt/')):return 'web-platform'
 if id.startswith('workerd/durable-object/'):
  return {'stub':'durable-objects/placement-and-routing','sql':'durable-objects/storage-sql'}.get(id.split('/')[-1],'durable-objects/storage-kv')
 if layer=='unit':
  if 'input-gate/' in id:return 'input-gates'
  if 'ltx-' in id:return 'ltx'
  if 's3-store' in id:return 'store'
  name=c['test_filter'];stem=name.split('::')[0]
  return {'capability':'rpc','cell_runtime':'object-identity','deploy':'object-identity','generation':'object-identity','js':'event-ownership','peer_auth':'rpc','pool':'event-ownership','rpc_params_compat_tests':'rpc'}[stem]
 if layer=='logic':return id.split('/')[1]
 if layer=='faults':return 'lease-fencing' if id.endswith('freeze-owner') else 'store-outages' if 'store-' in id else 'process-failure'
 raise ValueError(c)
title_overrides={
 'examples/hello':'Echo HTTP request URL','examples/body':'Accumulate JSON request bodies in object storage',
 'examples/counter':'Persist a counter across named-object fetches','examples/async':'Resume a timer before reading and writing object storage',
 'examples/rpc':'Increment and read object state through RPC methods','examples/webapi':'URL, UTF-8, base64 and header observations',
 'workerd/durable-object/kv':'List stored primitive and object values by key prefix',
 'workerd/durable-object/rollback':'Roll back a failed key-value transaction',
 'workerd/durable-object/sql':'Bind SQL parameters and read inserted rows',
 'workerd/durable-object/stub':'Object IDs round-trip and preserve RPC receiver and fetch dispatch',
 'workerd/durable-object/original-kv-operations':'Key-value, alarm, transaction and sync operations are callable',
 'wpt/full-upstream-harness':'Complete web-platform harness dependency coverage',
 'unit/s3-store-contract':'Conditional writes, ranges, pagination and retained deletion',
 'unit/ltx-upstream-internal-suite':'LTX internal upstream assertion coverage',
 'logic/specification/upstream-tla':'Coordination protocol model coverage'}
case_map={};placed=[]
for original in old['cases']:
 if original['layer']=='regressions':continue
 c=dict(original);legacy=c.pop('id');area=area_for(original);title=title_overrides.get(legacy)
 contract=None
 if c.get('corpus_wave'):
  contract=designs[(c['corpus_wave'],c['corpus_id'])];title=contract['intent']
 if not title:
  title=c.get('test_filter',legacy.split('/')[-1]).split('::')[-1]
  if c.get('mutation'):title='Reject compiled protocol with '+c['mutation']
  title=re.sub(r'([a-z])([A-Z])',r'\1 \2',title).replace('_',' ').replace('-',' ')
 new_id=c['layer']+'/'+area+'/'+slug(title)
 assert new_id not in {x['id'] for x in placed},new_id
 c['source']=relocated(c['source'])
 if c.get('fixture'):c['fixture']=relocated(c['fixture'])
 if c['source_sha256']:assert hashlib.sha256((ROOT/c['source']).read_bytes()).hexdigest()==c['source_sha256'],c['source']
 origins=[{'source':c.pop('source_origin'),'legacy_id':legacy}]
 for f in imports['files']:
  if f['path']==c['source'] or f['sha256']==c['source_sha256']:
   if f['origin'] not in [x['source'] for x in origins]:origins.append({'source':f['origin'],'sha256':f['sha256']})
 descriptor={'id':new_id,'layer':c.pop('layer'),'behaviour':area,'title':title,'origins':origins,'legacy_ids':[legacy]}
 descriptor.update(c)
 if contract:
  descriptor['contract']={k:v for k,v in contract.items() if k in ['intent','oracle','trace','preconditions','cleanup','source_contracts','implementation','distinctness']}
 if c.get('corpus_id'):descriptor['selector']=c['corpus_id']
 if legacy.startswith('workerd/globals/'):
  descriptor['origins'][0]['source']='workerd@19b1657bd/src/workerd/api/tests/global-scope-test.js#'+legacy.split('/')[-1]
 path=T/descriptor['layer']/area/(slug(title)+'.case.json')
 write(path,descriptor);case_map[legacy]={'id':new_id,'header':str(path.relative_to(ROOT))};placed.append(descriptor)
excluded=[]
for e in old['excluded_designs']:
 w=e['wave'];i=e['id'];r=designs[(w,i)];area=corpus_area(w,i,r);layer=e['layer']
 row={'id':layer+'/'+area+'/'+slug(r['intent']),'layer':layer,'behaviour':area,'title':r['intent'],'origins':[{'source':e['source_origin'],'legacy_id':w+'/'+i}],'corpus_wave':w,'corpus_id':i,'runnable':False,'reason':e['reason'],'contract':r}
 path=T/layer/area/(slug(r['intent'])+'.design.json');assert not path.exists(),path;write(path,row);excluded.append(str(path.relative_to(ROOT)))
write(P/'PATH-MIGRATION.json',{'baseline_commit':'35051ca','paths':{k:relocated(k) for k in moves},'case_aliases':case_map})
write(P/'IDENTICAL-SOURCES.json',dedup)
# Existing public example paths remain useful, outside the behaviour test tree.
for oldroot,listing in [('examples',ex),('tests-hyperbob',hy)]:
 p=ROOT/oldroot;saved=T/'artifacts/layout-before-behaviour'/('root-'+oldroot)
 if p.exists() or p.is_symlink():p.rename(saved)
 p.mkdir()
 for name,(area,label) in listing.items():(p/name).symlink_to(os.path.relpath(T/'conformance'/area/'fixtures'/label,p))
 readme=P/('examples-overview.source.md' if oldroot=='examples' else 'hyperbob-overview.source.md')
 if readme.exists():(p/'README.md').symlink_to(os.path.relpath(readme,p))
print('Relocated',len(moves),'paths;',len(placed),'case headers;',len(excluded),'design headers;',len(dedup),'identical source groups')
