"""Run immutable authored Python schedules with process-backed driver methods."""
import concurrent.futures,importlib.util,json,os,time,traceback,urllib.error
from pathlib import Path
from common import ROOT,dump,result,safe_id
from runtime import fetch
from .topology import stage,require_response
from .fleet import Fleet

def module(path):
 spec=importlib.util.spec_from_file_location('phase2_'+str(path).replace('/','_'),path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class ProcessDriver:
 def __init__(self,fleet,case):
  self.fleet=fleet;self.case_id=case['selector'];self.run_id=os.urandom(8).hex();self.events=[];self.roots={};self.cohorts=[];self.jobs_total=0;self.serial=0;self.request_serial=0;self.control_calls=0;self.trace_entered=False;self.dispatch_attempted=False;self.stage_verified=True;self.case_seconds=240 if case['corpus_wave']=='durable-recovery-stress' else 360;self.deadline=time.monotonic()+self.case_seconds;self.runtime={n:{'node':f'suite-node-{n-1}'} for n in range(1,6)};self.pool=concurrent.futures.ThreadPoolExecutor(max_workers=16);self.alarm=case['corpus_wave']=='alarm-event-stress';self.bucket=fleet.bucket
 def prerequisite(self,value,detail):
  if not value:raise AssertionError(detail)
 def event(self,kind,**data):self.events.append({'kind':kind,'driver_monotonic':time.monotonic(),'driver_unix_ms':int(time.time()*1000),**data})
 def wait(self,fn,description,timeout=15,poll=.15):
  end=min(self.deadline,time.monotonic()+timeout)
  while time.monotonic()<end:
   value=fn()
   if value:return value
   time.sleep(poll)
  # Original alarm optional branch catches the original exception type.
  if hasattr(self,'timeout_type'):raise self.timeout_type(description)
  raise AssertionError('bounded observation timeout: '+description)
 def http(self,node,url,body=None,timeout=12):
  import re
  target=int(re.search(r'192\.168\.77\.(\d)',url)[1]);return require_response(self.fleet.req(target-1,{'path':'/'+url.split('/',3)[-1],'json':body,'timeout':timeout}))
 def response(self,root,method,args=None,node=None):
  self.control_calls+=1;self.prerequisite(self.control_calls<=1600,'control bound')
  return self.fleet.req((node or self.roots[root]['node'])-1,{'path':'/op','json':{'root':root,'method':method,'args':args or {}},'timeout':15})
 def op(self,root,method,args=None,node=None):
  args=dict(args or {});request=args.setdefault('request',self.token()) if self.alarm else None
  value=require_response(self.response(root,method,args,node))
  if self.alarm and method not in ('identity','probeAlarm'):return self.verify_receipt(root,method,request,value)
  return value
 def owner(self,id):return self.fleet.owner(id)
 def root(self,label,node=1):
  name=self.case_id+'-'+self.run_id+'-'+label;self.roots[name]={'node':node}
  self.op(name,'prepare',{'run_id':self.run_id,'case_id':self.case_id} if self.alarm else {})
  ident=self.op(name,'identity');owner=self.owner(ident['root']);self.prerequisite(owner['node']==self.runtime[node]['node'],'initial owner differs from process witness')
  self.roots[name].update(identity=ident,owner=owner);self.event('root-initialized',root=name,identity=ident,owner=owner);return name
 def batch(self,root,operations,node=None):
  self.prerequisite(self.stage_verified,'preflight incomplete');self.prerequisite(1<=len(operations)<=16,'batch bound');active=[c for c in self.cohorts if not c.get('terminal')];self.prerequisite(len(active)<4 and sum(c['count'] for c in active)+len(operations)<=16,'active HTTP/client-process bound exceeded');self.jobs_total+=len(operations);self.prerequisite(self.jobs_total<=128,'total jobs bound');self.dispatch_attempted=True
  jobs=[];futures=[]
  for method,args in operations:
   args=dict(args)
   if self.alarm:args.setdefault('request',self.token())
   jobs.append({'root':root,'method':method,'args':args,'body':{'root':root,'method':method,'args':args}});futures.append(self.pool.submit(self.response,root,method,args,node))
  cohort={'label':str(len(self.cohorts)),'jobs':jobs,'futures':futures,'count':len(jobs)};self.cohorts.append(cohort);self.event('concurrent-dispatch',label=cohort['label'],jobs=jobs);return cohort
 def records(self,cohort):
  values={}
  for i,f in enumerate(cohort['futures']):
   if f.done():
    try:values['j'+str(i)]=f.result()
    except Exception as e:values['j'+str(i)]={'status':None,'error':str(e)}
  return values
 def finish(self,cohort,success=True,timeout=30):
  values=self.wait(lambda:(v if len(v:=self.records(cohort))==cohort['count'] else None),'cohort '+cohort['label'],timeout);rows=[values['j'+str(i)] for i in range(cohort['count'])];cohort['terminal']=True
  if success:self.prerequisite(all(r.get('status')==200 for r in rows),rows)
  if self.alarm:
   for job,row in zip(cohort['jobs'],rows):
    if row.get('status')==200:self.verify_receipt(job['root'],job['method'],job['args']['request'],row['body'])
  self.event('cohort-terminal',rows=rows);return rows
 def store(self):return {'events':list(self.fleet.events),'effects':list(self.fleet.effects)}
 def control(self,mode):
  for p in self.fleet.proxies.values():p.set(mode)
  self.event('store-control',mode=mode)
 def logged(self,root,kind,requests):
  n=self.roots[root]['node']-1;tokens=['DRS_'+kind+' '+self.roots[root]['identity']['root']+' '+v for v in requests]
  self.wait(lambda:all(t in (self.fleet.out/f'node-{n}-{self.fleet.generation[n]}.log').read_text() for t in tokens),'native '+kind+' barrier')
 def restart(self,roots,all_nodes=True,target=2,release_store_after_stop=False):
  before={r:dict(self.roots[r]) for r in roots};nodes=list(self.fleet.nodes) if all_nodes else sorted({before[r]['node']-1 for r in roots})
  for root,old in before.items():
   self.prerequisite(self.owner(old['identity']['root'])==old['owner'],'owner drift before SIGKILL')
  for n in nodes:self.fleet.stop_node(n,True)
  if release_store_after_stop:self.control('release')
  time.sleep(5)
  if all_nodes:
   # Start the demand target first; preserve fresh empty data directories.
   self.fleet.start(target-1)
  for root,old in before.items():
   ident=self.wait(lambda:self.op(root,'identity',node=target),'cold identity',30);owner=self.owner(ident['root'])
   self.prerequisite(ident['root']==old['identity']['root'] and ident['isolate']!=old['identity']['isolate'],'cold identity did not change isolate')
   self.prerequisite(owner['epoch']>old['owner']['epoch'] and owner['node']==self.runtime[target]['node'],'cold epoch/owner mismatch')
   self.roots[root].update(identity=ident,owner=owner,node=target);self.event('cold-restoration',root=root,before=old,identity=ident,owner=owner)
  for n in nodes:
   if n not in self.fleet.nodes:self.fleet.start(n)
 def close(self):
  self.control('release');self.pool.shutdown(wait=True,cancel_futures=True)

def run_group(cases,runtimes,out):
 out.mkdir(parents=True,exist_ok=True);wave=cases[0]['corpus_wave'];source=stage(ROOT/cases[0]['fixture'],out,wave);original=module(source/'driver.py');schedules=module(source/'cases.py');rows=[]
 Driver=type('ReviewedProcessDriver',(ProcessDriver,original.Driver),{'root':original.Driver.root,'finish':original.Driver.finish})
 for case in cases:
  for runtime in runtimes:
   if runtime=='workerd':
    rows.append(result(case,runtime,'not-applicable','celld-specific bucket ownership, lease epochs and dead-owner recovery have no stock workerd fleet implementation'));continue
   directory=out/safe_id(case['selector']);fleet=None;driver=None;t=time.monotonic();art=directory/'observation.json'
   try:
    fleet=Fleet.__new__(Fleet);fleet.__init__(source,directory);driver=Driver(fleet,case);fleet.guard.begin(case['id'],driver.case_seconds)
    if hasattr(original,'ObservationTimeout'):driver.timeout_type=original.ObservationTimeout
    value=schedules.CASES[case['selector']](driver);dump(art,{'result':value,'events':driver.events});status='pass';reason='unchanged authored schedule/oracles passed with live process/store witnesses'
   except Exception as e:
    dump(art,{'error':str(e),'traceback':traceback.format_exc(),'events':driver.events if driver else []});status='fail';reason=str(e)[:700]
   finally:
    if driver:driver.close()
    if fleet:fleet.close()
   if fleet and fleet.guard.violations:status='fail';reason='independent resource/deadline guard rejected qualification'
   rows.append(result(case,runtime,status,reason,int((time.monotonic()-t)*1000),[art,directory/'fleet.json',directory/'resource-guard.json',out/'staging.json']));print(status,runtime,case['id'],flush=True)
 return rows
