"""Owned process watchdog, with kernel descendant limits for source campaigns."""
import os,signal,threading,time,subprocess,json,shutil,hashlib,sys
from pathlib import Path
from common import ROOT,dump
class Guard:
 def __init__(self,out,profile=None):
  self.out=out;out.mkdir(parents=True,exist_ok=True);self.profile=profile or {};self.started=time.monotonic();self.entries={};self.violations=[];self.active=None;self.lock=threading.Lock();self.done=threading.Event();self.samples=0;self.largest_gap=0;self.previous=self.started;self.finished=None;self.cgroup=None;self.discovered={};self.peak_disk=0;self.peak_rss=0;self.peak_processes=0;self.last_disk=0
  if profile:
   import ctypes
   assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0,'subreaper setup failed'
   self.unit='celld-tests-20261010-'+str(os.getpid())+'-'+str(time.monotonic_ns())
   mountpoint=out/'working';mountpoint.mkdir();keeper=Path(__file__).with_name('quota-keeper.py')
   args=['systemd-run','--user','--quiet','--unit='+self.unit,'--property=Delegate=yes','--property=MemoryMax='+str(profile['rss_bytes']),'--property=MemorySwapMax=0','--property=CPUQuota=100%','--property=TasksMax='+str(max(128,profile.get('pids',128))),'/usr/bin/unshare','--user','--map-root-user','--mount',sys.executable,str(keeper),str(mountpoint),str(profile['disk_bytes']),str(ROOT)]
   subprocess.run(args,check=True,capture_output=True,timeout=10)
   props=subprocess.check_output(['systemctl','--user','show',self.unit,'-p','ControlGroup','-p','MainPID','-p','MemoryMax','-p','MemorySwapMax','-p','TasksMax','-p','CPUQuotaPerSecUSec'],text=True,timeout=10)
   self.kernel_properties=dict(x.split('=',1) for x in props.splitlines());self.cgroup=Path('/sys/fs/cgroup')/self.kernel_properties['ControlGroup'].lstrip('/');self.holder=int(self.kernel_properties['MainPID'])
   assert int((self.cgroup/'memory.max').read_text())==profile['rss_bytes']
   assert (self.cgroup/'memory.swap.max').read_text().strip()=='0'
   assert int((self.cgroup/'pids.max').read_text())==max(128,profile.get('pids',128))
   quota,period=map(int,(self.cgroup/'cpu.max').read_text().split());assert quota<=period
   self.workspace=Path('/proc')/str(self.holder)/'root'/str(mountpoint).lstrip('/')
   end=time.monotonic()+10
   while True:
    try:
     if (self.workspace/'.quota-ready').exists():break
    except (PermissionError,FileNotFoundError):pass # unshare temporarily changes dumpability before exec
    if time.monotonic()>end:raise RuntimeError('owned filesystem quota startup failed')
    time.sleep(.02)
   fs=os.statvfs(self.workspace);assert fs.f_blocks*fs.f_frsize<=profile['disk_bytes']
   self.filesystem={'kind':'private unprivileged mount-namespace tmpfs','maximum_bytes':fs.f_blocks*fs.f_frsize,'mountpoint':str(mountpoint),'access_path':str(self.workspace),'keeper_pid':self.holder}
   self.kernel_start=self.kernel_stats()
  self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
 def environment(self,env):return {**env,**({'CELLD_TEST_CGROUP':str(self.cgroup),'CELLD_TEST_NAMESPACE':str(self.holder),'GOMAXPROCS':'2','TMPDIR':str(self.workspace)} if self.cgroup else {})}
 def kernel_stats(self):
  value={}
  for name in ['memory.current','memory.peak','memory.events','cpu.stat','pids.current','pids.events']:
   value[name]=(self.cgroup/name).read_text().strip()
  return value
 def register(self,name,process,rss_mib=1024,log_mib=16):
  row={'process':process,'rss_limit_bytes':rss_mib*1024**2,'log_limit_bytes':log_mib*1024**2,'peak_rss_bytes':0,'peak_log_bytes':0,'samples':0,'pid':process.p.pid}
  try:
   stat=(Path('/proc')/str(process.p.pid)/'stat').read_text().rsplit(')',1)[1].split();row.update(start_ticks=int(stat[19]),peak_rss_bytes=int(stat[21])*os.sysconf('SC_PAGE_SIZE'),peak_log_bytes=process.log.stat().st_size,samples=1)
  except FileNotFoundError:pass
  with self.lock:self.entries[name]=row
 def begin(self,case,seconds):
  with self.lock:self.active={'case':case,'seconds':seconds,'started_monotonic':time.monotonic(),'deadline':time.monotonic()+seconds}
 def end(self):
  with self.lock:self.active=None
 def members(self):return [int(x) for x in (self.cgroup/'cgroup.procs').read_text().split() if int(x)!=self.holder]
 def kill(self):
  if self.cgroup:
   for pid in self.members():
    try:os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:pass
  else:
   for row in self.entries.values():
    if row['process'].p.poll() is None:
     try:os.killpg(row['pid'],signal.SIGKILL)
     except ProcessLookupError:pass
 def reject(self,reason):
  if not any(x['reason']==reason for x in self.violations):self.violations.append({'reason':reason,'at_monotonic':time.monotonic(),'case':self.active})
  self.kill()
 def sample(self):
  now=time.monotonic();self.samples+=1;self.largest_gap=max(self.largest_gap,now-self.previous);self.previous=now
  if now-self.started>self.profile.get('wave_seconds',3600) or (self.active and now>self.active['deadline']):self.reject('outer case/group deadline')
  for name,row in self.entries.items():
   p=row['process']
   if p.p.poll() is not None:continue
   try:
    stat=(Path('/proc')/str(p.p.pid)/'stat').read_text().rsplit(')',1)[1].split();tick=int(stat[19]);rss=int(stat[21])*os.sysconf('SC_PAGE_SIZE')
    if 'start_ticks' in row and row['start_ticks']!=tick:raise RuntimeError('owned PID identity changed')
    row.setdefault('start_ticks',tick);row['samples']+=1;row['peak_rss_bytes']=max(row['peak_rss_bytes'],rss);row['peak_log_bytes']=max(row['peak_log_bytes'],p.log.stat().st_size)
    if rss>row['rss_limit_bytes']:self.reject('RSS limit: '+name)
    if row['peak_log_bytes']>row['log_limit_bytes']:self.reject('log limit: '+name)
   except FileNotFoundError:pass
  if self.cgroup:
   members=self.members();rss=0
   for pid in members:
    try:
     stat=(Path('/proc')/str(pid)/'stat').read_text().rsplit(')',1)[1].split();tick=int(stat[19]);current=int(stat[21])*os.sysconf('SC_PAGE_SIZE');rss+=current
     key=str(pid)+':'+str(tick);entry=self.discovered.setdefault(key,{'pid':pid,'start_ticks':tick,'peak_rss_bytes':0,'samples':0,'pgid':int(stat[2])});entry['peak_rss_bytes']=max(entry['peak_rss_bytes'],current);entry['samples']+=1
    except FileNotFoundError:pass
   self.peak_rss=max(self.peak_rss,rss);self.peak_processes=max(self.peak_processes,len(members))
   if len(members)>self.profile.get('pids',128):self.reject('owned process count limit')
   if rss>self.profile['rss_bytes']:self.reject('aggregate RSS limit')
   stats=self.kernel_stats();cpu=dict(x.split() for x in stats['cpu.stat'].splitlines());events=dict(x.split() for x in stats['memory.events'].splitlines());pids=dict(x.split() for x in stats['pids.events'].splitlines())
   if int(events.get('max',0)) or int(events.get('oom',0)) or int(events.get('oom_kill',0)):self.reject('kernel memory limit event')
   if int(pids.get('max',0)):self.reject('kernel task limit event')
   if int(cpu['usage_usec'])>self.profile.get('cpu_seconds',3600)*1000000:self.reject('aggregate CPU time limit')
   if now-self.last_disk>=.2:
    total=0
    for root,dirs,files in os.walk(self.workspace):
     for name in files:
      try:total+=os.lstat(Path(root)/name).st_size
      except FileNotFoundError:pass
    self.last_disk=now;self.peak_disk=max(self.peak_disk,total)
    if total>self.profile['disk_bytes']:self.reject('owned writable bytes limit')
 def loop(self):
  while not self.done.wait(.05):
   with self.lock:
    try:self.sample()
    except Exception as e:self.reject('resource supervision error: '+str(e))
 def finish(self):
  if self.finished:return self.finished
  self.done.set();self.thread.join(2)
  with self.lock:self.sample()
  kernel=None
  if self.cgroup:
   remaining=self.members()
   if remaining:self.reject('owned descendants remained after cleanup')
   end=time.monotonic()+2
   while self.members() and time.monotonic()<end:time.sleep(.02)
   adopted=[]
   children=Path('/proc/self/task')/str(os.getpid())/'children'
   for pid in map(int,children.read_text().split()):
    try:
     if self.kernel_properties['ControlGroup'] in (Path('/proc')/str(pid)/'cgroup').read_text():
      os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);adopted.append(pid)
    except (FileNotFoundError,ProcessLookupError,ChildProcessError):pass
   kernel={'adopted_reaped_pids':adopted,'path':str(self.cgroup),'properties':self.kernel_properties,'start':self.kernel_start,'final':self.kernel_stats(),'remaining_pids':self.members(),'descendants':self.discovered,'peak_aggregate_rss_bytes':self.peak_rss,'peak_processes':self.peak_processes,'peak_owned_writable_bytes':self.peak_disk,'filesystem_policy':'kernel tmpfs capacity plus 200ms logical-size accounting; all generated files use owned quota mount; complete verified archive retained by operator instruction'}
   retained=self.out/'retained';shutil.copytree(self.workspace,retained,symlinks=True)
   manifest={}
   for source in self.workspace.rglob('*'):
    if source.is_file():
     relative=source.relative_to(self.workspace);digest=hashlib.sha256(source.read_bytes()).hexdigest();assert hashlib.sha256((retained/relative).read_bytes()).hexdigest()==digest;manifest[str(relative)]=digest
   kernel['filesystem']={**self.filesystem,'retained':str(retained),'retained_files_sha256':manifest,'preservation':'copy all bytes and verify every hash before releasing private mount namespace; no persistent state deleted'}
   subprocess.run(['systemctl','--user','stop',self.unit],check=True,capture_output=True,timeout=10)
  records={name:{**{k:v for k,v in row.items() if k!='process'},'exit_code':row['process'].p.poll(),'reaped':row['process'].p.poll() is not None} for name,row in self.entries.items()}
  value={'source':'independent Linux procfs sampling; matching owned child PID/start ticks','poll_seconds':.05,'max_sampling_gap_seconds':self.largest_gap,'samples':self.samples,'group_deadline_seconds':self.profile.get('wave_seconds',3600),'elapsed_seconds':time.monotonic()-self.started,'processes':records,'violations':self.violations,'profile':self.profile,'kernel_domain':kernel,'policy':'kernel memory/swap/CPU/task ceiling plus external RSS, disk, CPU-time and deadline supervision; any breach invalidates group qualification' if kernel else 'SIGKILL only owned process groups on RSS/log/deadline breach'}
  dump(self.out/'resource-guard.json',value);self.finished=value;return value
