"""Owned, bounded subprocesses and stable per-case results; stdlib only."""
from pathlib import Path
import atexit, contextlib, hashlib, json, os, signal, socket, subprocess, time
CHILDREN=[]
ROOT=Path(__file__).resolve().parents[2]
TESTS=ROOT/'tests'
STATUSES=('pass','fail','expected-fail','not-applicable')
def dump(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def safe_id(s):return ''.join(c if c.isalnum() or c in '.-_' else '_' for c in s)
def clean_env():
    # A fixture must never inherit an account credential or paid service endpoint.
    env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('TOKEN','SECRET','PASSWORD','API_KEY','AWS_','AZURE_','GOOGLE_','S3_ENDPOINT'))}
    env.update(CELLD_TOKIO_THREADS='2',CELLD_V8_HEAP_LIMIT_MB='128',CELLD_MAX_RESIDENT_CELLS='16',CELLD_READY_FLEET_GATE_MS='0',CELLD_SHUTDOWN_TOTAL_MS='2000')
    return env
class Process:
    def __init__(self,args,directory,log,env=None,limits=None):
        self.log=Path(log);self.log.parent.mkdir(parents=True,exist_ok=True)
        self.file=self.log.open('wb');self.args=[str(x) for x in args]
        child_env=dict(env or clean_env());cgroup=child_env.pop('CELLD_TEST_CGROUP',None);namespace=child_env.pop('CELLD_TEST_NAMESPACE',None)
        def bound():
            if cgroup:
                with open(cgroup+'/cgroup.procs','w') as f:f.write(str(os.getpid()))
                if hasattr(os,'sched_getaffinity'):os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
            if namespace:
                for kind in ['user','mnt']:
                    fd=os.open('/proc/'+namespace+'/ns/'+kind,os.O_RDONLY)
                    try:os.setns(fd,0)
                    finally:os.close(fd)
                os.chdir(directory)
            if not limits:return
            import resource
            if limits.get('cpus') and hasattr(os,'sched_getaffinity'):
                os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:limits['cpus']]))
            if limits.get('cpu'):resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu'],limits['cpu']))
            if limits.get('memory') and __import__('sys').platform=='linux':resource.setrlimit(resource.RLIMIT_AS,(limits['memory'],limits['memory']))
        self.p=subprocess.Popen(self.args,cwd=directory,env=child_env,stdout=self.file,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=bound if limits or cgroup else None)
        CHILDREN.append(self)
    def stop(self):
        # Only the process group created here. Also continue a frozen child.
        for sig in ([signal.SIGCONT,signal.SIGTERM] if self.p.poll() is None else []):
            try:os.killpg(self.p.pid,sig)
            except ProcessLookupError:pass
        try:self.p.wait(timeout=4)
        except subprocess.TimeoutExpired:
            try:os.killpg(self.p.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            self.p.wait(timeout=4)
        self.file.close()
        if self in CHILDREN:CHILDREN.remove(self)
    def __enter__(self):return self
    def __exit__(self,*args):self.stop()
def command(args,directory,log,timeout=90,env=None,limits=None):
    started=time.monotonic()
    with Process(args,directory,log,env,limits) as p:
        try:code=p.p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:code=124
    return code,round((time.monotonic()-started)*1000)
def result(case,runtime,status,reason,duration=0,artifacts=()):
    assert status in STATUSES
    return dict(id=case['id'],layer=case['layer'],runtime=runtime,status=status,reason=reason,duration_ms=duration,artifacts=[str(x) for x in artifacts if Path(x).exists()])
def reserve_ports():
    # The whole suite is serial; the lock prevents competing suite invocations.
    import fcntl
    path=TESTS/'artifacts'/'.suite.lock';path.parent.mkdir(exist_ok=True)
    f=path.open('a');fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    return f
def port_available(port):
    if not 9800<=port<=9899:raise ValueError('port outside lane range')
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',port))

def stop_children():
    for child in list(CHILDREN):
        try:child.stop()
        except Exception:pass
atexit.register(stop_children)
