"""Five real celld processes, official SeaweedFS and bounded per-node faults."""
import http.client,http.server,json,os,signal,socket,threading,time,urllib.request,urllib.error,xml.etree.ElementTree as ET,hashlib,hmac,datetime,urllib.parse
from pathlib import Path
from common import ROOT,Process,clean_env,command,dump,sha,port_available
from runtime import executable,fetch
BASE=Path.home()/'celld-tests-20261010/phase2'
def identity(proc):
 p=Path('/proc')/str(proc.p.pid);s=(p/'stat').read_text().rsplit(')',1)[1].split()
 return {'pid':proc.p.pid,'start_ticks':int(s[19]),'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'exe_sha256':sha(p/'exe')}
class Proxy:
 def __init__(self,port,out,events=None,effects=None):
  self.mode='release';self.release=threading.Event();self.release.set();self.events=events if events is not None else [];self.effects=effects if effects is not None else [];self.match=".ltx";self.out=out;proxy=self
  class Handler(http.server.BaseHTTPRequestHandler):
   protocol_version='HTTP/1.1'
   def log_message(self,*a):pass
   def request(self):
    start=time.monotonic();mode=proxy.mode;body=self.rfile.read(int(self.headers.get('Content-Length',0)))
    # No auth material or arbitrary object contents enter the journal.
    key=self.path.split('?',1)[0];record={'index':len(proxy.events),'kind':mode,'method':self.command,'key':key,'at':time.time()};proxy.events.append(record)
    if key=='/__state':
     record.update(status=200,duration_ms=int((time.monotonic()-start)*1000));data=json.dumps({'events':proxy.events,'effects':proxy.effects}).encode()
     self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
    if key=='/__effect':
     if self.command=='POST':proxy.effects.append(body.decode());data=b'OK'
     else:data=json.dumps(proxy.effects).encode()
     self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
    selected=proxy.match in key and self.command=='PUT'
    if mode=='cut':self.close_connection=True;self.connection.shutdown(socket.SHUT_RDWR);return
    if mode in ('stall','hold_write') and selected:
     record['kind']='write_held';proxy.release.wait(30)
    try:
     if mode=='429' or (mode=='fail' and selected):
      record['kind']='put_failed';status=429;data=b'<Error><Code>SlowDown</Code></Error>';headers={}
     else:
      c=http.client.HTTPConnection('127.0.0.1',9806,timeout=15);headers={k:v for k,v in self.headers.items() if k.lower()!='connection'}
      c.request(self.command,self.path,body,headers);r=c.getresponse();status=r.status;data=r.read(32*1024*1024);headers={k:v for k,v in r.getheaders() if k.lower() not in ('transfer-encoding','content-length','connection')};c.close()
     if selected and 200<=status<300:
      proxy.events.append({'index':len(proxy.events),'kind':'put_persisted','key':key,'at':time.time()})
      if mode=='hold_ack':
       proxy.events.append({'index':len(proxy.events),'kind':'ack_held','key':key,'at':time.time()});proxy.release.wait(30)
     self.send_response(status)
     for k,v in headers.items():self.send_header(k,v)
     self.send_header('Content-Length',str(len(data)));self.send_header('Connection','close');self.end_headers()
     if self.command!='HEAD':self.wfile.write(data)
     record.update(status=status,duration_ms=int((time.monotonic()-start)*1000))
    except (OSError,TimeoutError) as e:record['error']=type(e).__name__;self.close_connection=True
   do_GET=do_HEAD=do_PUT=do_POST=do_DELETE=request
  port_available(port);self.server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler);self.server.daemon_threads=True;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
 def set(self,mode):
  assert mode in ['release','stall','429','cut','hold_write','hold_ack','fail'];self.mode=mode
  if mode in ('stall','hold_write','hold_ack'):self.release.clear()
  else:self.release.set()
 def close(self):self.set('release');self.server.shutdown();self.server.server_close();self.thread.join(2);dump(self.out,self.events)
