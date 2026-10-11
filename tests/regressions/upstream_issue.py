"""Standalone upstream regressions: fresh retained state and PID-only cleanup."""
import contextlib,hashlib,http.client,http.server,json,os,pathlib,shutil,signal,subprocess,threading,time,urllib.parse
Path=pathlib.Path

def environment():
 env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('TOKEN','SECRET','PASSWORD','API_KEY','AWS_','AZURE_','GOOGLE_'))}
 env.update(CELLD_TOKIO_THREADS='2',CELLD_V8_HEAP_LIMIT_MB='128',CELLD_READY_FLEET_GATE_MS='0',CELLD_SHUTDOWN_TOTAL_MS='10000')
 return env

def request(port,path,timeout=5):
 conn=http.client.HTTPConnection('127.0.0.1',port,timeout=timeout)
 try:
  conn.request('GET',path);r=conn.getresponse();body=r.read().decode()
  if r.status!=200:raise AssertionError((r.status,body))
  try:return json.loads(body)
  except ValueError:return body
 finally:conn.close()

def descendants(parent):
 children=set();parents={}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:parents[int(p.name)]=int((p/'stat').read_text().rsplit(')',1)[1].split()[1])
  except (FileNotFoundError,PermissionError):pass
 changed=True
 while changed:
  added={pid for pid,ppid in parents.items() if ppid==parent or ppid in children}-children
  changed=bool(added);children.update(added)
 return children

