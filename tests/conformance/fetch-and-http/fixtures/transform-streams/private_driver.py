#!/usr/bin/env python3
"""Finite request-only adapter. Never starts/deploys/builds a runtime or applies faults.
The direct-runtime test-harness supervisor owns and independently verifies process, resource, and teardown evidence.
Missing prerequisites are typed BLOCKED. Fixture success remains BLOCKED until
finalize() accepts the external terminal teardown receipt; no synthetic guard is proof.
"""
import datetime, hashlib, http.client, ipaddress, json, pathlib, re, signal, time, urllib.parse
HERE=pathlib.Path(__file__).resolve().parent
PROFILE='native-transform-frozen-v1'
BINARY='62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
FILES=('common.js','context.js','vectors.js','operations.js','fixture.js','entry.js','wrangler.jsonc','profile.json','manifest.json','source-pins.json','private_driver.py')
CHARACTERIZATIONS=set()
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
 for field in ('exclusive_run_slot','owned_disposable_runtime','hard_limits_observed','cleanup_ownership_verified','fresh_roots_verified','ordinary_do_scope_reviewed','same_runtime_placement_verified'):
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
 for field in ('ownership_evidence','limits_evidence','review_evidence','cleanup_plan_evidence','placement_evidence'):
  value=guard.get(field,{})
  need(isinstance(value.get('path'),str) and pathlib.Path(value['path']).is_file(),'missing evidence file: '+field)
  need(sha(value['path'])==value.get('sha256'),'evidence file digest mismatch: '+field)
 owner=guard.get('owner',{})
 for field in ('vm_id','boot_id','start_ticks'):need(isinstance(owner.get(field),str) and owner[field],'missing owner '+field)
 need(type(owner.get('runtime_pid')) is int and owner['runtime_pid']>0 and owner.get('executable_sha256')==BINARY,'owned runtime executable witness missing')
 limits=guard.get('limits',{})
 for field,maximum in [('case_wall_seconds',30),('memory_mib',512),('pids',128),('vcpus',1)]:need(type(limits.get(field)) is int and 1<=limits[field]<=maximum,'missing/excessive enforced limit: '+field)
 for field,exact in [('native_operations_max',4),('operation_output_bytes_max',262144),('total_fixture_bytes_max',4194304),('receipt_bytes_max',1048576),('control_requests_max',5)]:need(limits.get(field)==exact,'logical envelope mismatch: '+field)
 roots=guard.get('roots',{});need(set(roots)=={'caller','primary','secondary'},'exact root roles required')
 for role in ('caller','primary','secondary'):
  root=roots.get(role,{})
  need(isinstance(root.get('name'),str) and re.fullmatch('[A-Za-z0-9_-]{1,100}',root['name']),'bounded fresh root name required')
  identity=root.get('identity',{})
  need(identity.get('profile')==PROFILE and all(isinstance(identity.get(f),str) and identity[f] for f in ('root','instance')),'complete root identity required')
 need(len({roots[role]['name'] for role in roots})==3 and len({roots[role]['identity']['root'] for role in roots})==3,'three distinct verified roots required')
 placements=guard.get('placements',{})
 need(set(placements)=={'caller','primary','secondary'},'all root placements required')
 for role in placements:need(placements[role].get('identity')==roots[role]['identity'] and placements[role].get('owner')==owner,'same-runtime observed recipient placement required')
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
  if value['status']=='FAIL' and value.get('traceEntryUnknown') is True:
   peer=guard['roots']['secondary']['identity'];need(value.get('dispatchAttempted') is True,'unknown primary dispatch must retain attempted flag')
   need(any(r.get('run')==guard['run_id'] and r.get('recipient')==peer and r.get('requestId')==guard['run_id']+':secondary:2' and r.get('kind')=='peer' and r.get('traceEntered') is True and r.get('status')=='FAIL' and any(e.get('schedule') is False for e in r.get('errors',[])) for r in value.get('evidence',{}).get('receipts',[])),'known body failure required beside uncertain primary')
   return
  uncertain=value.get('blocker',{}).get('type')=='BLOCKED_UNCERTAIN_DISPATCH'
  if uncertain:
   need(value['status']=='BLOCKED' and value.get('phase')=='trace-unknown' and value.get('dispatchAttempted') is True and value.get('traceEntryUnknown') is True,'inconsistent uncertain-dispatch receipt')
  else:
   need(value['status']=='BLOCKED' and value.get('phase')=='precondition' and value.get('blocker',{}).get('type')=='BLOCKED_PREREQUISITE' and not value.get('traceEntryUnknown',False),'invalid precondition receipt')
  return
 if value['status']=='BLOCKED':need(value.get('blocker',{}).get('type') in ('BLOCKED_SCHEDULE','BLOCKED_NATIVE_CLEANUP'),'unsupported entered-trace blocker')
 identities={role:guard['roots'][role]['identity'] for role in ('primary','secondary')}
 need(value.get('recipients')==identities,'recipient identities mismatch')
 evidence=value.get('evidence',{});events=evidence.get('events');receipts=evidence.get('receipts')
 need(isinstance(events,list) and isinstance(receipts,list) and len(events)<=64,'missing or excessive actual events/receipts')
 main_id=guard['run_id']+':primary:1';peer_id=guard['run_id']+':secondary:2'
 need(any(e.get('kind')=='main-enter' and e.get('label')==case_id and e.get('recipient')==identities['primary'] and e.get('requestId')==main_id and e.get('run')==guard['run_id'] for e in events),'actual primary body-entry witness missing')
 if value['status']!='PASS':return
 row=next(r for r in json.loads((HERE/'manifest.json').read_text()) if r['id']==case_id)
 expected=[('main-enter',case_id,'primary',main_id),('held',row['hold_label'],'primary',main_id),('peer-enter',row['peer_operation'],'secondary',peer_id),('peer-done',row['peer_operation'],'secondary',peer_id),('released',row['hold_label'],'primary',main_id),('main-done',case_id,'primary',main_id)]
 need(len(events)==len(expected),'complete exact causal overlap event trace required')
 for sequence,(event,(kind,label,role,request_id)) in enumerate(zip(events,expected)):
  need(event=={'run':guard['run_id'],'kind':kind,'label':label,'recipient':identities[role],'requestId':request_id,'sequence':sequence},'uncorrelated or nonoverlapping event')
 need(type(evidence.get('wallMs')) is int and 0<=evidence['wallMs']<=29000,'fixture elapsed bound')
 need(len(receipts)==2 and len({r.get('requestId') for r in receipts})==2,'two distinct actual recipient request receipts required')
 total_bytes=0;max_live=0
 for kind,role,request_id,operation in [('main','primary',main_id,case_id),('peer','secondary',peer_id,row['peer_operation'])]:
  receipt=next((r for r in receipts if r.get('requestId')==request_id),{})
  need(receipt.get('run')==guard['run_id'] and receipt.get('recipient')==identities[role] and receipt.get('kind')==kind and receipt.get('id')==operation,'recipient operation receipt correlation')
  need(receipt.get('status')=='PASS' and receipt.get('traceEntered') is True and isinstance(receipt.get('value'),dict) and receipt.get('errors')==[],'assertion-bearing failure-free recipient body receipt required')
  clean=receipt.get('cleanup',{})
  need(clean.get('status')=='ok' and clean.get('run')==guard['run_id'] and clean.get('requestId')==request_id and clean.get('recipient')==identities[role],'operation cleanup correlation')
  need(isinstance(clean.get('actions'),list) and all(a.get('status')=='fulfilled' for a in clean['actions']),'cleanup action failures or unresolved actions')
  need(clean.get('pending')==0 and clean.get('bodyPending') is False and clean.get('bodyStarted') is True and clean.get('unreleasedHandles')==0 and clean.get('disposed') is True and clean.get('jsDisposed') is True and clean.get('nativeUnresolved')==0 and clean.get('openOperations')==0 and clean.get('failures')==[] and clean.get('unhandledRejections')==[] and type(clean.get('fixtureHandlesReleased')) is int,'fixture-owned resources or original body not drained')
  need(type(clean.get('maxOpenOperations')) is int and 0<=clean['maxOpenOperations']<=3,'native operation counter missing/exceeded')
  need(type(clean.get('totalBytes')) is int and 0<=clean['totalBytes']<=2097152,'per-recipient bytes bound')
  max_live+=clean['maxOpenOperations'];total_bytes+=clean['totalBytes']
 need(max_live<=4 and total_bytes<=4194304,'conservative simultaneous-operation or aggregate byte bound exceeded')
 cleanup=value.get('cleanup',{});need(value.get('phase')=='complete' and cleanup.get('status')=='ok' and cleanup.get('run')==guard['run_id'] and cleanup.get('pending')==0 and cleanup.get('held')==0 and cleanup.get('failures')==[],'coordinator cleanup incomplete')
 remote=cleanup.get('remote',[]);need(len(remote)==2,'both independent recipients must clean up')
 for role,receipt in zip(('primary','secondary'),remote):
  need(receipt.get('run')==guard['run_id'] and receipt.get('recipient')==identities[role] and receipt.get('status')=='ok' and receipt.get('active')==0 and receipt.get('contexts')==1 and receipt.get('allContextsDisposed') is True,'recipient terminal cleanup incomplete')
  residual=receipt.get('residual',[]);need(len(residual)==1 and residual[0].get('disposed') is True and residual[0].get('jsDisposed') is True and residual[0].get('nativeUnresolved')==0 and residual[0].get('pending')==0 and residual[0].get('bodyPending') is False and residual[0].get('bodyStarted') is True and residual[0].get('unreleasedHandles')==0 and residual[0].get('openOperations')==0,'recipient still owns original body or fixture resources')
 need(value.get('errors')==[] and value.get('traceEntryUnknown') is False and value.get('bodyReceiptMissing') is False,'PASS hides error or uncertain body')
 need(value.get('qualification')=='PENDING_EXTERNAL_SUPERVISOR_REVIEW','external teardown qualification missing')

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
  receipt=client.request('/run',payload)
  uncertain=receipt.get('blocker',{}).get('type')=='BLOCKED_UNCERTAIN_DISPATCH' or receipt.get('phase')=='trace-unknown' or receipt.get('traceEntryUnknown') is True
  if uncertain:
   receipt=dict(receipt);receipt['traceEntryUnknown']=True;result['traceEntryUnknown']=True;result['do_not_retry']=True;result['cleanup']={'status':'UNKNOWN','required':'Independent owned process/storage teardown; no blind retry.'}
  result['unqualified_fixture_receipt']=receipt;validate_terminal(receipt,case_id,guard);result['fixture_result']=receipt;result.pop('unqualified_fixture_receipt',None);result['traceEntered']=receipt['traceEntered']
  if receipt['status']=='PASS':result.update(semantic_status='PASS',blocker={'type':'BLOCKED_EXTERNAL_TEARDOWN','detail':'Independent terminal process/storage/resource receipt required before counting runtime success.'})
  else:
   result['status']=receipt['status'];result['traceEntryUnknown']=uncertain or receipt.get('traceEntryUnknown',False)
   if receipt.get('blocker'):result['blocker']=receipt['blocker']
   if receipt.get('blocker',{}).get('type')=='BLOCKED_NATIVE_CLEANUP':result['do_not_retry']=True;result['cleanup']={'status':'UNKNOWN_NATIVE','required':'Independent owned process/storage teardown; unresolved native state cannot be auto-promoted.'}
 except Exception as error:
  result['error']=str(error);result['blocker']={'type':'BLOCKED_PREREQUISITE' if not result.get('dispatch_attempted') else 'BLOCKED_UNCERTAIN_DISPATCH','detail':str(error)}
  if result.get('dispatch_attempted'):result['traceEntryUnknown']=True;result['do_not_retry']=True;result['cleanup']={'status':'UNKNOWN','required':'No retry. The direct-runtime test-harness supervisor must terminate/reap only the owned guest/runtime and remove owned storage.'}
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
