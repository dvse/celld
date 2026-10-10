"""Three private nodes, local MinIO, exact HTTP matrix from every ingress."""
import json,os,pathlib,signal,subprocess,time,urllib.request,sys
root=pathlib.Path(os.environ.get('CELLD_TEST_TOOLS_ROOT',str(pathlib.Path.home()/'celld-suite-20261010')))
if sys.platform!='linux' or any(not (root/'bin'/name).is_file() for name in ['minio','mc']):
 print(json.dumps({'unavailable':'Requires the fleet host's local MinIO and mc in $CELLD_TEST_TOOLS_ROOT/bin (default ~/celld-suite-20261010/bin)'}));raise SystemExit(77)
case=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();art.mkdir(parents=True,exist_ok=True)
binary=os.environ['CELLD_BIN'];base=int(os.environ.get('CELLD_TEST_PORT_BASE','9740'))
assert 9700<=base and base+7<=9949
endpoint=f'http://127.0.0.1:{base+6}'
env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','CELLD_','MINIO_','S3_'))}
env.update(AWS_ACCESS_KEY_ID='suite-public',AWS_SECRET_ACCESS_KEY='suite-public-password',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',MINIO_ROOT_USER='suite-public',MINIO_ROOT_PASSWORD='suite-public-password',CELLD_TOKIO_THREADS='2',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_SHUTDOWN_TOTAL_MS='5000',RUST_LOG='info,celld::capability=debug,celld::capability_session=debug')
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
  subprocess.run(mc+['mb','private/r5-02'],check=True,stdout=log,stderr=log)
  subprocess.run([binary,'deploy',str(case),'--bucket','s3://r5-02','--endpoint',endpoint],env=env,check=True,stdout=log,stderr=log)
 nodes=[]
 for i in range(3):
  data=art/f'data-{i}';data.mkdir()
  nodes.append(start([binary,'--bucket','s3://r5-02','--endpoint',endpoint,'--listen',f'127.0.0.1:{base+i}','--internal-listen',f'127.0.0.1:{base+3+i}'],f'node-{i}',{'CELLD_NODE':f'r5-02-{i}','CELLD_TEST_DATA_DIR':str(data)}))
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
 def kill(i):
  os.killpg(nodes[i].pid,signal.SIGKILL);nodes[i].wait()
 def wait_ledger(pred,seconds=20):
  deadline=time.monotonic()+seconds
  while time.monotonic()<deadline:
   ledger=call(0,'source','ledger')
   if pred(ledger):return ledger
   time.sleep(.2)
  return ledger
 for i,kind in enumerate(['source','holder','receiver']):check(kind+' placement initialized',call(i,kind,'init'))
 check('direct holder',call(1,'holder','hold','direct')==42)
 check('retained local alias',call(1,'holder','hold','local',True)==42)
 check('active call target',call(1,'holder','hold','active')==42)
 check('forwarded aliases',call(2,'receiver','take'))
 kill(2)
 ledger=wait_ledger(lambda d:d.get('disposed:forward-only')==1)
 check('dead final receiver releases forwarded-only target',ledger.get('disposed:forward-only')==1)
 check('forwarder local alias survives receiver death',call(1,'holder','alive')==42 and ledger.get('disposed:forward-kept',0)==0)
 # >60 seconds is intentional: live sessions impose no application deadline.
 check('healthy 70-second call',call(1,'holder','slow',70000)==42)
 check('admit pending call',call(1,'holder','pending'))
 time.sleep(.5)
 kill(1)
 ledger=wait_ledger(lambda d:all(d.get('disposed:'+n)==1 for n in ['direct','active','forward-kept']))
 check('dead holder releases direct export',ledger.get('disposed:direct')==1)
 check('dead holder cancels active call owner',ledger.get('disposed:active')==1)
 check('dead forwarding holder releases upstream alias',ledger.get('disposed:forward-kept')==1)
 check('source local alias survives holder death',ledger.get('disposed:local',0)==0 and call(0,'source','retained')==42)
 call(0,'source','release')
 ledger=wait_ledger(lambda d:d.get('disposed:local')==1)
 check('last local alias disposes exactly once',ledger.get('disposed:local')==1)
 check('all disposers exactly once',all(ledger.get('disposed:'+n)==1 for n in ['direct','active','forward-only','forward-kept','local']))
 import re
 counts=[]
 for line in (art/'node-0.log').read_text().splitlines():
  if 'event="capability_revoke"' in line:
   match=re.search(r'exports=(\d+) pins=(\d+)',line)
   if match:counts.append([int(x) for x in match.groups()])
 if counts:check('native exports and heap pins return to zero',counts[-1]==[0,0])
 else:print(json.dumps({'native_counts':'unavailable on baseline without capability_revoke instrumentation'}),flush=True)
 (art/'native-counts.json').write_text(json.dumps(counts)+'\n')
 (art/'ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 summary={'cases':len(results),'passed':sum(r['pass'] for r in results),'failed':sum(not r['pass'] for r in results)}
 (art/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
 raise SystemExit(bool(summary['failed']))

finally:
 # Keep the store running until all nodes have drained and released ownership.
 for process in reversed(processes[1:]):stop(process)
 if processes:stop(processes[0])
 for log in logs:log.close()
