"""Three private nodes, local MinIO, exact HTTP matrix from every ingress."""
import json,os,pathlib,signal,subprocess,time,urllib.request,sys
root=pathlib.Path(os.environ.get('CELLD_TEST_TOOLS_ROOT',str(pathlib.Path.home()/'celld-suite-20261010')))
if sys.platform!='linux' or any(not (root/'bin'/name).is_file() for name in ['minio','mc']):
 print(json.dumps({'unavailable':'Requires the fleet host\'s local MinIO and mc in $CELLD_TEST_TOOLS_ROOT/bin (default ~/celld-suite-20261010/bin)'}));raise SystemExit(77)
case=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();art.mkdir(parents=True,exist_ok=True)
destination=int(os.environ.get('DESTINATION','2'))
binary=os.environ['CELLD_BIN'];base=int(os.environ.get('CELLD_TEST_PORT_BASE','9740'))
assert 9700<=base and base+8<=9949
endpoint=f'http://127.0.0.1:{base+6}'
env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','CELLD_','MINIO_','S3_'))}
env.update(AWS_ACCESS_KEY_ID='suite-public',AWS_SECRET_ACCESS_KEY='suite-public-password',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',MINIO_ROOT_USER='suite-public',MINIO_ROOT_PASSWORD='suite-public-password',CELLD_TOKIO_THREADS='2',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_SHUTDOWN_TOTAL_MS='5000',RUST_LOG='info,celld::capability=debug,celld::capability_session=debug')
from proxy import Proxy
proxy=Proxy(base+8,base+4)
processes=[];logs=[]
def start(command,name,extra={}):
 log=(art/(name+'.log')).open('w');logs.append(log)
 p=subprocess.Popen(command,env={**env,**extra},stdout=log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(p);return p
def get(url):
 with urllib.request.urlopen(url,timeout=90) as response:return json.load(response)
def stop(p):
 if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
 try:p.wait(timeout=8)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
try:
 (art/'store').mkdir()
 minio=start([str(root/'bin/minio'),'server',str(art/'store'),'--address',f'127.0.0.1:{base+6}','--console-address',f'127.0.0.1:{base+7}'],'minio')
 for _ in range(300):
  try:
   with urllib.request.urlopen(endpoint+'/minio/health/ready',timeout=.3):pass
   break
  except OSError:time.sleep(.1)
 else:raise RuntimeError('MinIO readiness timeout')
 mc=[str(root/'bin/mc'),'--config-dir',str(art/'mc')]
 with (art/'setup.log').open('w') as log:
  subprocess.run(mc+['alias','set','private',endpoint,'suite-public','suite-public-password'],check=True,stdout=log,stderr=log)
  subprocess.run(mc+['mb','private/r7-02'],check=True,stdout=log,stderr=log)
  subprocess.run([binary,'deploy',str(case),'--bucket','s3://r7-02','--endpoint',endpoint],env=env,check=True,stdout=log,stderr=log)
 nodes=[]
 for i in range(3):
  data=art/f'data-{i}';data.mkdir()
  nodes.append(start([binary,'--bucket','s3://r7-02','--endpoint',endpoint,'--listen',f'127.0.0.1:{base+i}','--internal-listen',f'127.0.0.1:{base+3+i}','--advertise',f'127.0.0.1:{base+8 if i==1 else base+3+i}'],f'node-{i}',{'CELLD_NODE':f'r7-02-{i}','CELLD_TEST_DATA_DIR':str(data),'CELLD_REBALANCE_INTERVAL_MS':'100','CELLD_PLACEMENT_WEIGHT':'128' if i==destination else '1'}))
 for i in range(3):
  for _ in range(300):
   if nodes[i].poll() is not None:raise RuntimeError('node exited')
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{base+i}/.well-known/celld/health',timeout=.3):pass
    break
   except OSError:time.sleep(.1)
  else:raise RuntimeError('node readiness timeout')
 results=[]
 def call(i,kind,method,*args):
  import urllib.parse
  return get(f'http://127.0.0.1:{base+i}/{kind}/{method}?'+urllib.parse.urlencode({'args':json.dumps(args)}))['ok']
 def check(name,value):
  results.append({'name':name,'pass':bool(value)});print(json.dumps(results[-1]),flush=True)
  (art/'results.json').write_text(json.dumps(results,indent=2)+'\n')
 import concurrent.futures,re
 def post(i,path):
  with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{base+3+i}'+path,method='POST'),timeout=30) as r:return json.load(r)
 post(1,'/rebalance/pause')
 check('sender initialized',bool(call(0,'sender','init')))
 scope='Receiver:'+call(1,'receiver','init')
 label='remote' if destination==2 else 'local'
 check(label+' warm route points at B',bool(call(0,'sender','warm')))
 call(1,'receiver','fill')
 proxy.arm()
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
  future=pool.submit(call,0,'sender','send',label)
  check(label+' request paused after route selection',proxy.arrived.wait(10))
  post(1,'/evict/'+scope)
  post(1,'/rebalance/resume')
  deadline=time.monotonic()+20;handoff=False
  while time.monotonic()<deadline:
   log=(art/'node-1.log').read_text()
   handoff=any('event="cell_handoff_accepted"' in l and scope in l and f'successor=r7-02-{destination} ' in l for l in log.splitlines())
   if handoff:break
   time.sleep(.05)
  check(label+' actual signed handoff completed',handoff)
  proxy.release.set()
  value=future.result(timeout=60)
 check(label+' one execution with callback and streams',value=={'value':42,'bytes':[1,2,3],'count':1})
 (art/'outcome.json').write_text(json.dumps(value)+'\n')
 deadline=time.monotonic()+5
 while time.monotonic()<deadline:
  ledger=call(0,'sender','ledger')
  if ledger['disposals'].get(label)==1:break
  time.sleep(.05)
 check(label+' callback exactly once released',ledger['disposals'].get(label)==1)
 check(label+' writable result',ledger['writes'].get(label)==[4,5])
 check(label+' receiver ledger',call(destination,'receiver','ledger').get(label)==1)
 # Final state and native cleanup are retained for independent review.
 time.sleep(.3)
 (art/'proxy-events.json').write_text(json.dumps(proxy.events,indent=2)+'\n')
 (art/'ledger.json').write_text(json.dumps(call(0,'sender','ledger'),indent=2)+'\n')
 log=(art/'node-0.log').read_text();check('authenticated stale-route retries observed','event="remote_route_retry"' in log and 'attempt=NotOwner' in log)
 summary={'cases':len(results),'passed':sum(r['pass'] for r in results),'failed':sum(not r['pass'] for r in results)}
 (art/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
 raise SystemExit(bool(summary['failed']))

finally:
 # Keep the store running until all nodes have drained and released ownership.
 for process in reversed(processes[1:]):stop(process)
 if processes:stop(processes[0])
 proxy.close()
 for log in logs:log.close()
