#!/usr/bin/env python3
"""Request-only, import-only adapter. No deployment, process launch, guest, or fault action.
A separately reviewed supervisor supplies a fresh owned fleet, hard bounds, identity,
placement and final teardown evidence. This file cannot manufacture those witnesses.
"""
import datetime, hashlib, http.client, ipaddress, json, pathlib, re, signal, time, urllib.parse
HERE=pathlib.Path(__file__).resolve().parent
BINARY='8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f'
PROFILE='active-websocket-candidate-v1'
FILES=('common.js','fixture.js','lab.js','cases.js','wrangler.jsonc','package.json','profile.json','manifest.json','source-pins.json','private_driver.py')
class Blocked(Exception):
    code='BLOCKED_PREREQUISITE'
def need(condition,message):
    if not condition: raise Blocked(message)
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def pins():return {name:sha(HERE/name) for name in FILES}
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def origin(value):
    u=urllib.parse.urlsplit(value)
    need(u.scheme=='http' and not u.username and not u.password and not u.query and not u.fragment and u.path in ('','/') and u.port==18080,'credential-free literal private HTTP origin on fixture port18080 required')
    try:ip=ipaddress.ip_address(u.hostname)
    except ValueError as e:raise Blocked('IP literal required; no DNS or redirects') from e
    need(ip.version==4 and (ip.is_loopback or any(ip in ipaddress.ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16'))),'public/link-local destination prohibited')
    return u.scheme+'://'+u.netloc

def validate_guard(guard,case_id):
    rows=json.loads((HERE/'manifest.json').read_text());need(case_id in {r['id'] for r in rows},'unknown case')
    for key in ('exclusive_run_slot','owned_disposable_fleet','hard_limits_observed','cleanup_ownership_verified','local_receiver_placement_verified','active_websocket_only_scope_reviewed'):
        need(guard.get(key) is True,'missing external verified prerequisite: '+key)
    need(re.fullmatch('[a-f0-9]{16}',guard.get('run_id','')) is not None,'fresh 16-hex run ID required')
    need(guard.get('binary_sha256')==BINARY,'binary mismatch')
    source=json.loads((HERE/'source-pins.json').read_text())
    need(sha(source['runtime_manifest'])==source['runtime_manifest_sha256'] and source['binary_sha256']==BINARY,'frozen source manifest changed')
    for item in source['sources']:need(sha(item['path'])==item['sha256'],'pinned source changed: '+item.get('manifest_key',item['path']))
    need(guard.get('implementation_hashes')==pins() and guard.get('reviewed_implementation_hashes')==pins(),'implementation or independent review stale')
    need(case_id in guard.get('reviewed_case_ids',[]),'case lacks accepted distinctness/oracle review')
    need(guard.get('profile_sha256')==sha(HERE/'profile.json'),'profile mismatch')
    for key in ('ownership_evidence','limits_evidence','placement_evidence','review_evidence','cleanup_plan_evidence'):
        evidence=guard.get(key,{})
        need(isinstance(evidence.get('path'),str) and pathlib.Path(evidence['path']).is_file(),'missing supervisor evidence file: '+key)
        need(sha(evidence['path'])==evidence.get('sha256'),'evidence digest mismatch: '+key)
    limits=guard.get('limits',{})
    for key,maximum in [('case_wall_seconds',30),('memory_mib_per_guest',1024),('pids_per_guest',128),('vcpus_per_guest',2)]:
        value=limits.get(key);need(type(value) is int and 1<=value<=maximum,'missing/excessive hard resource bound '+key)
    need(limits.get('fixture_logical_bytes_allowance')==4194304 and limits.get('simultaneous_control_requests_max')==8 and limits.get('live_websockets_max')==4,'logical request/payload bounds mismatch')
    caller=guard.get('caller',{});recipient=guard.get('recipient',{})
    for role in (caller,recipient):
        origin(role.get('origin',''))
        need(re.fullmatch('[A-Za-z0-9_-]{1,100}',role.get('name','')) is not None,'bounded DO name required')
        for key in ('vm_id','boot_id','start_ticks'):need(isinstance(role.get(key),str) and role[key],'missing process/VM identity '+key)
        need(type(role.get('runtime_pid')) is int and role['runtime_pid']>0 and role.get('executable_sha256')==BINARY,'runtime executable identity missing')
        identity=role.get('identity',{});need(identity.get('profile')==PROFILE and all(isinstance(identity.get(k),str) and identity[k] for k in ('root','isolate')),'fixture identity witness missing')
    need(recipient['origin']=='http://192.168.77.1:18080','recipient must match fixed staged PRIVATE_ORIGIN; no runtime endpoint override')
    need(caller['name']!=recipient['name'] and caller['identity']['root']!=recipient['identity']['root'] and caller['identity']['isolate']!=recipient['identity']['isolate'],'caller and recipient must be independently witnessed DOs')
    need((caller['vm_id'],caller['runtime_pid'],caller['start_ticks'])!=(recipient['vm_id'],recipient['runtime_pid'],recipient['start_ticks']),'two independently observed runtime processes required')
    need(guard.get('recipient_gateway_process')=={k:recipient[k] for k in ('vm_id','runtime_pid','start_ticks')},'receiver must reside locally to its ingress gateway for ordinary local WebSocket recipient dispatch')
    return guard

class PrivateClient:
    def __init__(self,deadline):self.deadline=deadline;self.sockets=set();self.attempts=0
    def request(self,base,path,body=None):
        base=origin(base);need(path.startswith('/') and not path.startswith('//') and len(path)<256,'bounded relative fixture path')
        self.attempts+=1;need(self.attempts<=4,'external control request bound')
        u=urllib.parse.urlsplit(base);remaining=self.deadline-time.monotonic();need(remaining>0,'case deadline expired')
        connection=http.client.HTTPConnection(u.hostname,u.port,timeout=min(remaining,26));self.sockets.add(connection)
        try:
            encoded=None if body is None else json.dumps(body).encode();need(encoded is None or len(encoded)<8192,'driver request bound')
            connection.request('GET' if body is None else 'POST',path,body=encoded,headers={'Content-Type':'application/json','Connection':'close'})
            response=connection.getresponse();need(response.status==200,'unexpected HTTP status; redirects are never followed')
            raw=response.read(4194305);need(len(raw)<=4194304,'driver response evidence bound');return json.loads(raw)
        finally:connection.close();self.sockets.discard(connection)
    def close(self):
        for connection in list(self.sockets):connection.close();self.sockets.discard(connection)

def validate_terminal(value,case_id,guard):
    need(value.get('id')==case_id and value.get('run')==guard['run_id'] and value.get('profile')==PROFILE and value.get('binary')==BINARY,'terminal receipt correlation mismatch')
    need(value.get('caller')==guard['caller']['identity'],'terminal caller mismatch')
    need(value.get('status') in ('PASS','FAIL','BLOCKED') and type(value.get('traceEntered')) is bool,'typed terminal result required')
    if not value['traceEntered']:
        need(value['status']=='BLOCKED' and value.get('phase')=='precondition' and isinstance(value.get('error'),dict),'invalid precondition receipt')
        return
    need(value.get('recipient')==guard['recipient']['identity'],'terminal recipient mismatch')
    need(value['status'] in ('PASS','FAIL'),'entered trace cannot become a setup block')
    evidence=value.get('evidence',{});need(isinstance(evidence.get('events'),list),'missing evidence')
    for key,maximum in [('wireBytes',524288),('frames',256),('controls',128),('wallMs',24000)]:
        need(type(evidence.get(key)) is int and evidence[key]>=0 and (value['status']!='PASS' or evidence[key]<=maximum),'unverified fixture bound '+key)
    need(value.get('characterization')==(case_id in ('W023','W024')),'classification mismatch')
    if value['status']=='PASS':
        cleanup=value.get('cleanup',{});remote=cleanup.get('remote',{});local=cleanup.get('local',{})
        need(value.get('phase')=='complete' and cleanup.get('status')=='ok','semantic success lacks cleanup')
        need(all(any(e.get('kind')==kind for e in evidence['events']) for kind in ('identities','clean-close-control','recovery')),'clean controls or identities absent')
        need(any(e.get('kind')=='identities' and e.get('caller')==guard['caller']['identity'] and e.get('recipient')==guard['recipient']['identity'] for e in evidence['events']),'identities do not match source witness')
        need(remote.get('run')==guard['run_id'] and all(remote.get(k)==v for k,v in guard['recipient']['identity'].items()),'recipient cleanup identity mismatch')
        need(remote.get('cleanup')=='ok' and remote.get('faults')==[] and all(remote.get(k)==0 for k in ('live','held','waiters')),'recipient cleanup unverified')
        need(all(local.get(k)==0 for k in ('live','pending','tasks')),'local sockets/normalizers remain')
        need(0<=remote.get('wireBytes',-1)<=524288 and 0<=remote.get('frames',-1)<=256,'recipient aggregate bound')
        clients=evidence.get('clients',[]);peers=remote.get('peers',[])
        need(2<=len(clients)<=8 and {p['id'] for p in clients}=={p['id'] for p in peers},'complete endpoint set required')
        for client in clients:
            peer=next(p for p in peers if p['id']==client['id'])
            need(client.get('errors')==[] and peer.get('errors')==[],'error on clean socket')
            for side in (client,peer):
                events=side.get('close',[]);need(len(events)==1 and events[0].get('wasClean') is True,'one clean close per endpoint required')
            need(all(m.get('ready') is True for m in client.get('messages',[])),'unsettled normalization')
            need([m['value'] for m in client['messages']]==peer.get('sent') and client.get('sent')==peer.get('received'),'complete transport transcript mismatch')



def run_case(case_id,guard):
    report={'id':case_id,'status':'BLOCKED','traceEntered':False,'started_utc':utc(),'binary_sha256':BINARY}
    client=None;timer=False;previous=None
    try:
        report['implementation_hashes']=pins();validate_guard(guard,case_id);need(hasattr(signal,'setitimer'),'absolute wall timer unavailable');need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'dedicated driver process required: pre-existing wall timer')
        report.update(run_id=guard['run_id'],profile=PROFILE,profile_sha256=sha(HERE/'profile.json'),owner_witness={'caller':guard['caller'],'recipient':guard['recipient']},limits=guard['limits'])
        deadline=time.monotonic()+min(guard['limits']['case_wall_seconds'],28)
        def expired(*_):raise TimeoutError('absolute case deadline; supervisor must destroy owned fleet')
        previous=signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,deadline-time.monotonic());timer=True;client=PrivateClient(deadline)
        for role in ('caller','recipient'):
            target=guard[role];observed=client.request(target['origin'],'/root/'+target['name']+'/identity')
            need(observed==target['identity'],'live '+role+' identity differs from supervisor placement proof')
        health=client.request(guard['recipient']['origin'],'/health');need(health.get('profile')==PROFILE and case_id in health.get('caseIds',[]),'staged health/profile mismatch')
        payload={'id':case_id,'run':guard['run_id'],'recipient':guard['recipient']['name'],'expectedCaller':guard['caller']['identity'],'expectedRecipient':guard['recipient']['identity']}
        report['dispatch_attempted']=True;report['traceEntered']=None
        value=client.request(guard['caller']['origin'],'/root/'+guard['caller']['name']+'/run',payload)
        report['unqualified_fixture_receipt']=value
        validate_terminal(value,case_id,guard)
        report.update(traceEntered=value.get('traceEntered') is True,fixture_result=value);report.pop('unqualified_fixture_receipt',None)
        if value.get('status')=='PASS':
            need(value.get('phase')=='complete' and report['traceEntered'] and value.get('cleanup',{}).get('status')=='ok','invalid PASS receipt')
            report['semantic_status']='PASS';report['characterization']=case_id in ('W023','W024');report['blocker']='Final independently evidenced teardown/resource record required; characterization can never become a promotion PASS.'
        else:report['status']=value.get('status') if value.get('status') in ('FAIL','BLOCKED') else 'FAIL'
    except Exception as error:
        report['error']=str(error)
        if report['traceEntered'] is True:report['status']='FAIL'
        else:report['blocker']={'type':'BLOCKED_PREREQUISITE' if isinstance(error,Blocked) else 'BLOCKED_NO_CORRELATED_TERMINAL_RECEIPT','detail':str(error)}
    finally:
        if client:client.close();report['local_socket_cleanup']={'open':len(client.sockets),'attempts':client.attempts}
        if timer:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
        report['finished_utc']=utc();report['supervisor_teardown_required']=bool(report.get('dispatch_attempted'))
    return report

def finalize(report,teardown):
    """Called only after the external supervisor actually destroys its owned fleet."""
    need(not report.get('characterization'),'buffering characterization is never a promotion PASS')
    need(report.get('semantic_status')=='PASS' and report.get('traceEntered') is True,'no complete semantic candidate')
    need(teardown.get('run_id')==report.get('run_id') and teardown.get('id')==report['id'],'teardown correlation mismatch')
    need(teardown.get('implementation_hashes')==report['implementation_hashes'] and teardown.get('binary_sha256')==BINARY,'teardown input mismatch')
    need(teardown.get('owner_witness')==report['owner_witness'],'teardown ownership mismatch')
    for flag in ('all_owned_processes_reaped','all_owned_sockets_closed','all_case_storage_destroyed','no_unowned_process_touched','hard_wall_limit_satisfied'):
        need(teardown.get(flag) is True,'cleanup not independently established: '+flag)
    evidence=teardown.get('evidence',{});need(isinstance(evidence.get('path'),str) and pathlib.Path(evidence['path']).is_file() and sha(evidence['path'])==evidence.get('sha256'),'teardown evidence missing')
    observations=teardown.get('resource_high_water',{})
    for role in ('caller','recipient'):
        record=observations.get(role,{})
        for key,limit in [('memory_mib','memory_mib_per_guest'),('pids','pids_per_guest'),('vcpus','vcpus_per_guest')]:
            measured=record.get(key);need(type(measured) is int and 0<measured<=report['limits'][limit],'unverified resource high water '+role+' '+key)
    return {**report,'status':'PASS','supervisor_teardown_required':False,'teardown':teardown,'blocker':None}
