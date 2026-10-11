#!/usr/bin/env python3
"""Finite request-only adapter. Never starts/deploys/builds a runtime or applies faults.
The direct-runtime test-harness supervisor owns and independently verifies process, resource, and teardown evidence.
Missing prerequisites are typed BLOCKED. Fixture success remains BLOCKED until
finalize() accepts the external terminal teardown receipt; no synthetic guard is proof.
"""
import datetime, hashlib, http.client, ipaddress, json, pathlib, re, signal, time, urllib.parse
HERE=pathlib.Path(__file__).resolve().parent
PROFILE='sqlite-concurrency-frozen-v1'
BINARY='62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
FILES=('common.js','cell-cases.js','fixture.js','cases.js','entry.js','wrangler.jsonc','profile.json','manifest.json','source-pins.json','private_driver.py')
CHARACTERIZATIONS={'T014','T021','T029'}
class Blocked(Exception):
 code='BLOCKED_PREREQUISITE'
def need(value,message):
 if not value:raise Blocked(message)
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def pins():return {name:sha(HERE/name) for name in FILES}
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def origin(value):
 u=urllib.parse.urlsplit(value)
 need(u.scheme=='http' and not u.username and not u.password and not u.query and not u.fragment and u.path in ('','/') and u.port==18080,'credential-free private HTTP origin on port 18080 required')
 try:ip=ipaddress.ip_address(u.hostname)
 except ValueError as error:raise Blocked('IP literal required, no DNS') from error
 need(ip.version==4 and (ip.is_loopback or any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))),'public/link-local destinations prohibited')
 return 'http://'+u.netloc

