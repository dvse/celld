"""Private multi-node celld fleet for regressions: fresh MinIO and data under
CELLD_TEST_ARTIFACTS, loopback ports from CELLD_TEST_PORT_BASE.

Tools: CELLD_TEST_MINIO / CELLD_TEST_MC (default: $CELLD_TEST_TOOLS_ROOT/bin,
~/celld-suite-20261010/bin)
and CELLD_ESBUILD. Exit 77 from callers when they are absent."""
import json,os,pathlib,shutil,signal,subprocess,time,urllib.request,urllib.error
TOOLS=pathlib.Path(os.environ.get('CELLD_TEST_TOOLS_ROOT',str(pathlib.Path.home()/'celld-suite-20261010')))/'bin'
MINIO=os.environ.get('CELLD_TEST_MINIO',str(TOOLS/'minio'));MC=os.environ.get('CELLD_TEST_MC',str(TOOLS/'mc'))
ESBUILD=os.environ.get('CELLD_ESBUILD') or shutil.which('esbuild') or ''
def available():
    missing=[n for n,p in [('minio',MINIO),('mc',MC),('esbuild',ESBUILD)] if not p or not pathlib.Path(p).is_file()]
    return None if not missing else 'missing tools: '+', '.join(missing)
class Fleet:
    def __init__(self,binary,fixture,art,names,placement=None,base=9900,env=None,bucket='lab'):
        assert 9700<=base and base+2*len(names)+2<=9949,'ports outside the regression range'
        self.binary=str(binary);self.fixture=pathlib.Path(fixture);self.art=pathlib.Path(art);self.art.mkdir(parents=True,exist_ok=True)
        self.names=names;self.base=base;self.bucket=bucket;self.procs={};self.logs=[]
        self.store_port=base+2*len(names);self.endpoint=f'http://127.0.0.1:{self.store_port}'
        e={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','CELLD_','MINIO_','S3_'))}
        e.update(AWS_ACCESS_KEY_ID='lab-public',AWS_SECRET_ACCESS_KEY='lab-public-password',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',MINIO_ROOT_USER='lab-public',MINIO_ROOT_PASSWORD='lab-public-password',CELLD_TOKIO_THREADS='2',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_SHUTDOWN_TOTAL_MS='5000',RUST_LOG='info',CELLD_ESBUILD=ESBUILD)
        if placement:e['CELLD_PLACEMENT']=json.dumps(placement)
        e.update(env or {});self.env=e
    def public(self,i):return self.base+i
    def internal(self,i):return self.base+len(self.names)+i
    def _start(self,cmd,name,extra=None):
        log=(self.art/(name+'.log')).open('a');self.logs.append(log)
        p=subprocess.Popen(cmd,env={**self.env,**(extra or {})},stdout=log,stderr=subprocess.STDOUT,start_new_session=True);return p
    def start(self):
        (self.art/'store').mkdir(exist_ok=True)
        self.procs['minio']=self._start([MINIO,'server',str(self.art/'store'),'--address',f'127.0.0.1:{self.store_port}','--console-address',f'127.0.0.1:{self.store_port+1}'],'minio')
        for _ in range(300):
            try:urllib.request.urlopen(self.endpoint+'/minio/health/ready',timeout=.3).close();break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('MinIO readiness timeout')
        mc=[MC,'--config-dir',str(self.art/'mc')]
        with (self.art/'setup.log').open('a') as log:
            # The health endpoint can answer before S3 authentication is
            # initialized. Retry only that startup response, within 30 s.
            deadline=time.monotonic()+30
            while True:
                ready=subprocess.run(mc+['alias','set','lab',self.endpoint,'lab-public','lab-public-password'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=5)
                log.write(ready.stdout);log.flush()
                if ready.returncode==0:break
                if 'Server not initialized yet' not in ready.stdout or time.monotonic()>=deadline:ready.check_returncode()
                time.sleep(.1)
            subprocess.run(mc+['mb','-p','lab/'+self.bucket],check=True,stdout=log,stderr=log)
            for script in [p for p in sorted(self.fixture.iterdir()) if p.is_dir() and ((p/'wrangler.json').exists() or (p/'wrangler.jsonc').exists())]+[self.fixture]:
                subprocess.run([self.binary,'deploy',str(script),'--bucket','s3://'+self.bucket,'--endpoint',self.endpoint],env=self.env,check=True,stdout=log,stderr=log)
        for i,n in enumerate(self.names):self.start_node(i)
        for i in range(len(self.names)):self.wait_healthy(i)
    def start_node(self,i):
        n=self.names[i];data=self.art/f'data-{n}';data.mkdir(exist_ok=True)
        self.procs[n]=self._start([self.binary,'--bucket','s3://'+self.bucket,'--endpoint',self.endpoint,'--listen',f'127.0.0.1:{self.public(i)}','--internal-listen',f'127.0.0.1:{self.internal(i)}'],n,{'CELLD_NODE':n,'CELLD_TEST_DATA_DIR':str(data)})
    def wait_healthy(self,i,timeout=60):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            if self.procs[self.names[i]].poll() is not None:raise RuntimeError('node exited '+self.names[i])
            try:urllib.request.urlopen(f'http://127.0.0.1:{self.public(i)}/.well-known/celld/health',timeout=.5).close();return
            except OSError:time.sleep(.1)
        raise RuntimeError('node readiness timeout '+self.names[i])
    def get(self,i,path,timeout=90):
        t=time.monotonic()
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{self.public(i)}{path}',timeout=timeout) as r:body=r.read();status=r.status
        except urllib.error.HTTPError as e:body=e.read();status=e.code
        ms=round((time.monotonic()-t)*1000)
        try:val=json.loads(body)
        except ValueError:val=body.decode(errors='replace')
        return status,val,ms
    def state(self,i):
        with urllib.request.urlopen(f'http://127.0.0.1:{self.internal(i)}/state',timeout=5) as r:return json.load(r)
    def pid(self,name):return self.procs[name].pid
    def rss_kb(self,name):
        for line in open(f'/proc/{self.pid(name)}/status'):
            if line.startswith('VmRSS:'):return int(line.split()[1])
    def log(self,name):return (self.art/(name+'.log')).read_text(errors='replace')
    def stop(self):
        for name in [n for n in self.names if n in self.procs]+(['minio'] if 'minio' in self.procs else []):
            p=self.procs[name]
            if p.poll() is None:
                try:os.killpg(p.pid,signal.SIGTERM)
                except ProcessLookupError:pass
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
        for l in self.logs:l.close()
