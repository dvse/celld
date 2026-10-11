"""Three private nodes, local MinIO, exact HTTP matrix from every ingress."""
import json,os,pathlib,signal,subprocess,time,urllib.request,sys
root=pathlib.Path(os.environ.get('CELLD_TEST_TOOLS_ROOT',str(pathlib.Path.home()/'celld-suite-20261010')))
if sys.platform!='linux' or any(not (root/'bin'/name).is_file() for name in ['minio','mc']):
 print(json.dumps({'unavailable':'Requires the fleet host\'s local MinIO and mc in $CELLD_TEST_TOOLS_ROOT/bin (default ~/celld-suite-20261010/bin)'}));raise SystemExit(77)
case=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();art.mkdir(parents=True,exist_ok=True)
binary=os.environ['CELLD_BIN'];base=int(os.environ.get('CELLD_TEST_PORT_BASE','9740'))
assert 9700<=base and base+7<=9949
endpoint=f'http://127.0.0.1:{base+6}'
env={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','CELLD_','MINIO_','S3_'))}
env.update(AWS_ACCESS_KEY_ID='suite-public',AWS_SECRET_ACCESS_KEY='suite-public-password',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',MINIO_ROOT_USER='suite-public',MINIO_ROOT_PASSWORD='suite-public-password',CELLD_TOKIO_THREADS='2',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_SHUTDOWN_TOTAL_MS='5000',RUST_LOG='info,celld::capability=debug',CELLD_PLACEMENT=json.dumps({'Sender':['r9-05-0'],'Receiver':['r9-05-1'],'Third':['r9-05-2']}))
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
  subprocess.run(mc+['mb','private/r9-05'],check=True,stdout=log,stderr=log)
  subprocess.run([binary,'deploy',str(case),'--bucket','s3://r9-05','--endpoint',endpoint],env=env,check=True,stdout=log,stderr=log)
 nodes=[]
 for i in range(3):
  data=art/f'data-{i}';data.mkdir()
  nodes.append(start([binary,'--bucket','s3://r9-05','--endpoint',endpoint,'--listen',f'127.0.0.1:{base+i}','--internal-listen',f'127.0.0.1:{base+3+i}'],f'node-{i}',{'CELLD_NODE':f'r9-05-{i}','CELLD_TEST_DATA_DIR':str(data)}))
 for i in range(3):
  for _ in range(300):
   if nodes[i].poll() is not None:raise RuntimeError('node exited')
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{base+i}/.well-known/celld/health',timeout=.3):pass
    break
   except OSError:time.sleep(.1)
  else:raise RuntimeError('node readiness timeout')
 for i,kind in enumerate(['sender','receiver','third']):
  for attempt in range(100):
   try:
    if get(f'http://127.0.0.1:{base+i}/{kind}/init') is True:break
   except OSError:pass
   time.sleep(.1)
  else:raise RuntimeError('placement warmup '+kind)
 expected=json.loads((case/'expected.json').read_text());results=[]
 actual=get(f'http://127.0.0.1:{base}/')
 for key,value in expected.items():results.append({'name':key,'pass':actual.get(key)==value,'actual':actual.get(key),'expected':value})
 for i,klass in enumerate(['Sender','Receiver','Third']):results.append({'name':klass+' actual owner','pass':'scope='+klass+':' in (art/f'node-{i}.log').read_text()})
 for i,kind in enumerate(['sender','receiver','third']):
  try:get(f'http://127.0.0.1:{base+i}/{kind}/cleanup')
  except OSError:pass
 import re
 deadline=time.monotonic()+5
 while time.monotonic()<deadline:
  pending=False
  for i in range(3):
   values=re.findall(r'event="capability_revoke" exports=(\d+) pins=(\d+)',(art/f'node-{i}.log').read_text())
   if values and values[-1]!=('0','0'):pending=True
  if not pending:break
  time.sleep(.05)
 counts=[]
 for i in range(3):
  values=[list(map(int,m)) for m in re.findall(r'event="capability_revoke" exports=(\d+) pins=(\d+)',(art/f'node-{i}.log').read_text())]
  counts.append(values)
  if values:results.append({'name':f'node {i} final exports/pins','pass':values[-1]==[0,0],'actual':values[-1]})
 (art/'native-counts.json').write_text(json.dumps(counts))
 import urllib.parse
 def call(i,kind,method,*args):return get(f'http://127.0.0.1:{base+i}/{kind}/{method}?'+urllib.parse.urlencode({'args':json.dumps(args)}))
 expected_disconnect={'aborted':True,'reason':{'name':'AbortError','message':'An AbortSignal received over RPC was implicitly aborted because the connection back to its trigger was lost.'}}
 results.append({'name':'arm forwarded death signal','pass':call(0,'sender','armDeath','relay') is True})
 os.killpg(nodes[1].pid,signal.SIGKILL);nodes[1].wait()
 call(0,'sender','abortDeath')
 disconnected=call(2,'third','check')
 results.append({'name':'intermediary death uses AbortError','pass':disconnected==expected_disconnect,'actual':disconnected})
 results.append({'name':'arm direct death signal','pass':call(0,'sender','armDeath','direct') is True})
 os.killpg(nodes[0].pid,signal.SIGKILL);nodes[0].wait()
 disconnected=call(2,'third','check')
 results.append({'name':'source death uses AbortError','pass':disconnected==expected_disconnect,'actual':disconnected})
 summary={'cases':len(results),'passed':sum(r['pass'] for r in results),'failed':sum(not r['pass'] for r in results),'results':results,'actual':actual}
 (art/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
 raise SystemExit(bool(summary['failed']))

finally:
 # Keep the store running until all nodes have drained and released ownership.
 for process in reversed(processes[1:]):stop(process)
 if processes:stop(processes[0])
 for log in logs:log.close()