def validate_guard(case_id,guard):
 rows=json.loads((HERE/'manifest.json').read_text());need(case_id in {r['id'] for r in rows},'unknown case')
 for field in ('exclusive_run_slot','owned_disposable_runtime','hard_limits_observed','cleanup_ownership_verified','fresh_roots_verified','ordinary_do_scope_reviewed'):
  need(guard.get(field) is True,'missing supervisor prerequisite: '+field)
 need(isinstance(guard.get('run_id'),str) and re.fullmatch('[a-f0-9]{16}',guard['run_id']),'fresh 16-hex run ID required')
 origin(guard.get('origin',''))
 need(guard.get('binary_sha256')==BINARY,'frozen binary mismatch; visibility candidate is a separate profile')
 source=json.loads((HERE/'source-pins.json').read_text())
 need(sha(source['runtime_manifest'])==source['runtime_manifest_sha256'],'frozen manifest changed')
 for item in source['sources']:need(sha(item['path'])==item['sha256'],'pinned source changed: '+item['path'])
 need(guard.get('implementation_hashes')==pins() and guard.get('reviewed_implementation_hashes')==pins(),'implementation hash or independent review stale')
 need(case_id in guard.get('reviewed_case_ids',[]),'case lacks accepted distinctness/oracle review')
 need(guard.get('profile_sha256')==sha(HERE/'profile.json'),'profile mismatch')
 for field in ('ownership_evidence','limits_evidence','review_evidence','cleanup_plan_evidence'):
  value=guard.get(field,{})
  need(isinstance(value.get('path'),str) and pathlib.Path(value['path']).is_file(),'missing evidence file: '+field)
  need(sha(value['path'])==value.get('sha256'),'evidence file digest mismatch: '+field)
 owner=guard.get('owner',{})
 for field in ('vm_id','boot_id','start_ticks'):need(isinstance(owner.get(field),str) and owner[field],'missing owner '+field)
 need(type(owner.get('runtime_pid')) is int and owner['runtime_pid']>0 and owner.get('executable_sha256')==BINARY,'owned runtime executable witness missing')
 limits=guard.get('limits',{})
 for field,maximum in [('case_wall_seconds',30),('memory_mib',512),('pids',128),('vcpus',1)]:need(type(limits.get(field)) is int and 1<=limits[field]<=maximum,'missing/excessive enforced limit: '+field)
 for field,exact in [('recipient_rpc_max',12),('sql_cursors_max',128),('native_join_pairs_max',4096),('receipt_bytes_max',1048576),('control_requests_max',5)]:need(limits.get(field)==exact,'logical envelope mismatch: '+field)
 roots=guard.get('roots',{});need(set(roots)=={'caller','primary','secondary'},'exact root roles required')
 for role in ('caller','primary','secondary'):
  root=roots.get(role,{})
  need(isinstance(root.get('name'),str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',root['name']),'bounded fresh root name required')
  identity=root.get('identity',{})
  need(identity.get('profile')==PROFILE and all(isinstance(identity.get(f),str) and identity[f] for f in ('root','instance')),'complete root identity required')
 need(len({roots[role]['name'] for role in roots})==3 and len({roots[role]['identity']['root'] for role in roots})==3,'three distinct verified roots required')
 return guard

class PrivateClient:
 def __init__(self,base,deadline):self.base=origin(base);self.deadline=deadline;self.attempts=0;self.sockets=set()
 def request(self,path,body=None):
  need(path in ('/health','/identity','/run'),'unknown fixture route')
  self.attempts+=1;need(self.attempts<=5,'control request bound')
  remaining=self.deadline-time.monotonic();need(remaining>0,'absolute case deadline elapsed')
  parsed=urllib.parse.urlsplit(self.base);conn=http.client.HTTPConnection(parsed.hostname,parsed.port,timeout=min(remaining,28));self.sockets.add(conn)
  try:
   data=None if body is None else json.dumps(body).encode();need(data is None or len(data)<8192,'request bound')
   conn.request('GET' if data is None else 'POST',path,body=data,headers={'Content-Type':'application/json','Connection':'close'})
   response=conn.getresponse();need(response.status==200,'non-200 response; redirects never followed')
   payload=response.read(1048577);need(len(payload)<=1048576,'receipt size bound');return json.loads(payload)
  finally:conn.close();self.sockets.discard(conn)
 def close(self):
  for conn in list(self.sockets):conn.close();self.sockets.discard(conn)

def validate_terminal(value,case_id,guard):
 need(value.get('id')==case_id and value.get('run')==guard['run_id'] and value.get('profile')==PROFILE,'case/run/profile receipt mismatch')
 need(value.get('caller')==guard['roots']['caller']['identity'],'caller identity mismatch')
 need(value.get('status') in ('PASS','FAIL','BLOCKED') and type(value.get('traceEntered')) is bool,'typed terminal result required')
 if not value['traceEntered']:
  if value.get('blocker',{}).get('type')=='BLOCKED_UNCERTAIN_DISPATCH':
   need(value['status']=='BLOCKED' and value.get('phase')=='trace-unknown' and value.get('dispatchAttempted') is True and value.get('traceEntryUnknown') is True,'invalid uncertain dispatch receipt');return
  need(value['status']=='BLOCKED' and value.get('phase')=='precondition' and value.get('blocker',{}).get('type')=='BLOCKED_PREREQUISITE','invalid precondition receipt');return
 need(value['status'] in ('PASS','FAIL') or (value['status']=='BLOCKED' and value.get('blocker',{}).get('type')=='BLOCKED_SCHEDULE'),'entered trace requires semantic result or typed schedule blocker')
 identities={role:guard['roots'][role]['identity'] for role in ('primary','secondary')}
 need(value.get('recipients')==identities,'recipient identities mismatch')
 evidence=value.get('evidence',{});events=evidence.get('events');receipts=evidence.get('receipts')
 need(isinstance(events,list) and isinstance(receipts,list),'missing events or recipient results')
 need(any(e.get('kind')=='trace-enter' and e.get('label')==case_id and e.get('run')==guard['run_id'] and e.get('recipient')==identities['primary'] for e in events),'actual primary recipient trace-entry witness missing')
 if value['status']=='PASS':
  if case_id in {'T001','T002','T003','T004','T005','T006','T007','T008','T009','T010','T027'}:need(any(r.get('cohort',{}).get('queuedBeforeHold') is True and r.get('cohort',{}).get('releaseBeforeContenderEntry') is True for r in receipts if r.get('cohort')),'admitted transaction overlap witness missing')
  need(len(events)<=128,'event bound'); local=[e for r in receipts for e in r.get('localEvents',[])]; need(any(e.get('kind')=='held' for e in events) or any(e.get('label','').startswith('pause-enter:') and e.get('run')==guard['run_id'] and e.get('recipient')==identities['primary'] for e in local),'bounded overlap witness missing')
  need(type(evidence.get('wallMs')) is int and 0<=evidence['wallMs']<=29000,'fixture elapsed bound unverified')
  need(any(r.get('run')==guard['run_id'] and r.get('id')==case_id and r.get('recipient')==identities['primary'] and isinstance(r.get('value'),dict) and r.get('status')=='PASS' and r.get('traceEntered') is True and any(e.get('label')=='body-enter:'+case_id and e.get('requestId')==r.get('requestId') for e in r.get('localEvents',[])) for r in receipts),'assertion-bearing primary result missing')
  for event in events:need(event.get('run')==guard['run_id'] and event.get('recipient') in identities.values() and isinstance(event.get('requestId'),str) and event['requestId'].startswith(guard['run_id']+':'),'uncorrelated event')
  for receipt in receipts:need(receipt.get('run')==guard['run_id'] and receipt.get('recipient') in identities.values() and isinstance(receipt.get('requestId'),str) and receipt['requestId'].startswith(guard['run_id']+':'),'uncorrelated recipient result')
  need(len({r['requestId'] for r in receipts})==len(receipts),'duplicate request receipt')
  classification=next(row['classification'] for row in json.loads((HERE/'manifest.json').read_text()) if row['id']==case_id)
  if classification.startswith('cross-request-'):need(len(receipts)>=2,'independent incoming request receipt missing')
  for event in local:need(event.get('run')==guard['run_id'] and event.get('recipient') in identities.values() and isinstance(event.get('requestId'),str) and event['requestId'].startswith(guard['run_id']+':'),'uncorrelated local continuation witness')
  cleanup=value.get('cleanup',{});need(value.get('phase')=='complete' and cleanup.get('status')=='ok' and cleanup.get('run')==guard['run_id'],'incomplete fixture cleanup')
  need(cleanup.get('pending')==0 and cleanup.get('held')==0,'foreground promises or holds remain')
  remote=cleanup.get('remote',[]);need(len(remote)==2,'both recipients must clean up')
  for role,row in zip(('primary','secondary'),remote):need(row.get('run')==guard['run_id'] and row.get('recipient')==identities[role] and row.get('status')=='ok' and row.get('active')==0 and row.get('cursors')==0 and row.get('timers')==0,'recipient cleanup correlation/completion missing')
  expected='NONPROMOTING_PINNED_CHARACTERIZATION' if case_id in CHARACTERIZATIONS else 'PENDING_EXTERNAL_SUPERVISOR_REVIEW'
  need(value.get('qualification')==expected,'promotion/characterization label mismatch')

def run_case(case_id,guard):
 result={'id':case_id,'status':'BLOCKED','traceEntered':False,'started_utc':now(),'profile':PROFILE,'binary_sha256':BINARY};client=None;armed=False;previous=None
 try:
  result['implementation_hashes']=pins();validate_guard(case_id,guard)
  need(hasattr(signal,'setitimer') and signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'dedicated adapter process with absolute wall timer required')
  result.update(run_id=guard['run_id'],owner=guard['owner'],limits=guard['limits'],roots=guard['roots'],guard_sha256=hashlib.sha256(json.dumps(guard,sort_keys=True).encode()).hexdigest())
  deadline=time.monotonic()+guard['limits']['case_wall_seconds']
  def expired(*_):raise TimeoutError('absolute case deadline; owned supervisor teardown required')
  previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,deadline-time.monotonic());armed=True;client=PrivateClient(guard['origin'],deadline)
  health=client.request('/health');need(health.get('profile')==PROFILE and case_id in health.get('caseIds',[]),'health/profile mismatch')
  for role in ('caller','primary','secondary'):
   target=guard['roots'][role];got=client.request('/identity',{'name':target['name'],'role':'caller' if role=='caller' else 'recipient'});need(got==target['identity'],'live root identity mismatch: '+role)
  payload={'id':case_id,'run':guard['run_id'],'name':guard['roots']['caller']['name'],'primary':guard['roots']['primary']['name'],'secondary':guard['roots']['secondary']['name'],'expectedCaller':guard['roots']['caller']['identity'],'expectedPrimary':guard['roots']['primary']['identity'],'expectedSecondary':guard['roots']['secondary']['identity']}
  result['dispatch_attempted']=True
  receipt=client.request('/run',payload);result['unqualified_fixture_receipt']=receipt;validate_terminal(receipt,case_id,guard);result['fixture_result']=receipt;result.pop('unqualified_fixture_receipt',None);result['traceEntered']=receipt['traceEntered']
  if receipt['status']=='PASS':result.update(semantic_status='PASS',blocker={'type':'BLOCKED_EXTERNAL_TEARDOWN','detail':'Independent terminal process/storage/resource receipt required before counting runtime success.'})
  else:
   result['status']=receipt['status'];result['traceEntryUnknown']=receipt.get('traceEntryUnknown',False)
   if receipt.get('blocker'):result['blocker']=receipt['blocker']
 except Exception as error:
  result['error']=str(error);result['blocker']={'type':'BLOCKED_PREREQUISITE' if not result.get('dispatch_attempted') else 'BLOCKED_UNCERTAIN_DISPATCH','detail':str(error)}
  if result.get('dispatch_attempted'):result['traceEntryUnknown']=True;result['cleanup']={'status':'UNKNOWN','required':'No retry. The direct-runtime test-harness supervisor must terminate/reap only the owned guest/runtime and remove owned storage.'}
 finally:
  if client:client.close()
  if armed:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
  result['finished_utc']=now()
 return result

def finalize(result,teardown):
 """Validate a real supervisor's external receipt. Does not perform teardown."""
 need(result.get('semantic_status')=='PASS' and result.get('traceEntered') is True,'no semantic result to finalize')
 need(teardown.get('run_id')==result.get('run_id') and teardown.get('case_id')==result.get('id') and teardown.get('owner')==result.get('owner'),'terminal supervisor correlation mismatch')
 need(teardown.get('implementation_hashes')==result.get('implementation_hashes'),'terminal implementation hashes mismatch')
 for field in ('process_reaped','owned_storage_removed','hard_bounds_respected','no_unowned_resources_touched'):need(teardown.get(field) is True,'terminal proof missing: '+field)
 observed=teardown.get('observed',{})
 for field,limit in [('peak_memory_mib','memory_mib'),('peak_pids','pids'),('allocated_vcpus','vcpus'),('elapsed_seconds','case_wall_seconds')]:need(type(observed.get(field)) in (int,float) and 0<=observed[field]<=result['limits'][limit],'terminal measured bound missing/exceeded: '+field)
 evidence=teardown.get('evidence',{});need(isinstance(evidence.get('path'),str) and pathlib.Path(evidence['path']).is_file() and sha(evidence['path'])==evidence.get('sha256'),'supervisor terminal evidence file absent/changed')
 result=dict(result);result['status']='PASS';result['external_teardown']=teardown;result.pop('blocker',None);result['promotion_eligible']=result['id'] not in CHARACTERIZATIONS
 return result
