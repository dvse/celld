#!/usr/bin/env python3
"""Request-only adapter. No builds, deployment, guests, or resource setting changes."""
import argparse, datetime, hashlib, ipaddress, json, pathlib, signal, time, urllib.error, urllib.parse, urllib.request, uuid
HERE=pathlib.Path(__file__).resolve().parent
BINARY='62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
PROFILE='bounded-resource-frozen-v1'
FILES=('workers.js','fixture.js','cases.js','entry.js','wrangler.jsonc','profile.json','manifest.json','source-pins.json','run.py')
UNSUPPORTED={'Q016','Q017','Q018'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect prohibited')
def validate_terminal(v,request_id,case_id,origin):
 if v.get('requestId')!=request_id or v.get('id')!=case_id or v.get('profile')!=PROFILE or v.get('origin')!=origin:raise ValueError('receipt correlation/identity mismatch')
 if v.get('status') not in ('PASS','FAIL','BLOCKED'):raise ValueError('invalid terminal status')
 if v['status']=='PASS' and case_id=='Q010' and v.get('evidence',{}).get('computeEntered') is not True:raise ValueError('finite compute receiver entry witness missing')
 if v['status']=='PASS' and (case_id in UNSUPPORTED or v.get('traceEntered') is not True or v.get('phase')!='complete' or v.get('cleanup',{}).get('status')!='ok' or not isinstance(v.get('evidence'),dict)):raise ValueError('invalid PASS: unsupported protection, missing trace, assertions, or cleanup')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base-url');p.add_argument('--guard',type=pathlib.Path);p.add_argument('--case',required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
 result={'id':a.case,'status':'BLOCKED','traceEntered':False,'started_utc':now(),'adapter':'bounded-resource-request-only-v1'};armed=False
 try:
  if a.case not in {row['id'] for row in json.loads((HERE/'manifest.json').read_text())}:raise ValueError('unknown case')
  if a.case in UNSUPPORTED:raise ValueError('Unsupported protection observation execution BLOCKED pending separately reviewed scope/profile')
  if not a.base_url or not a.guard:raise ValueError('reviewed private endpoint and supervisor guard required; no request sent')
  u=urllib.parse.urlsplit(a.base_url)
  if u.scheme!='http' or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):raise ValueError('credential-free private HTTP origin required')
  ip=ipaddress.ip_address(u.hostname)
  if not (ip.is_loopback or any(ip.version==n.version and ip in n for n in map(ipaddress.ip_network,['10.0.0.0/8','172.16.0.0/12','192.168.0.0/16']))):raise ValueError('loopback/RFC1918 IP literal required')
  guard=json.loads(a.guard.read_text());hashes={name:sha(HERE/name) for name in FILES}
  for key in ('exclusive_run_slot','owned_disposable_fleet','pid_health_verified','limits_enforced','storage_teardown_owned','scope_review_excludes_restricted_lifetime'):
   if guard.get(key) is not True:raise ValueError('missing supervisor guard: '+key)
  for key in ('limits_evidence','owner_evidence','readiness_evidence','review_evidence','restricted_scope_review_evidence'):
   if not isinstance(guard.get(key),str) or not guard[key]:raise ValueError('missing evidence: '+key)
  if guard.get('base_url','').rstrip('/')!=a.base_url.rstrip('/') or guard.get('binary_sha256')!=BINARY:raise ValueError('endpoint/frozen binary mismatch')
  if guard.get('implementation_hashes')!=hashes or guard.get('reviewed_implementation_hashes')!=hashes or a.case not in guard.get('reviewed_case_ids',[]):raise ValueError('exact implementation independent review missing')
  if guard.get('profile_sha256')!=hashes['profile.json']:raise ValueError('profile hash mismatch')
  if guard.get('runtime_env')!={'CELLD_MAX_DYNAMIC_WORKER_CODE_BYTES':'8192','CELLD_TOKIO_THREADS':'2'}:raise ValueError('verified runtime environment mismatch')
  owner=guard.get('owner',{})
  if not isinstance(owner.get('runtime_pid'),int) or isinstance(owner.get('runtime_pid'),bool) or owner['runtime_pid']<=0 or not all(isinstance(owner.get(k),str) and owner[k] for k in ('vm_id','root')):raise ValueError('verified owner PID/VM/root required')
  limits=guard.get('limits',{})
  for key,lo,hi in [('case_wall_seconds',1,30),('memory_mib_per_guest',1,1024),('pids_per_guest',1,128),('vcpus_per_guest',1,2)]:
   value=limits.get(key)
   if isinstance(value,bool) or not isinstance(value,(int,float)) or not lo<=value<=hi:raise ValueError('enforced limit missing/excessive: '+key)
  for key,val in [('trace_rpc_attempts_max',16),('logical_payload_bytes_max',33554432),('loaded_workers_max',4),('live_foreground_requests_max',4)]:
   if limits.get(key)!=val:raise ValueError('resource envelope mismatch: '+key)
  timeout=guard.get('request_timeout_seconds',0)
  if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not 1<=timeout<=30:raise ValueError('request timeout must be 1..30')
  deadline=time.monotonic()+limits['case_wall_seconds']
  def expired(*_):raise TimeoutError('absolute case deadline; owned supervisor teardown required')
  if not hasattr(signal,'setitimer'):raise ValueError('absolute wall timer unavailable')
  signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,limits['case_wall_seconds']);armed=True
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
  def request(path,body=None):
   req=urllib.request.Request(a.base_url.rstrip('/')+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json'})
   try:response=opener.open(req,timeout=max(.001,min(timeout,deadline-time.monotonic())))
   except urllib.error.HTTPError as e:response=e
   with response:
    data=response.read(1048577)
    if len(data)>1048576:raise ValueError('receipt exceeds 1MiB')
    return json.loads(data)
  health=request('/health')
  if health.get('profile')!=PROFILE or a.case not in health.get('caseIds',[]):raise ValueError('deployed profile precondition failed')
  origin=request('/identity',{'root':owner['root']})
  if not all(isinstance(origin.get(k),str) and origin[k] for k in ('root','isolate')):raise ValueError('runtime identity missing')
  token=str(uuid.uuid4());result.update(dispatch_attempted=True,requestId=token,binary_sha256=BINARY,guard_sha256=sha(a.guard),implementation_hashes=hashes,owner_witness=owner,enforced_limits=limits,qualification='PENDING_EXTERNAL_SUPERVISOR_TEARDOWN_REVIEW')
  value=request('/run',{'id':a.case,'root':owner['root'],'requestId':token});validate_terminal(value,token,a.case,origin);result.update(status=value['status'],traceEntered=value.get('traceEntered') is True,result=value)
 except Exception as error:
  result['error']=str(error)
  if result.get('dispatch_attempted'):result.update(traceEntryUnknown=True,cleanup={'status':'UNKNOWN','required':'Tear down only owned fleet/process/storage; never retry uncertain dispatch.'})
 finally:
  if armed:signal.setitimer(signal.ITIMER_REAL,0)
  result['finished_utc']=now();a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'id':a.case,'status':result['status'],'traceEntered':result['traceEntered'],'report':str(a.report)}));return 0 if result['status']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
