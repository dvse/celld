"""Three private nodes, local MinIO, exact HTTP matrix from every ingress."""
import json,os,pathlib,signal,subprocess,time,urllib.request,sys
root=pathlib.Path(os.environ.get('CELLD_TEST_TOOLS_ROOT',str(pathlib.Path.home()/'celld-suite-20261010')))
if sys.platform!='linux' or any(not (root/'bin'/name).is_file() for name in ['minio','mc']):
 print(json.dumps({'unavailable':'Requires the fleet host\'s local MinIO and mc in $CELLD_TEST_TOOLS_ROOT/bin (default ~/celld-suite-20261010/bin)'}));raise SystemExit(77)
case=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();art.mkdir(parents=True,exist_ok=True)
binary=os.environ['CELLD_BIN'];base=int(os.environ.get('CELLD_TEST_PORT_BASE','9740'))
assert 9700<=base and base+9<=9949
endpoint=f'http://127.0.0.1:{base+6}'
env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','CELLD_','MINIO_','S3_'))}
env.update(AWS_ACCESS_KEY_ID='suite-public',AWS_SECRET_ACCESS_KEY='suite-public-password',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',MINIO_ROOT_USER='suite-public',MINIO_ROOT_PASSWORD='suite-public-password',CELLD_TOKIO_THREADS='2',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_SHUTDOWN_TOTAL_MS='5000',RUST_LOG='info,celld::capability=debug,celld::capability_session=debug')
from proxy import Proxy
proxies=[Proxy(base+8+i,base+3+i) for i in range(2)]
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
  subprocess.run(mc+['mb','private/r7-03'],check=True,stdout=log,stderr=log)
  subprocess.run([binary,'deploy',str(case),'--bucket','s3://r7-03','--endpoint',endpoint],env=env,check=True,stdout=log,stderr=log)
 nodes=[]
 for i in range(2):
  data=art/f'data-{i}';data.mkdir()
  nodes.append(start([binary,'--bucket','s3://r7-03','--endpoint',endpoint,'--listen',f'127.0.0.1:{base+i}','--internal-listen',f'127.0.0.1:{base+3+i}','--advertise',f'127.0.0.1:{base+8+i}'],f'node-{i}',{'CELLD_NODE':f'r7-03-{i}','CELLD_TEST_DATA_DIR':str(data)}))
 for i in range(2):
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
 def ledger(i,kind,pred,seconds=5):
  end=time.monotonic()+seconds
  while True:
   value=call(i,kind,'ledger')
   if pred(value) or time.monotonic()>end:return value
   time.sleep(.05)
 check('sender placement initialized',call(0,'sender','init'))
 check('receiver placement initialized',call(1,'receiver','init'))
 check('unrelated live anchor',call(0,'sender','setup')==42)
 import concurrent.futures
 for iteration in range(3):
  for kind in ['child','graph','error','bad']:
   label=f'{kind}-{iteration}';proxies[1].arm('cancel')
   with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(call,0,'sender','call',label,kind)
    value=ledger(1,'receiver',lambda d:d.get(label+':started')==1)
    check(label+' handler entered',value.get(label+':started')==1)
    proxies[1].cancel()
    check(label+' consumer canceled',future.result(timeout=30)=='failed')
   proxies[1].arm('normal');call(0,'sender','release',label)
   suffixes=['background']+(['child'] if kind in ['child','bad','graph'] else [])+(['read','write','graph'] if kind=='graph' else [])
   value=ledger(1,'receiver',lambda d:all(d.get(label+':'+x)==1 for x in suffixes))
   check(label+' late graph released exactly once',all(value.get(label+':'+x)==1 for x in suffixes))
   check(label+' healthy anchor survives',call(0,'sender','alive')==42)
 # Result-first ordering uses ordinary delivery/disposal; cancellation cannot
 # revoke a result that has already acquired its own reference.
 for kind in ['child','graph']:
  label='result-first-'+kind
  with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
   future=pool.submit(call,0,'sender','call',label,kind)
   ledger(1,'receiver',lambda d:d.get(label+':started')==1)
   call(0,'sender','release',label)
   check(label+' delivered and disposed',future.result(timeout=30)=='ok')
 call(0,'sender','finish');time.sleep(.3)
 import re
 counts=[]
 for i in range(2):
  entries=[]
  for line in (art/f'node-{i}.log').read_text().splitlines():
   if 'event="capability_revoke"' in line:
    m=re.search(r'exports=(\d+) pins=(\d+)',line)
    if m:entries.append([int(x) for x in m.groups()])
  counts.append(entries)
  if entries:check(f'node {i} exports and pins return to zero',entries[-1]==[0,0])
  else:print(json.dumps({'native_counts':'unavailable', 'node':i}),flush=True)
 events=proxies[1].events
 check('twelve per-call disconnects injected',sum(e['fault']=='cancel' for e in events)==12)
 (art/'proxy-events.json').write_text(json.dumps(events,indent=2)+'\n')
 (art/'native-counts.json').write_text(json.dumps(counts)+'\n')
 (art/'ledger.json').write_text(json.dumps(call(1,'receiver','ledger'),indent=2)+'\n')
 summary={'cases':len(results),'passed':sum(r['pass'] for r in results),'failed':sum(not r['pass'] for r in results)}
 (art/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
 raise SystemExit(bool(summary['failed']))

finally:
 # Keep the store running until all nodes have drained and released ownership.
 for process in reversed(processes[1:]):stop(process)
 if processes:stop(processes[0])
 for proxy in proxies:proxy.close()
 for log in logs:log.close()