class Fleet:
 def __init__(self,source,out,settings=None,width=5,resource_guard=None):
  self.out=out;out.mkdir(parents=True,exist_ok=True);self.nodes={};self.identities={};self.proxies={};self.events=[];self.effects=[];self.generation={};self.store=None;self.binary=executable('celld');self.source=source
  from .guard import Guard
  self.guard=resource_guard or Guard(out)
  self.env=clean_env();self.env.update(AWS_ACCESS_KEY_ID='suite-public-test-only',AWS_SECRET_ACCESS_KEY='suite-public-test-only',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',CELLD_ESBUILD=executable('esbuild'),CELLD_TTL_MS='4000',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_OPERATION_DEADLINE_MS='15000',CELLD_DURABILITY='bucket',CELLD_RECOVERY_RETRY_MS='100',CELLD_WAKER_TICK_MS='200',CELLD_MAX_RESIDENT_CELLS='128',CELLD_SHUTDOWN_TOTAL_MS='5000',CELLD_DEPLOY_POLL_S='3600' if 'versions' in source.parts else '1',CELLD_DEPLOY_MAX_AGE_S='60')
  self.env.update(settings or {})
  self.env=self.guard.environment(self.env)
  self.bucket='phase2-'+os.urandom(8).hex();self.endpoint='http://127.0.0.1:9806'
  for p in range(9800,9809):port_available(p)
  for d in ['data','meta','tmp']:(out/d).mkdir()
  auth=out/'s3-auth.json';dump(auth,{'identities':[{'name':'phase2-fixture','credentials':[{'accessKey':'suite-public-test-only','secretKey':'suite-public-test-only'}],'actions':['Admin:'+self.bucket]}]})
  args=[str(BASE/'tools/seaweedfs/weed'),'server','-filer','-s3','-dir='+str(out/'data'),'-master.dir='+str(out/'meta'),'-ip=127.0.0.1','-ip.bind=127.0.0.1','-master.port=9800','-master.port.grpc=9801','-filer.port=9802','-filer.port.grpc=9803','-volume.port=9804','-volume.port.grpc=9805','-s3.port=9806','-s3.port.grpc=9807','-s3.ip.bind=127.0.0.1','-s3.config='+str(auth),'-master.telemetry=false','-debug=false','-volume.pprof=false','-iam=false','-s3.iam=false','-s3.port.iceberg=0','-s3.port.lance=0','-metricsPort=0','-master.volumeSizeLimitMB=64','-volume.max=8']
  self.store=Process(args,out,out/'seaweedfs.log',{**self.env,'GOMAXPROCS':'2','GOMEMLIMIT':'512MiB','TMPDIR':str(out/'tmp')})
  self.guard.register('seaweedfs',self.store,768,32)
  end=time.monotonic()+40
  while True:
   try:
    self.s3('PUT','');break
   except Exception:
    if time.monotonic()>end:raise RuntimeError('SeaweedFS readiness deadline')
    time.sleep(.2)
  self.deploy(source)
  for n in range(width):self.proxies[n]=Proxy(9840+n,out/f'node-{n}-store-events.json',self.events,self.effects);self.start(n)
  dump(out/'fleet.json',{'nodes':{n:identity(p) for n,p in self.nodes.items()},'binary':{'path':self.binary,'sha256':sha(self.binary)},'store':{'sha256':sha(BASE/'tools/seaweedfs/weed'),'version':'4.48','ports':list(range(9800,9808))},'ingress':list(range(9820,9820+width)),'internal':list(range(9830,9830+width)),'proxies':list(range(9840,9840+width)),'bucket':self.bucket})
 def s3(self,method,key):
  url=self.endpoint+'/'+self.bucket+('/'+key if key else '');parsed=urllib.parse.urlsplit(url)
  now=datetime.datetime.now(datetime.timezone.utc);stamp=now.strftime('%Y%m%dT%H%M%SZ');date=stamp[:8];empty=hashlib.sha256(b'').hexdigest()
  headers={'Host':parsed.netloc,'x-amz-content-sha256':empty,'x-amz-date':stamp}
  signed='host;x-amz-content-sha256;x-amz-date';canonical=method+'\n'+urllib.parse.quote(urllib.parse.unquote(parsed.path),safe='/~')+'\n'+parsed.query+'\n'+''.join(k.lower()+':'+v+'\n' for k,v in headers.items())+'\n'+signed+'\n'+empty
  scope=date+'/us-east-1/s3/aws4_request';value='AWS4-HMAC-SHA256\n'+stamp+'\n'+scope+'\n'+hashlib.sha256(canonical.encode()).hexdigest();secret=b'AWS4suite-public-test-only'
  for part in [date,'us-east-1','s3','aws4_request']:secret=hmac.new(secret,part.encode(),hashlib.sha256).digest()
  signature=hmac.new(secret,value.encode(),hashlib.sha256).hexdigest();headers['Authorization']='AWS4-HMAC-SHA256 Credential=suite-public-test-only/'+scope+', SignedHeaders='+signed+', Signature='+signature
  req=urllib.request.Request(url,method=method,headers=headers)
  with urllib.request.urlopen(req,timeout=3) as r:return r.read(4*1024*1024)
 def owner(self,root):
  listing=ET.fromstring(self.s3('GET','?list-type=2'));keys=[n.text for n in listing.iter() if n.tag.endswith('}Key') or n.tag=='Key'];keys=[k for k in keys if k.endswith(':'+root+'/own.json')]
  if len(keys)!=1:raise AssertionError('owner absent/ambiguous for '+root)
  return json.loads(self.s3('GET',keys[0]))
 def deploy(self,source):
  log=self.out/('deploy-'+str(time.monotonic_ns())+'.log');code,_=command([self.binary,'deploy',source,'--bucket','s3://'+self.bucket,'--endpoint',self.endpoint],ROOT,log,60,self.env)
  if code:raise RuntimeError('fixture deployment failed: '+str(log))
 def start(self,n):
  g=self.generation.get(n,0)+1;self.generation[n]=g;data=self.out/f'node-{n}-generation-{g}';data.mkdir()
  env={**self.env,'CELLD_NODE':f'suite-node-{n}','CELLD_TEST_DATA_DIR':str(data)}
  for port in [9820+n,9830+n]:port_available(port)
  p=Process([self.binary,'--bucket','s3://'+self.bucket,'--endpoint',f'http://127.0.0.1:{9840+n}','--listen',f'127.0.0.1:{9820+n}','--internal-listen',f'127.0.0.1:{9830+n}'],ROOT,self.out/f'node-{n}-{g}.log',env);self.nodes[n]=p;self.identities[n]=identity(p);self.guard.register(f'node-{n}-{g}',p)
  end=time.monotonic()+25
  while time.monotonic()<end:
   if p.p.poll() is not None:raise RuntimeError('node startup exit '+str(p.p.returncode))
   try:
    if fetch(9820+n,{'path':'/.well-known/celld/health','timeout':1})['status']==200:return
   except Exception:pass
   time.sleep(.15)
  raise RuntimeError('node readiness deadline')
 def req(self,n,step):return fetch(9820+n,step)
 def stop_node(self,n,kill=True):
  p=self.nodes[n];before=self.identities.get(n,{'pid':p.p.pid,'witness_error':'process exited before initial identity read'})
  if kill and p.p.poll() is None:os.killpg(p.p.pid,signal.SIGKILL)
  p.stop();self.nodes.pop(n);dump(self.out/f'dead-node-{n}-{self.generation[n]}.json',{'before':before,'returncode':p.p.returncode,'reaped':True,'proc_absent':not Path('/proc',str(p.p.pid)).exists()})
 def close(self):
  for proxy in self.proxies.values():proxy.set('release')
  for n in list(self.nodes):self.stop_node(n,False)
  for proxy in self.proxies.values():proxy.close()
  if self.store:self.store.stop()
  self.guard.finish()
