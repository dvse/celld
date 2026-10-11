"""Original generation-cutover schedules with real native deploy/reload controls."""
import json,os,time,traceback,urllib.error,urllib.request
from pathlib import Path
from common import ROOT,Process,dump,result,safe_id,sha
from runtime import fetch
from .fleet import Fleet,identity
from .topology import stage
from .recovery import ProcessDriver,module

def run_group(cases,runtimes,out):
 out.mkdir(parents=True,exist_ok=True);source=stage(ROOT/cases[0]['fixture'],out,'deployment-recovery');original=module(source/'driver.py');schedules=module(source/'cases.py')
 scope=dict(original.__dict__);exec(compile('class Operator:\n'+(source/'operator_methods.inc').read_text(),str(source/'operator_methods.inc'),'exec'),scope);Operator=scope['Operator']
 class Driver(ProcessDriver,Operator,original.Driver):
  def __init__(self,fleet,case):super().__init__(fleet,case);self.deployments=[];self.setup_entered=False
  def root(self,*a,**kw):return original.Driver.root(self,*a,**kw)
  def finish(self,*a,**kw):return original.Driver.finish(self,*a,**kw)
  def response(self,root,method,args=None,node=None):
   record=self.roots[root];return self.fleet.req((node or record['node'])-1,{'path':'/op','json':{'root':record['name'],'namespace':record.get('namespace','root'),'method':method,'args':args or {}},'timeout':20})
  def http_response(self,node,url,body,timeout=20):
   import re
   n=int(re.search(r'192\.168\.77\.(\d)',url)[1]);return fetch(9830+n-1,{'path':'/reload','json':body,'timeout':timeout})
  def object(self,key):
   try:raw=self.fleet.s3('GET',key)
   except urllib.error.HTTPError as e:
    if e.code==404:return None
    raise
   return {'sha256':__import__('hashlib').sha256(raw).hexdigest(),'body':raw.decode()}
  def store_control(self,mode,match):
   for p in self.fleet.proxies.values():p.match=match;p.set(mode)
   self.event('publication-control',mode=mode,match=match)
  def launch_deploy(self,version):
   self.prerequisite('/' not in version and (source/'versions'/version).exists(),'known fixture version')
   log=self.fleet.out/f'deploy-{len(self.deployments)}-{version}.log'
   proc=Process([self.fleet.binary,'deploy',source/'versions'/version,'--bucket','s3://'+self.bucket,'--endpoint','http://127.0.0.1:9840'],ROOT,log,self.fleet.env)
   self.fleet.guard.register('deploy-'+str(len(self.deployments)),proc)
   job={'version':version,'process':proc,'identity':identity(proc),'log':log,'started':time.monotonic()};self.deployments.append(job);self.event('deploy-start',version=version,identity=job['identity']);return job
  def deploy_records(self,job):
   p=job['process'].p;code=p.poll()
   if code is None:return None
   return {'exit_code':code,'stderr':job['log'].read_text(),'timed_out':False,'output_truncated':False,'operator_error':None}
  def finish_deploy(self,job,success=True):
   value=self.wait(lambda:self.deploy_records(job),'native deployment terminal receipt',45);job['terminal']=True;job['process'].stop()
   self.prerequisite((value['exit_code']==0)==success,value);self.trace_entered=True
   if success:value['pointer']=self.verify_publication(job['version'])
   self.event('deploy-terminal',version=job['version'],result=value);return value
  def kill_deploy(self,job):
   import signal
   p=job['process'];self.prerequisite(identity(p)==job['identity'],'deploy PID identity changed');os.killpg(p.p.pid,signal.SIGKILL);return self.finish_deploy(job,False)
  def signal_external(self,root,gate):
   token='UPG_RELEASE '+self.roots[root]['identity']['root']+' '+gate
   with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:9840/__effect',data=token.encode()),timeout=3) as r:self.prerequisite(r.status==200,'external gate release')
  def logged(self,root,kind,requests):
   n=self.roots[root]['node']-1;tokens=['UPG_'+kind+' '+self.roots[root]['identity']['root']+' '+v for v in requests]
   self.wait(lambda:all(t in (self.fleet.out/f'node-{n}-{self.fleet.generation[n]}.log').read_text() for t in tokens),'native '+kind+' barrier')
  def alarm_completed(self,root,op,build):
   n=self.roots[root]['node']-1;token='UPG_ALARM '+self.roots[root]['identity']['root']+' '+op+' '+build
   self.wait(lambda:token in (self.fleet.out/f'node-{n}-{self.fleet.generation[n]}.log').read_text(),'alarm completion log',20)
  def close(self):
   for job in self.deployments:
    if not job.get('terminal'):job['process'].stop()
   super().close()
 rows=[]
 for case in cases:
  for runtime in runtimes:
   if runtime=='workerd':rows.append(result(case,runtime,'not-applicable','native celld deploy/current pointer publication, /reload adoption and bucket epoch recovery are outside stock workerd server API'));continue
   directory=out/case['selector'];f=None;d=None;t=time.monotonic();art=directory/'observation.json'
   try:
    f=Fleet.__new__(Fleet);f.__init__(source/'versions/v1',directory);d=Driver(f,case);f.guard.begin(case['id'],d.case_seconds);value=schedules.CASES[case['selector']](d);status='pass';reason='unchanged generation-cutover schedule/oracles passed';dump(art,{'result':value,'events':d.events})
   except Exception as e:
    status='fail';reason=str(e)[:700];dump(art,{'error':str(e),'traceback':traceback.format_exc(),'events':d.events if d else []})
   finally:
    if d:d.close()
    if f:f.close()
   if f and f.guard.violations:status='fail';reason='independent resource/deadline guard rejected qualification'
   rows.append(result(case,runtime,status,reason,int((time.monotonic()-t)*1000),[art,directory/'fleet.json',directory/'resource-guard.json',out/'staging.json']));print(status,runtime,case['id'],flush=True)
 return rows
