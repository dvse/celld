#!/usr/bin/env python3
"""Concrete alarm adapter derived from durable-recovery-stress/driver.py. Import-only: no CLI starts any process or workload.
The invoking supervisor must already own and transfer two disposable Guest objects.
Every case consumes and closes that fleet. Missing bounds/review/identity => BLOCKED.
"""
import datetime, hashlib, importlib.util, json, os, pathlib, re, shlex, signal, subprocess, time, uuid
HERE = pathlib.Path(__file__).resolve().parent
PROJECT = pathlib.Path('/workspace/shared/celld-os-project')
BINARIES = {'original':'62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e','candidate':'8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f'}
HELPERS = PROJECT / 'tests/emulated-network/guest_helpers.py'
STAGE = '/stage/alarm-event-stress'
PYTHON = 'LD_LIBRARY_PATH=/stage/native-durability/lib PYTHONHOME=/stage/native-durability/python /stage/native-durability/python/bin/python3.13'
class Blocked(Exception): pass
class ObservationTimeout(AssertionError): pass
class ControlStop(BaseException): pass
class CaseDeadline(ControlStop): pass
class ShutdownRequested(ControlStop): pass
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def check(ok, detail):
    if not ok: raise AssertionError(detail)
def need(ok, detail):
    if not ok: raise Blocked(detail)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def pins(): return {name:digest(HERE/name) for name in ('fixture.js','wrangler.jsonc','http_jobs.py','driver.py','cases.py','manifest.json','source-pins.json','bucket-profile.json')}
def host_identity(guest):
    pid = guest.p.pid; base = pathlib.Path('/proc') / str(pid)
    exe = (base / 'exe').resolve(strict=True); fields = (base / 'stat').read_text().rsplit(')', 1)[1].split()
    need('qemu-system-' in exe.name and fields[0] != 'Z', 'Guest is not a live QEMU process')
    return {'pid':pid, 'executable':str(exe), 'start_ticks':fields[19], 'pgid':os.getpgid(pid)}
def validate_guard(guard, case_id):
    need(guard.get('exclusive_run_slot') is True and guard.get('owned_disposable_fleet') is True, 'exclusive disposable fleet ownership required')
    need(guard.get('transfer_cleanup_ownership') is True, 'supervisor must explicitly transfer cleanup ownership for both Guest objects')
    need(guard.get('runtime') in BINARIES, 'select original or candidate explicitly')
    need(guard.get('binary_sha256') == BINARIES[guard['runtime']], 'selected binary pin mismatch')
    need(guard.get('implementation_hashes') == pins(), 'exact implementation hash mismatch')
    need(guard.get('reviewed_implementation_hashes') == pins() and case_id in guard.get('reviewed_case_ids', []), 'independent review missing or stale')
    need(guard.get('profile') == 'bucket', 'bucket-only alarm recovery profile; fleet proof is unsupported')
    need(re.fullmatch(r'[a-f0-9]{16}', guard.get('run_id','')) is not None, 'invalid fresh run ID')
    need(guard.get('profile_sha256') == digest(HERE/'bucket-profile.json'), 'bucket profile hash mismatch')
    need(guard.get('qemu_limits_verified') is True and guard.get('guest_cgroup_limits_verified') is True, 'pre-provisioned hard bounds required; adapter never modifies cgroups')
    for field in ('review_evidence','limits_evidence','deployment_evidence'):
        need(isinstance(guard.get(field),str) and bool(guard[field]), 'missing '+field)
