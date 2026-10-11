#!/usr/bin/env python3
"""Request-only adapter. Does not build, deploy, launch, or tear down any runtime."""
import argparse,datetime,hashlib,ipaddress,json,pathlib,signal,time,urllib.error,urllib.parse,urllib.request,uuid
HERE=pathlib.Path(__file__).resolve().parent
BINARY='8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f'
PROFILE='module-graph-candidate8d27-v1'
FILES=('graphs.mjs','cases.mjs','fixture.mjs','entry.mjs','wrangler.jsonc','profile.json','manifest.json','source-pins.json','run.py')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect prohibited')
def validate_terminal(value,request_id,case_id,origin):
 if value.get('requestId')!=request_id or value.get('id')!=case_id or value.get('profile')!=PROFILE or value.get('compatibilityDate')!='2026-09-04' or value.get('origin')!=origin:raise ValueError('receipt correlation/profile mismatch')
 if value.get('status') not in ('PASS','FAIL','BLOCKED') or not isinstance(value.get('traceEntered'),bool):raise ValueError('invalid terminal status')
 if value['status']=='PASS':
  cleanup=value.get('cleanup',{})
  if cleanup.get('unsettledTaskCount')!=0 or cleanup.get('outerTasks')!=[{'label':'setup','settled':True},{'label':'trace','settled':True}]:raise ValueError('PASS requires complete setup and trace task settlement')
  states=cleanup.get('startupStates');workers=cleanup.get('workers')
  if cleanup.get('unsettledStartupCount')!=0 or type(workers) is not int or not 1<=workers<=4 or not isinstance(states,list) or len(states)!=workers or any(state not in ('fulfilled','rejected') for state in states):raise ValueError('PASS requires every native startup completion or rejection witness')
  if value.get('traceEntered') is not True or value.get('phase')!='complete' or not isinstance(value.get('evidence'),dict) or cleanup.get('status')!='ok' or cleanup.get('drained') is not True or cleanup.get('pending')!=[] or cleanup.get('unsettledRpcCount')!=0 or cleanup.get('errors')!=[]:raise ValueError('PASS requires complete assertion trace and every invocation drained before disposal')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url');p.add_argument('--guard',type=pathlib.Path);p.add_argument('--case',required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
 result={'id':a.case,'status':'BLOCKED','traceEntered':False,'started_utc':now(),'adapter':'module-graph-request-only-v1','dispatch_attempted':False};armed=False
 try:
  ids={x['id'] for x in json.loads((HERE/'manifest.json').read_text())}
  if a.case not in ids:raise ValueError('unknown case')
  if not a.base_url or not a.guard:raise ValueError('exact reviewed supervisor guard and private endpoint required; no request sent')
  url=urllib.parse.urlsplit(a.base_url)
  if url.scheme!='http' or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):raise ValueError('credential-free private HTTP origin required')
  ip=ipaddress.ip_address(url.hostname)
  if not (ip.is_loopback or any(ip.version==net.version and ip in net for net in map(ipaddress.ip_network,['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']))):raise ValueError('only loopback/RFC1918 numeric origins permitted')
  guard=json.loads(a.guard.read_text());hashes={name:sha(HERE/name) for name in FILES}
  for key in ('exclusive_run_slot','owned_disposable_fleet','pid_health_verified','limits_enforced','storage_teardown_owned','scope_review_excludes_restricted_lifetime','fresh_supervisor_root_verified'):
   if guard.get(key) is not True:raise ValueError('missing verified guard: '+key)
  for key in ('limits_evidence','owner_evidence','readiness_evidence','review_evidence','restricted_scope_review_evidence'):
   if not isinstance(guard.get(key),str) or not guard[key]:raise ValueError('missing evidence reference: '+key)
  if guard.get('base_url','').rstrip('/')!=a.base_url.rstrip('/') or guard.get('binary_sha256')!=BINARY:raise ValueError('endpoint or candidate binary mismatch')
  if guard.get('implementation_hashes')!=hashes or guard.get('reviewed_implementation_hashes')!=hashes or a.case not in guard.get('reviewed_case_ids',[]):raise ValueError('exact independent source review required')
  if guard.get('profile_sha256')!=hashes['profile.json']:raise ValueError('bounded profile mismatch')
  pins=json.loads((HERE/'source-pins.json').read_text())
  for src in pins['sources']:
   if sha(HERE/src['path'])!=src['sha256']:raise ValueError('source provenance changed: '+src['path'])
  owner=guard.get('owner',{})
  if type(owner.get('runtime_pid')) is not int or owner['runtime_pid']<=0 or not all(isinstance(owner.get(k),str) and owner[k] for k in ('vm_id','root')):raise ValueError('verified owner PID/VM/root required')
  prefix,token=owner['root'].split(':',1)
  if prefix!=a.case or str(uuid.UUID(token))!=token:raise ValueError('fresh supervisor root must be case ID plus canonical UUID')
  limits=guard.get('limits',{})
  for key,lo,hi in [('case_wall_seconds',1,24),('memory_mib_per_guest',1,1024),('pids_per_guest',1,128),('vcpus_per_guest',1,2)]:
   val=limits.get(key)
   if isinstance(val,bool) or not isinstance(val,(int,float)) or not lo<=val<=hi:raise ValueError('missing/excessive enforced limit: '+key)
  for key,val in [('loaded_workers_max',4),('trace_rpc_attempts_max',512),('semantic_invocations_max',32),('live_foreground_requests_max',12),('semantic_inflight_max',8),('modules_per_graph_max',9),('utf8_code_bytes_per_graph_max',24576)]:
   if limits.get(key)!=val:raise ValueError('exact trace envelope required: '+key)
  timeout=guard.get('request_timeout_seconds')
  if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 1<=timeout<=24:raise ValueError('request timeout must be 1..24 seconds')
  if not hasattr(signal,'setitimer'):raise ValueError('absolute wall timer unavailable')
  deadline=time.monotonic()+limits['case_wall_seconds']
  def expired(*_):raise TimeoutError('absolute 24 second envelope expired; owned teardown required')
  signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,limits['case_wall_seconds']);armed=True
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
  def request(path,body=None):
   remaining=deadline-time.monotonic()
   if remaining<=0:raise TimeoutError('absolute deadline expired')
   req=urllib.request.Request(a.base_url.rstrip('/')+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   try:response=opener.open(req,timeout=min(timeout,remaining))
   except urllib.error.HTTPError as error:response=error
   with response:
    data=response.read(1048577)
    if len(data)>1048576:raise ValueError('receipt exceeds 1 MiB')
    return json.loads(data)
  health=request('/health')
  if health.get('profile')!=PROFILE or health.get('compatibilityDate')!='2026-09-04' or health.get('hasLoader') is not True or sorted(health.get('caseIds',[]))!=sorted(ids):raise ValueError('deployed inventory/profile mismatch')
  origin=request('/identity',{'root':owner['root']})
  if origin.get('name')!=owner['root'] or not all(isinstance(origin.get(k),str) and origin[k] for k in ('root','isolate')):raise ValueError('fresh root identity mismatch')
  result.update(dispatch_attempted=True,requestId=token,binary_sha256=BINARY,implementation_hashes=hashes,guard_sha256=sha(a.guard),owner_witness=owner,enforced_limits=limits)
  value=request('/run',{'id':a.case,'root':owner['root'],'requestId':token});validate_terminal(value,token,a.case,origin)
  result.update(status=value['status'],traceEntered=value['traceEntered'],result=value,qualification='PENDING_EXTERNAL_OWNED_PROCESS_STORAGE_TEARDOWN_AND_REVIEW')
 except Exception as error:
  result.update(status='BLOCKED',error=str(error))
  if result['dispatch_attempted']:result.update(traceEntryUnknown=True,cleanup={'status':'UNKNOWN','required':'Tear down only owned fleet/process/storage. Do not retry uncertain dispatch.'})
 finally:
  if armed:signal.setitimer(signal.ITIMER_REAL,0)
  result['finished_utc']=now();a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'id':a.case,'status':result['status'],'traceEntered':result['traceEntered'],'report':str(a.report)}));return 0 if result['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
