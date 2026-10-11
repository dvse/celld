#!/usr/bin/env python3
"""Request-only adapter. Never deploys, launches, kills, or modifies a runtime."""
import argparse,datetime,hashlib,ipaddress,json,pathlib,urllib.parse,urllib.request,uuid
HERE=pathlib.Path(__file__).resolve().parent
BINARY='62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirects prohibited by private adapter')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--base-url',required=True);p.add_argument('--guard',type=pathlib.Path,required=True)
 p.add_argument('--case',required=True);p.add_argument('--evidence',type=pathlib.Path,required=True)
 a=p.parse_args();result={'id':a.case,'status':'BLOCKED','traceEntered':False,'started_utc':now(),'adapter':'request-only-v1'}
 try:
  u=urllib.parse.urlsplit(a.base_url)
  if u.scheme!='http' or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
   raise ValueError('base URL must be credential-free private HTTP origin')
  ip=ipaddress.ip_address(u.hostname)
  allowed=ip.is_loopback or any(ip in net for net in [ipaddress.ip_network('10.0.0.0/8'),ipaddress.ip_network('172.16.0.0/12'),ipaddress.ip_network('192.168.0.0/16')] if ip.version==net.version)
  if not allowed:raise ValueError('only loopback or RFC1918 IP literals permitted')
  guard=json.loads(a.guard.read_text())
  required=('exclusive_run_slot','owned_disposable_fleet','pid_health_verified','limits_enforced','storage_teardown_owned')
  if any(guard.get(k) is not True for k in required):raise ValueError('external supervisor guard missing required verified ownership/limits')
  if not isinstance(guard.get('limits_evidence'),str) or not guard['limits_evidence']:raise ValueError('external enforced-limits evidence reference required')
  if guard.get('base_url','').rstrip('/')!=a.base_url.rstrip('/'):raise ValueError('guard endpoint mismatch')
  if guard.get('binary_sha256')!=BINARY:raise ValueError('frozen binary hash mismatch')
  if guard.get('profile_sha256')!=digest(HERE/'wrangler.jsonc'):raise ValueError('separate profile hash mismatch')
  hashes={name:digest(HERE/name) for name in ('index.js','cases.js','sources.mjs','manifest.json','wrangler.jsonc')}
  if guard.get('implementation_hashes')!=hashes:raise ValueError('guard must match all staged wave hashes')
  if not 1<=guard.get('request_timeout_seconds',0)<=30:raise ValueError('request timeout must be 1..30 seconds')
  cases=json.loads((HERE/'manifest.json').read_text())
  if a.case not in {c['id'] for c in cases}:raise ValueError('unknown case')
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
  timeout=guard['request_timeout_seconds'];base=a.base_url.rstrip('/')
  with opener.open(base+'/health',timeout=timeout) as response:health=json.loads(response.read(65536))
  if health.get('profile')!='loader-props-2026-09-04' or health.get('compatibilityDate')!='2026-09-04' or health.get('hasLoader') is not True or a.case not in health.get('caseIds',[]):raise ValueError('deployed fixture/profile preflight mismatch')
  payload={'id':a.case,'tag':a.case+':'+str(uuid.uuid4())}
  request=urllib.request.Request(base+'/run',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
  result.update({'dispatch_attempted':True,'root_tag':payload['tag'],'binary_sha256':BINARY,'implementation_hashes':hashes,'guard_sha256':digest(a.guard)})
  try:
   with opener.open(request,timeout=timeout) as response:observed=json.loads(response.read(1048576))
  except Exception as error:
   result.update(status='BLOCKED',error='No terminal fixture receipt: '+str(error),traceEntered=False,traceEntryUnknown=True,cleanup={'status':'UNKNOWN','required':'External supervisor must tear down its owned fleet; do not retry automatically.'})
  else:
   if observed.get('id')!=a.case or observed.get('requestTag')!=payload['tag'] or observed.get('status') not in ('PASS','FAIL','BLOCKED') or not isinstance(observed.get('traceEntered'),bool):raise ValueError('invalid fixture receipt')
   if observed.get('status')=='PASS':
    origin=observed.get('origin',{})
    if observed.get('requestTag')!=payload['tag'] or origin.get('name')!=payload['tag']:raise ValueError('PASS root/tag correlation mismatch')
    if observed.get('profile')!='loader-props-2026-09-04' or observed.get('compatibilityDate')!='2026-09-04' or observed.get('phase')!='complete':raise ValueError('PASS profile/date/phase mismatch')
    if not isinstance(origin.get('root'),str) or not origin['root'] or not isinstance(origin.get('isolate'),str) or not origin['isolate']:raise ValueError('PASS missing origin witness')
    if observed.get('cleanup',{}).get('status')!='ok' or not observed['traceEntered']:raise ValueError('PASS missing trace/cleanup receipt')
   result.update(observed)
   result['qualification']='PENDING_EXTERNAL_SUPERVISOR_TEARDOWN_AND_REVIEW'
 except Exception as error:result.update(status='BLOCKED',error=str(error))
 result['finished_utc']=now();a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
 return 0 if result['status']=='PASS' else 2
if __name__=='__main__':raise SystemExit(main())