class Driver:
    def __init__(self, guests, guard, case_id):
        validate_guard(guard, case_id)
        need(len(guests)==2 and [g.node for g in guests]==[1,2], 'exact two owned guests required')
        self.guests=guests; self.guard=guard; self.case_id=case_id; self.run_id=guard['run_id']; self.binary=BINARIES[guard['runtime']]; self.runtime_label=guard['runtime']; self.control_calls=0; self.request_serial=0
        self.prefix='/tmp/aes-'+self.run_id; self.bucket='aes-'+self.run_id
        self.events=[]; self.cohorts=[]; self.roots={}; self.jobs_total=0; self.serial=0; self.trace_entered=False; self.dispatch_attempted=False
        self.deadline=time.monotonic()+360; self.cleanup_authorized=False; self.runtime={}; self.stage_verified=False
        expected=guard.get('qemu',[]); need(len(expected)==2,'QEMU ownership records required')
        self.qemu=[host_identity(g) for g in guests]
        need(self.qemu==expected and all(x['pgid']==x['pid'] for x in self.qemu),'QEMU identity/process-group mismatch')
        # The exact ownership records are now trusted; later failures still tear down this fleet.
        self.cleanup_authorized=True
        helper_pin=next(x['sha256'] for x in json.loads((HERE/'source-pins.json').read_text())['sources'] if x['path']=='tests/emulated-network/guest_helpers.py')
        need(digest(HELPERS)==helper_pin,'trusted guest helper changed before import')
        specification=importlib.util.spec_from_file_location('aes_guest_helpers',HELPERS)
        module=importlib.util.module_from_spec(specification); specification.loader.exec_module(module)
        self.helpers=module
    def prerequisite(self,condition,detail):need(condition,detail)
    def event(self, kind, **data): self.events.append({'kind':kind, 'utc':utc(), 'elapsed':round(360-(self.deadline-time.monotonic()),3), **data})
    def py(self, node, source, timeout=25):
        remaining=getattr(self,'cleanup_deadline',self.deadline)-time.monotonic(); need(remaining>0,'case or cleanup wall deadline exhausted')
        return self.helpers.guest_python(self.guests[node-1],PYTHON,source,timeout=min(timeout,remaining))
    def http(self, node, url, body=None, timeout=12):
        need(url.startswith(('http://192.168.77.1:18080/','http://192.168.77.2:18080/','http://192.168.77.1:18081/','http://192.168.77.2:18081/','http://192.168.77.2:19000/')),'private endpoint restriction')
        source=f'''import json,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect prohibited')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({{}}),NoRedirect())
request=urllib.request.Request({url!r},data={None if body is None else json.dumps(body).encode()!r},headers={{'Content-Type':'application/json'}})
with opener.open(request,timeout={timeout}) as response:
 raw=response.read(2097153)
 if len(raw)>2097152:raise RuntimeError('control evidence bound')
 result=json.loads(raw)
'''
        return self.py(node,source,timeout+5)
    def token(self):
        self.request_serial+=1
        return self.case_id+':'+self.run_id+':q'+str(self.request_serial)
    def verify_receipt(self,root,method,request,result):
        need(isinstance(result,dict) and isinstance(result.get('receipt'),dict),'missing typed receiver receipt')
        receipt=result['receipt'];expected=self.roots[root].get('identity')
        need(receipt.get('run_id')==self.run_id and receipt.get('case_id')==self.case_id and receipt.get('request')==request,'receiver correlation mismatch')
        need(expected is None or receipt.get('root')==expected['root'],'receiver root mismatch')
        phases={'prepare':'prepared','inspect':'observed','arm':'armed','cancel':'canceled','transaction':'transaction-finished','foreground':'foreground-done','release':'gate-released','cleanup':'cleanup'}
        need(method in phases and isinstance(receipt.get('now'),int) and receipt.get('phase')==phases[method],'receiver phase/clock mismatch')
        self.event('receiver-receipt',root=root,method=method,receipt=receipt)
        if method in ('arm','cancel','transaction','foreground'):
            self.trace_entered=True
        return result['value']
    def op(self, root, method, args=None, node=None):
        self.control_calls+=1;need(self.control_calls<=1200,'control request bound')
        node=node or self.roots[root]['node'];args=dict(args or {})
        if method=='identity':return self.http(2,f'http://192.168.77.{node}:18080/op',{'root':root,'method':method,'args':args})
        request=args.setdefault('request',self.token());self.dispatch_attempted=True
        result=self.http(2,f'http://192.168.77.{node}:18080/op',{'root':root,'method':method,'args':args})
        if method=='probeAlarm':
            need(result.get('request')==request and isinstance(result.get('rejected'),bool),'uncorrelated public RPC probe')
            self.event('ordinary-alarm-rpc-outcome',root=root,outcome=result)
            return result
        return self.verify_receipt(root,method,request,result)
    def store(self): return self.http(1,'http://192.168.77.2:19000/__state')
    def control(self, mode):
        need(mode=='release','alarm wave permits store release only; no persistence fault profile')
        value=self.http(1,'http://192.168.77.2:19000/__control',{'mode':mode,'match':'.ltx'})
        self.event('store-control',mode=mode); return value
    def wait(self, fn, description, timeout=15):
        end=min(self.deadline,time.monotonic()+timeout)
        while time.monotonic()<end:
            result=fn()
            if result: return result
            time.sleep(.2)
        raise ObservationTimeout('barrier deadline: '+description)
    def process(self,node,pid,sha256=None):
        result=self.py(node,f'''import pathlib,hashlib,os,json
p=pathlib.Path('/proc')/str({pid});fields=(p/'stat').read_text().rsplit(')',1)[1].split()
if fields[0]=='Z':raise RuntimeError('zombie process')
exe=(p/'exe').resolve(strict=True)
result={{'pid':{pid},'exe':str(exe),'start_ticks':fields[19],'sha256':hashlib.sha256((p/'exe').read_bytes()).hexdigest()}}
''')
        if sha256: need(result['sha256']==sha256,'process executable digest mismatch')
        return result
    def preflight(self):
        source_pins=json.loads((HERE/'source-pins.json').read_text())
        for item in source_pins['sources']:
            need(digest(PROJECT/item['path'])==item['sha256'],'trusted control/source changed: '+item['path'])
        selected=source_pins['runtimes'][self.runtime_label]
        manifest=PROJECT/selected['manifest']
        need(digest(manifest)==selected['manifest_sha256'],'runtime manifest changed')
        frozen=json.loads(manifest.read_text())
        need(frozen['binary_sha256']==self.binary,'runtime manifest binary mismatch')
        for item in selected['contracts']:
            need(digest(PROJECT/item['path'])==item['sha256'],'selected contract source changed: '+item['path'])
            need(frozen['source_hashes'][item['key']]==item['sha256'],'source-to-binary relationship mismatch')
        self.frozen_runtime_manifest_sha256=digest(manifest)
        for guest in self.guests:
            argv=pathlib.Path('/proc',str(guest.p.pid),'cmdline').read_bytes().split(b'\0')
            argv=[x.decode() for x in argv if x]
            need('-m' in argv and argv[argv.index('-m')+1] in ('768','768M'),'QEMU768MiB RAM bound not observed')
            need('-smp' in argv and argv[argv.index('-smp')+1] in ('1','cpus=1'),'QEMU1vCPU bound not observed')
            self.event('qemu-limits',node=guest.node,memory_mib=768,vcpus=1)
        for node in (1,2):
            result=self.py(node,f'''import pathlib,hashlib,os,json
import signal
if not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal'):raise RuntimeError('verified pidfd signal hook unavailable')
root=pathlib.Path({STAGE!r})
files={{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['fixture.js','wrangler.jsonc','http_jobs.py']}}
pid=int(pathlib.Path({self.prefix+'-'+str(node)+'.pid'!r}).read_text())
process=pathlib.Path('/proc')/str(pid)
env=dict(part.split(b'=',1) for part in (process/'environ').read_bytes().split(b'\\0') if b'=' in part)
if env.get(b'AWS_ACCESS_KEY_ID')!=b'test-only' or env.get(b'AWS_SECRET_ACCESS_KEY')!=b'test-only' or env.get(b'AWS_ALLOW_HTTP')!=b'true':raise RuntimeError('runtime is not using fixture-only store credentials')
argv=(process/'cmdline').read_bytes().decode().split(chr(0));argv=[x for x in argv if x]
expected_argv=['/stage/direct/celld','--no-control-plane','--bucket',{self.bucket!r},'--endpoint','http://192.168.77.2:19000','--region','us-east-1','--listen','0.0.0.0:18080','--internal-listen','0.0.0.0:18081','--advertise',{f'192.168.77.{node}:18081'!r}]
if argv!=expected_argv:raise RuntimeError('runtime argv does not match owned private bucket/profile')
selected={{key:env.get(key.encode(),b'').decode() for key in ['CELLD_DURABILITY','CELLD_NODE','CELLD_WATCH','CELLD_TTL_MS','CELLD_TOKIO_THREADS','CELLD_ACTIVATIONS','CELLD_REBALANCE_INTERVAL_MS']}}
cgline=next(x for x in pathlib.Path('/proc/self/cgroup').read_text().splitlines() if x.startswith('0::'))
cgroup=pathlib.Path('/sys/fs/cgroup')/cgline[3:].lstrip('/')
limits={{key:(cgroup/key).read_text().strip() for key in ['pids.max','memory.max','cpu.max']}}
if cgline not in (process/'cgroup').read_text().splitlines():raise RuntimeError('runtime not in inherited bounded control cgroup')
result={{'files':files,'pid':pid,'env':selected,'limits':limits,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'private_bucket_argv_verified':True,'fixture_credentials_verified':True}}
''')
            need(result['files']=={n:digest(HERE/n) for n in ('fixture.js','wrangler.jsonc','http_jobs.py')},'deployed file hash mismatch')
            limits=result['limits']
            need(limits['pids.max'].isdigit() and 1<=int(limits['pids.max'])<=128,'guest inherited PID bound missing')
            need(limits['memory.max'].isdigit() and 1<=int(limits['memory.max'])<=536870912,'guest inherited memory bound missing')
            quota,period=limits['cpu.max'].split(); need(quota.isdigit() and int(quota)<=2*int(period),'guest inherited CPU bound missing')
            env=result['env']; expected={'CELLD_DURABILITY':'bucket','CELLD_NODE':f'aes-{self.run_id}-{node}-0','CELLD_WATCH':f'{self.prefix}-{node}-0','CELLD_TTL_MS':'30000','CELLD_TOKIO_THREADS':'2','CELLD_ACTIVATIONS':'2','CELLD_REBALANCE_INTERVAL_MS':'3600000'}
            need(env==expected,'runtime profile/environment mismatch')
            self.runtime[node]={'identity':self.process(node,result['pid'],self.binary),'node':env['CELLD_NODE'],'generation':0}
            self.event('runtime-preflight',node=node,record=result,process=self.runtime[node]['identity'])
            health=self.http(2,f'http://192.168.77.{node}:18080/health'); need(health.get('profile')=='alarm-event-stress-v1','fixture health mismatch')
            self.http(node,f'http://192.168.77.{node}:18081/rebalance/pause',{});self.event('initial-rebalance-paused',node=node)
        store_hash=next(x['sha256'] for x in source_pins['sources'] if x['path'].endswith('/native-durability/store.py'))
        store_record=self.py(2,f"import pathlib,hashlib;script=pathlib.Path('/stage/native-durability/store.py');pid=int(pathlib.Path({self.prefix+'-store.pid'!r}).read_text());result={{'pid':pid,'script_hash':hashlib.sha256(script.read_bytes()).hexdigest(),'argv':pathlib.Path('/proc',str(pid),'cmdline').read_bytes().decode().split(chr(0))}}")
        need(store_record['script_hash']==store_hash and '/stage/native-durability/store.py' in store_record['argv'],'unverified store executable/script')
        need('--root' in store_record['argv'] and store_record['argv'][store_record['argv'].index('--root')+1]==self.prefix+'-bucket','store root ownership mismatch')
        self.store_identity=self.process(2,store_record['pid']);self.event('store-process',record=self.store_identity)
        need(self.py(2,f"import pathlib;result=pathlib.Path('/proc/self/cgroup').read_text()==pathlib.Path('/proc',{str(store_record['pid'])!r},'cgroup').read_text()"),'store outside inherited bounded workload cgroup')
        state=self.store(); need(state['mode']=='release','store is not initially released')
        need(all(o['key'].startswith(self.bucket+'/') for o in state['objects']),'store contains unowned object keys')
        self.event('store-preflight',events=len(state['events']),objects=len(state['objects']))
        for node in (1,2):
            ready=self.py(node,f"import urllib.request;opener=urllib.request.build_opener(urllib.request.ProxyHandler({{}}));response=opener.open({'http://192.168.77.2:19000/'+self.bucket+'?list-type=2'!r},timeout=5);result={{'status':response.status,'bytes':len(response.read(2097153))}}")
            need(ready['status']==200 and ready['bytes']<=2097152,'cross-guest S3 list readiness failed')
            self.event('s3-list-ready',node=node,evidence=ready)
        self.stage_verified=True
    def root(self,label,node=1):
        need(len(self.roots)<2,'two-root bound')
        root=self.case_id+'-'+self.run_id+'-'+label
        self.roots[root]={'node':node}
        snapshot=self.op(root,'prepare',{'run_id':self.run_id,'case_id':self.case_id});ident=self.op(root,'identity');owner=self.owner(ident['root'])
        need(owner['node']==self.runtime[node]['node'],'initial owner placement not established')
        self.roots[root].update(identity=ident,owner=owner)
        need(snapshot['entries']==[] and snapshot['effects']==[] and snapshot['markers']==[] and snapshot['alarm'] is None,'root not fresh')
        self.event('root-initialized',root=root,node=node,identity=ident,owner=owner)
        return root
    def owner(self,root_id):
        return self.py(2,f'''import pathlib,json
rows=[]
for p in pathlib.Path({self.prefix+'-bucket'!r}).glob('*.json'):
 m=json.loads(p.read_text())
 if m['key'].startswith({self.bucket+'/'!r}) and m['key'].endswith(':'+{root_id!r}+'/own.json'):
  rows.append(json.loads(p.with_suffix('.data').read_bytes()))
if len(rows)!=1:raise RuntimeError('owner record absent or ambiguous')
result=rows[0]
''')
    def batch(self, root, operations, node=None):
        need(self.stage_verified,'preflight incomplete'); need(1<=len(operations)<=16,'batch load bound')
        active=[c for c in self.cohorts if not c.get('terminal')]
        need(len(active)<4 and sum(c['count'] for c in active)+len(operations)<=16,'active HTTP/client-process bound exceeded')
        self.jobs_total+=len(operations); need(self.jobs_total<=128,'case total request bound')
        self.dispatch_attempted=True
        self.serial+=1; label=f'b{self.serial}'; directory=f'{self.prefix}-jobs-{label}'; jobs=[]
        for i,(method,args) in enumerate(operations):
            args=dict(args);args.setdefault('request',self.token())
            jobs.append({'id':f'j{i}','node':node or self.roots[root]['node'],'body':{'root':root,'method':method,'args':args}})
        identity=self.py(2,f'''import json,pathlib,subprocess,os,time
jobpath=pathlib.Path({directory+'.input.json'!r});jobpath.write_text({json.dumps(jobs)!r})
log=open({directory+'.log'!r},'wb')
p=subprocess.Popen(['/stage/native-durability/python/bin/python3.13',{STAGE+'/http_jobs.py'!r},str(jobpath),{directory!r}],stdout=log,stderr=log)
fields=pathlib.Path('/proc',str(p.pid),'stat').read_text().rsplit(')',1)[1].split()
result={{'pid':p.pid,'exe':str(pathlib.Path('/proc',str(p.pid),'exe').resolve()),'start_ticks':fields[19]}}
''')
        cohort={'label':label,'directory':directory,'count':len(jobs),'jobs':jobs,'identity':identity}; self.cohorts.append(cohort)
        self.event('cohort-start',label=label,root=root,operations=operations,identity=identity); return cohort
    def records(self,cohort):
        return self.py(2,f'''import pathlib,json
p=pathlib.Path({cohort['directory']!r})
result={{q.stem:json.loads(q.read_text()) for q in p.glob('j*.json')}} if p.exists() else {{}}
''')
    def finish(self,cohort,success=True,timeout=30):
        values=self.wait(lambda: (r if len(r:=self.records(cohort))==cohort['count'] else None),'client cohort '+cohort['label'],timeout)
        ordered=[values[f'j{i}'] for i in range(cohort['count'])]
        self.event('cohort-original-outcomes',label=cohort['label'],receipts=ordered)
        need(not any('PRECONDITION_GATE_EXPIRED' in str(x) for x in ordered),'fixture gate expired before intended overlap')
        if success: check(all(x.get('status')==200 for x in ordered),{'unexpected_client_failure':ordered})
        for job,record in zip(cohort['jobs'],ordered):
            if record.get('status')==200:
                body=job['body'];self.verify_receipt(body['root'],body['method'],body['args']['request'],record['body'])
        cohort['terminal']=True
        self.event('cohort-finished',label=cohort['label'],receipts=ordered); return ordered
    def release(self,root,gates): return self.batch(root,[('release',{'gates':gates})])
    def snapshot(self,root,node=None):
        state=self.op(root,'inspect',node=node)
        need(not any(e['terminal']=='gate-expired' for e in state['entries']),'native handler gate expired before schedule established')
        return state
    def alarm_entry(self,root,label,retry=0,terminal=None,timeout=20,optional=False):
        def observed():
            state=self.snapshot(root)
            entries=[e for e in state['entries'] if e['label']==label and e['retry']==retry and (terminal is None or e['terminal']==terminal)]
            if entries:return (state,entries[-1])
        try:state,entry=self.wait(observed,'native event '+label+' retry '+str(retry),timeout)
        except ObservationTimeout:
            if optional:return None
            raise
        need(state['root']==self.roots[root]['identity']['root'],'native entry root changed')
        receipt={'root':state['root'],'run_id':self.run_id,'case_id':self.case_id,'entry':entry}
        self.event('native-alarm-entry',receipt=receipt);self.trace_entered=True
        check(entry['is_retry']==int(retry>0),'native retry metadata inconsistent')
        return entry
    def before_due(self,root,due,margin=250):
        state=self.snapshot(root);self.event('pre-due-window',root=root,due=due,clock=state['now'])
        need(state['now']+margin<due and not state['entries'],'pre-due schedule observation window missed')
        return state
    def after_due(self,root,due,slack=3000):
        end=min(self.deadline,time.monotonic()+135)
        while time.monotonic()<end:
            state=self.snapshot(root)
            if state['now']>=due+slack:return state
            time.sleep(.4)
        raise Blocked('guest clock did not reach bounded due observation window')
    def settled(self,root,labels,timeout=20):
        wanted=set(labels)
        def observed():
            state=self.snapshot(root)
            return state if state['alarm'] is None and not state['active'] and all(any(e['label']==label and e['terminal']=='success' for e in state['entries']) for label in wanted) else None
        return self.wait(observed,'all requested native handlers settled',timeout)

    def stop_runtime(self,node):
        expected=self.runtime[node]['identity']; current=self.process(node,expected['pid'],self.binary); need(current==expected,'runtime PID identity changed before fault')
        result=self.py(node,f'''import pathlib,os,signal,time,hashlib
expected={expected!r};fd=os.pidfd_open(expected['pid']);p=pathlib.Path('/proc')/str(expected['pid']);fields=(p/'stat').read_text().rsplit(')',1)[1].split()
if fields[19]!=expected['start_ticks'] or hashlib.sha256((p/'exe').read_bytes()).hexdigest()!=expected['sha256']:raise RuntimeError('signal identity mismatch')
# Only this exact verified disposable runtime is terminated, never a pidfile substitution.
signal.pidfd_send_signal(fd,signal.SIGKILL);os.close(fd)
for _ in range(100):
 if not p.exists() or (p/'stat').read_text().rsplit(')',1)[1].split()[0]=='Z':break
 time.sleep(.05)
else:raise RuntimeError('runtime exit deadline')
result={{'terminated':expected,'exited':True}}
''')
        self.event('runtime-stopped',node=node,result=result)
    def start_runtime(self,node):
        previous=self.runtime[node]; generation=previous['generation']+1
        name=f'aes-{self.run_id}-{node}-{generation}'; directory=f'{self.prefix}-{node}-{generation}'
        result=self.py(node,f'''import pathlib,subprocess,os,hashlib
binary=pathlib.Path('/stage/direct/celld')
if hashlib.sha256(binary.read_bytes()).hexdigest()!={self.binary!r}:raise RuntimeError('binary changed')
state=pathlib.Path({directory!r})
if state.exists():raise RuntimeError('replacement state must be fresh')
state.mkdir()
env=os.environ.copy();env.update(CELLD_DURABILITY='bucket',CELLD_TTL_MS='30000',CELLD_TOKIO_THREADS='2',CELLD_ACTIVATIONS='2',CELLD_REBALANCE_INTERVAL_MS='3600000',CELLD_WATCH=str(state),CELLD_NODE={name!r},AWS_ACCESS_KEY_ID='test-only',AWS_SECRET_ACCESS_KEY='test-only',AWS_ALLOW_HTTP='true',RUST_LOG='info')
log=open({self.prefix+'-'+str(node)+'.log'!r},'ab')
args=[str(binary),'--no-control-plane','--bucket',{self.bucket!r},'--endpoint','http://192.168.77.2:19000','--region','us-east-1','--listen','0.0.0.0:18080','--internal-listen','0.0.0.0:18081','--advertise',{f'192.168.77.{node}:18081'!r}]
p=subprocess.Popen(args,env=env,stdout=log,stderr=log)
pathlib.Path({self.prefix+'-'+str(node)+'.pid'!r}).write_text(str(p.pid))
result={{'pid':p.pid}}
''')
        self.runtime[node]={'identity':self.process(node,result['pid'],self.binary),'node':name,'generation':generation}
        self.helpers.wait_http_ready(self.guests[node-1],PYTHON,f'http://192.168.77.{node}:18080/health',pidfile=f'{self.prefix}-{node}.pid',logfile=f'{self.prefix}-{node}.log',attempts=60,poll_seconds=.2,request_timeout=1,timeout=min(80,self.deadline-time.monotonic()))
        self.http(node,f'http://192.168.77.{node}:18081/rebalance/pause',{})
        self.event('runtime-restarted',node=node,runtime=self.runtime[node])
    def restart(self,roots,all_nodes=True,target=2,release_store_after_stop=False):
        need(self.process(2,self.store_identity['pid'])==self.store_identity,'store process changed before recovery')
        before={root:dict(self.roots[root]) for root in roots}
        nodes=(1,2) if all_nodes else (before[roots[0]]['node'],)
        for root in roots:
            current=self.owner(before[root]['identity']['root']);expected=before[root]['owner']
            need(current['node']==expected['node'] and current['epoch']==expected['epoch'],'owner drift before fault: '+root)
            need(current['node'] in {self.runtime[node]['node'] for node in nodes},'selected fault does not target current owner')
            self.event('owner-reverified-before-fault',root=root,owner=current)
        for node in nodes:self.stop_runtime(node)
        if release_store_after_stop:self.control('release')
        self.event('lease-expiry-wait',seconds=35); time.sleep(35)
        if all_nodes:
            for node in nodes:self.start_runtime(node)
        for root in roots:
            ident=self.op(root,'identity',node=target); owner=self.owner(ident['root'])
            check(ident['root']==before[root]['identity']['root'] and ident['isolate']!=before[root]['identity']['isolate'],'identity did not cold restore')
            check(owner['epoch']>before[root]['owner']['epoch'],'owner epoch did not advance')
            check(owner['node']==self.runtime[target]['node'],'relocation not on intended live process')
            self.roots[root].update(identity=ident,owner=owner,node=target)
            self.event('restored-root',root=root,identity=ident,owner=owner)
        if not all_nodes:
            for node in nodes:self.start_runtime(node)
        need(self.process(2,self.store_identity['pid'])==self.store_identity,'store did not survive runtime recovery')
    def cleanup(self,force=False):
        """Signal all verified owned guests before waiting; every wait has a timeout.

        The outer BaseException deadline cannot be swallowed by these ordinary
        failure handlers. A deadline enters a separate <=4s forced reap attempt.
        """
        outcome={'status':'ok','guests':[],'errors':[],'started_utc':utc(),'forced':force}
        if not self.cleanup_authorized:return {'status':'not-authorized-no-action','started_utc':utc(),'finished_utc':utc()}
        if self.stage_verified and not force:
            self.cleanup_deadline=time.monotonic()+28
            for root in self.roots:
                try:self.op(root,'cleanup')
                except Exception as error:outcome['errors'].append('fixture cleanup: '+repr(error))
            try:self.control('release')
            except Exception as error:outcome['errors'].append('store release: '+repr(error))
        signaled=[]
        for guest,expected in zip(self.guests,self.qemu):
            try:
                if guest.p.poll() is None:
                    need(host_identity(guest)==expected,'QEMU identity changed; cleanup signal refused')
                    os.killpg(guest.p.pid,signal.SIGKILL if force else signal.SIGTERM)
                signaled.append((guest,expected))
            except ProcessLookupError:signaled.append((guest,expected))
            except Exception as error:outcome['errors'].append(repr(error))
        if not force:
            grace=time.monotonic()+10
            for guest,_ in signaled:
                try:guest.p.wait(timeout=max(0,grace-time.monotonic()))
                except subprocess.TimeoutExpired:pass
        # Both guests got TERM before either grace wait. Escalate only verified survivors.
        for guest,expected in signaled:
            try:
                if guest.p.poll() is None:
                    need(host_identity(guest)==expected,'QEMU identity changed before escalation')
                    os.killpg(guest.p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            except Exception as error:outcome['errors'].append(repr(error))
        for guest,_ in signaled:
            try:
                guest.p.wait(timeout=2)
                outcome['guests'].append({'pid':guest.p.pid,'returncode':guest.p.returncode,'reaped':guest.p.poll() is not None})
            except Exception as error:outcome['errors'].append(repr(error))
            finally:
                if not guest.log.closed:guest.log.close()
        if outcome['errors'] or len(outcome['guests'])!=2 or not all(x['reaped'] for x in outcome['guests']):outcome['status']='FAILED'
        outcome['finished_utc']=utc();return outcome

def run_case(guests,guard,case_id):
    """One case, already-owned Guest objects, no launch/deployment fallback."""
    specification=importlib.util.spec_from_file_location('aes_cases',HERE/'cases.py');cases=importlib.util.module_from_spec(specification);specification.loader.exec_module(cases)
    report={'id':case_id,'status':'BLOCKED','traceEntered':False,'profile':'bucket','started_utc':utc(),'source_pins_sha256':digest(HERE/'source-pins.json'),'binary_sha256':guard.get('binary_sha256'),'runtime':guard.get('runtime'),'implementation_hashes':pins(),'guard_sha256':hashlib.sha256(json.dumps(guard,sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    # Preserve an allocated object if fallible __init__ fails after ownership transfer.
    driver=Driver.__new__(Driver);driver.cleanup_authorized=False;driver.trace_entered=False;driver.events=[]
    alarm=False;previous_alarm=None;previous_term=None
    try:
        need(case_id in cases.CASES,'unknown case')
        need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'existing supervisor alarm cannot be replaced')
        def expired(*_):raise CaseDeadline('absolute supervised deadline')
        def terminate(*_):raise ShutdownRequested('supervisor SIGTERM requested bounded teardown')
        previous_alarm=signal.getsignal(signal.SIGALRM);previous_term=signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGALRM,expired);signal.signal(signal.SIGTERM,terminate);signal.setitimer(signal.ITIMER_REAL,360);alarm=True
        driver.__init__(guests,guard,case_id)
        driver.preflight();report['case_started_utc']=utc()
        report['evidence']=cases.CASES[case_id](driver)
        need(driver.trace_entered,'case returned without correlated trace-entry receipt')
        report['status']='PASS'
    except Blocked as error:report['error']=str(error)
    except ControlStop as error:report.update(status='FAIL' if driver.trace_entered else 'BLOCKED',error=repr(error))
    except Exception as error:report.update(status='FAIL' if driver.trace_entered else 'BLOCKED',error=repr(error))
    finally:
        report['case_finished_utc']=utc()
        if alarm:
            signal.setitimer(signal.ITIMER_REAL,0)
            # We are already cleaning up. A repeated SIGTERM records cancellation without
            # interrupting the finite all-guest signal/reap path.
            signal.signal(signal.SIGTERM,lambda *_:report.update(termination_during_cleanup=True))
        report['traceEntered']=driver.trace_entered;report['dispatch_attempted']=getattr(driver,'dispatch_attempted',False)
        report['dispatch_unconfirmed']=report['dispatch_attempted'] and not driver.trace_entered
        report['verified_frozen_runtime_manifest_sha256']=getattr(driver,'frozen_runtime_manifest_sha256',None)
        report['events']=driver.events;report['cleanup_started_utc']=utc()
        try:
            if alarm:signal.setitimer(signal.ITIMER_REAL,35)
            report['cleanup']=driver.cleanup()
        except (ControlStop,Exception) as error:
            if alarm:signal.setitimer(signal.ITIMER_REAL,0)
            # No guest control requests here: signal both verified survivors first,
            # then at most2s reap per guest. Preserve primary cleanup failure.
            try:emergency=driver.cleanup(force=True)
            except Exception as secondary:emergency={'status':'FAILED','error':repr(secondary)}
            report['cleanup']={'status':'FAILED','error':repr(error),'emergency':emergency}
        finally:
            if alarm:signal.setitimer(signal.ITIMER_REAL,0)
        report['cleanup_finished_utc']=utc()
        if report['cleanup']['status']!='ok':report['status']='BLOCKED';report['qualification']='CLEANUP_NOT_QUALIFIED'
        if previous_alarm is not None:signal.signal(signal.SIGALRM,previous_alarm)
        if previous_term is not None:signal.signal(signal.SIGTERM,previous_term)
        report['finished_utc']=utc()
    return report