class Runtime:
 def __init__(self,project,out,runtime='celld',binary=None,port=9860):
  self.project=project;self.out=out;self.runtime=runtime;self.port=port;out.mkdir(parents=True,exist_ok=True)
  self.binary=binary or os.environ['CELLD_BIN' if runtime=='celld' else 'WORKERD_BIN'];self.log=(out/'runtime.log').open('wb')
  config=json.loads((project/'wrangler.json').read_text());env=environment()
  if runtime=='celld':args=[self.binary,'dev',str(project),'--port',str(port),'--no-watch','--logs']
  else:
   bundle=out/'worker.mjs';esbuild=os.environ['CELLD_ESBUILD']
   with (out/'bundle.log').open('wb') as f:subprocess.run([esbuild,str(project/config['main']),'--bundle','--format=esm','--platform=neutral','--external:cloudflare:*','--external:node:*','--outfile='+str(bundle)],check=True,stdout=f,stderr=f,env=env)
   j=json.dumps;bindings=[];classes=[]
   for b in config.get('durable_objects',{}).get('bindings',[]):
    classes.append(b['class_name']);bindings.append('(name='+j(b['name'])+',durableObjectNamespace=(className='+j(b['class_name'])+'))')
   bindings.extend('(name='+j(b['binding'])+',workerLoader=())' for b in config.get('worker_loaders',[]))
   bindings.extend('(name='+j(k)+',text='+j(v)+')' for k,v in config.get('vars',{}).items())
   namespaces=','.join('(className='+j(c)+',uniqueKey='+j(c)+',enableSql=true)' for c in classes)
   disk=out/'storage';disk.mkdir()
   text='using Workerd = import "/workerd/workerd.capnp";\nconst config :Workerd.Config = (services=[(name="main",worker=(compatibilityDate='+j(config['compatibility_date'])+',modules=[(name="worker",esModule=embed "worker.mjs")],bindings=['+','.join(bindings)+'],durableObjectNamespaces=['+namespaces+'],durableObjectStorage=(localDisk="disk"),globalOutbound="internet")),(name="disk",disk=(path='+j(str(disk))+',writable=true)),(name="internet",network=(allow=["private","local"]))],sockets=[(name="http",address='+j('127.0.0.1:'+str(port))+',http=(),service="main")]);\n'
   cfg=out/'workerd.capnp';cfg.write_text(text);args=[self.binary,'serve','--experimental',str(cfg)]
  self.process=subprocess.Popen(args,cwd=project,env=env,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
  self.pids=[]
  (out/'process.json').write_text(json.dumps({'pid':self.process.pid,'command':args,'binary_sha256':hashlib.sha256(Path(self.binary).read_bytes()).hexdigest()},indent=2))
  try:
   import socket
   deadline=time.monotonic()+40
   while time.monotonic()<deadline:
    if self.process.poll() is not None:raise RuntimeError('runtime exited; '+str(out/'runtime.log'))
    try:
     with socket.create_connection(('127.0.0.1',port),.1):return
    except OSError:time.sleep(.1)
   raise RuntimeError('startup timed out')
  except BaseException:self.close();raise
 def close(self):
  owned=descendants(self.process.pid);self.pids=sorted(owned)
  if self.process.poll() is None:
   os.kill(self.process.pid,signal.SIGINT)
   try:self.process.wait(timeout=25)
   except subprocess.TimeoutExpired:
    for pid in [self.process.pid,*owned]:
     try:os.kill(pid,signal.SIGTERM)
     except ProcessLookupError:pass
    try:self.process.wait(timeout=5)
    except subprocess.TimeoutExpired:os.kill(self.process.pid,signal.SIGKILL);self.process.wait()
  for pid in owned:
   try:os.kill(pid,signal.SIGTERM)
   except ProcessLookupError:pass
  self.log.close()
  (self.out/'cleanup.json').write_text(json.dumps({'parent_pid':self.process.pid,'descendant_pids':self.pids,'exit':self.process.returncode,'state_preserved':True}))
 def __enter__(self):return self
 def __exit__(self,*args):self.close()

@contextlib.contextmanager
def origin(port=9868):
 class Handler(http.server.BaseHTTPRequestHandler):
  def do_GET(self):
   time.sleep(.5);body=b'origin answered';self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers()
   try:self.wfile.write(body)
   except BrokenPipeError:pass
  def log_message(self,*args):pass
 server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
 thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
 try:yield 'http://127.0.0.1:'+str(port)+'/'
 finally:server.shutdown();server.server_close();thread.join(2)

def run(issue,source):
 out=Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();out.mkdir(parents=True,exist_ok=True)
 project=out/'project';shutil.copytree(source,project,ignore=shutil.ignore_patterns('__pycache__'))
 runtime=os.environ.get('CELLD_TEST_RUNTIME','celld');observations={};passed=False
 try:
  if issue==292 and runtime=='workerd':print('v0.5.1 celld on-disk migration has no workerd equivalent');return 77
  if issue==292:
   old=os.environ.get('CELLD_V051_BIN')
   if not old:print('set CELLD_V051_BIN to stock v0.5.1 for migration seed');return 77
   with Runtime(project,out/'old-v051',binary=old) as rt:
    for value in ['a1','a2']:request(rt.port,'/write?v='+value)
    observations['before']=request(rt.port,'/read')
   expected={'root':['a1','a2'],'facet':['a1','a2']}
   assert observations['before']==expected,observations
   with Runtime(project,out/'candidate') as rt:observations['after']=request(rt.port,'/read')
   passed=observations['after']==expected
  elif issue==277:
   with origin() as url:
    cfg=json.loads((project/'wrangler.json').read_text());cfg['vars']={'ORIGIN':url};(project/'wrangler.json').write_text(json.dumps(cfg))
    with Runtime(project,out/runtime,runtime) as rt:
     for mode in ['fetch','storage','block']:
      request(rt.port,'/?mode='+mode)
      time.sleep(.2)  # The constructor's initiating request must retire first.
      request(rt.port,'/resolve?mode='+mode)
      deadline=time.monotonic()+3
      while True:
       value=request(rt.port,'/log?mode='+mode)
       if value==['awaited','fetched','stored'] or time.monotonic()>deadline or any(x.startswith('error:') for x in value):break
       time.sleep(.05)
      observations[mode]=value
   passed=all(v==['awaited','fetched','stored'] for v in observations.values())
  elif issue==287:
   with Runtime(project,out/runtime,runtime) as rt:
    code=subprocess.run(['node',str(project/'client.mjs'),str(rt.port)],capture_output=True,text=True,timeout=25,env=environment())
    (out/'client.log').write_text(code.stdout+code.stderr);observations=json.loads(code.stdout)
    passed=code.returncode==0 and all(observations.get(m)=='pong' for m in ['handler','loop','waituntil'])
  elif issue==294:
   with origin() as url,Runtime(project,out/runtime,runtime) as rt:
    for kind in ['timer','fetch','wait-until']:
     for cancel in [False,True]:
      path='/'+kind+'?object='+kind+'-'+str(cancel)+'&origin='+urllib.parse.quote(url,safe='')
      if cancel:
       try:request(rt.port,path,.05)
       except (TimeoutError,OSError):pass
      started=time.monotonic()
      try:value=request(rt.port,path,2)
      except (TimeoutError,OSError):value='TIMEOUT'
      observations[kind+'-'+str(cancel)]={'value':value,'seconds':round(time.monotonic()-started,3)}
   passed=all(v['value']==('origin answered' if k.startswith('fetch') else 'timer fired') for k,v in observations.items())
  else:raise ValueError(issue)
 finally:
  (out/'observation.json').write_text(json.dumps({'issue':issue,'runtime':runtime,'pass':passed,'observations':observations},indent=2)+'\n')
  print(json.dumps({'issue':issue,'runtime':runtime,'pass':passed,'observations':observations}),flush=True)
 return 0 if passed else 1
