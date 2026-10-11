"""Finite behaviour checks for examples previously excluded by the fetch-only driver."""
import concurrent.futures,json,socket,time,traceback,urllib.parse,shutil,types
from common import ROOT,dump,result,safe_id,command,clean_env
from runtime import Runtime,fetch,Unavailable

def check(case,rt):
 name=case['id'].split('/')[-1];seen=[]
 def req(path='/',**kw):
  r=fetch(rt.port,{'path':path,**kw});seen.append(r);dump(rt.out/'trace.json',seen);return r
 def ok(value,why):
  dump(rt.out/'trace.json',seen)
  if not value:raise AssertionError(why+'; '+json.dumps(seen)[-1200:])
 if name in ['kv','r2']:
  ok(req('/owned',method='PUT',body='retained')['status']==204,'put acknowledgement');ok(req('/owned')=={'status':200,'body':'retained'},'read after put');ok(req('/owned',method='DELETE')['status']==204,'delete acknowledgement');ok(req('/owned')['status']==404,'absence after delete')
 elif name=='d1':
  ok(req('/count')['body']=={'count':0},'initial count');ok(req('/',json={'name':'phase2','message':'owned'})=={'status':201,'body':{'id':1,'changes':1}},'insert');ok(req('/count')['body']=={'count':1},'persisted count')
 elif name=='vectordb':
  ok(req('/red',method='PUT',json=[255,0,0])['status']==201,'vector insert');ok(req('/255,0,0')['body']=={'name':'red','distance':0},'nearest neighbour')
 elif name=='alarm':
  ok(req('/')['body']=={'fires':0,'pendingAlarm':None},'initial alarm');ok(req('/arm')['body'].get('armed') is True,'arm')
  deadline=time.monotonic()+10
  while time.monotonic()<deadline:
   value=req('/')['body']
   if value=={'fires':1,'pendingAlarm':None}:break
   time.sleep(.2)
  else:raise AssertionError('native scheduled delivery deadline')
 elif name=='facets':
  ok(req('/')=={'status':200,'body':'0:hello, facet'},'initial facet');ok(req('/')=={'status':200,'body':'1:hello, facet'},'facet persistence')
 elif name=='persistent-dup':ok(req('/')['body']==['counter:a:1','counter:a:2','counter:a:3'],'persistent dup shares restored target')
 elif name=='restore-disposer':
  body=req('/')['body'];ok(body.get('legit')==[1,2] and body.get('value')==7 and body.get('localHits')==0,'restoration/disposal values');ok(body.get('afterForgery',{}).get('restores')==0,'restore control names rejected');ok(body.get('afterDispose',{}).get('disposed')==1,'remote disposer called exactly once')
 elif name=='island-lockdown':
  body=req('/')['body'];ok(all(body.get(k)==v for k,v in {'abort':True,'timeout':'fired','clone':2,'uuid':'string','encode':2,'response':'ok','errorName':'E','frozenArray':True}.items()),'lockdown host API probes')
 elif name=='turn-queue-facet':
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   future=pool.submit(fetch,rt.port,{'path':'/race','timeout':10});time.sleep(.01);held=req('/hold?n=15000000',timeout=10);race=future.result(timeout=12);seen.append(race);ok(held['body']=='held' and race['body']=='pong','overlapping facet opening completed')
  ok(req('/probe')['body']=='alive','subsequent turn makes progress')
 elif name=='wasm':
  for key,count in [('a',1),('a',2),('b',1)]:ok(req('/c/'+key)=={'status':200,'body':{'name':key,'n':count,'lang':'rust'}},'compiled WASM named durable counter')
 elif name=='router':
  for key,count in [('a',1),('a',2),('b',1)]:ok(req('/'+key)=={'status':200,'body':{'name':key,'n':count}},'named routing and durable count')
 elif name=='rpc-dispose':ok(req('/')['body']=={'doPromise':1,'doResult':1,'svcPromise':2,'svcResult':2,'doPipeline':'hello x','doProxyPipeline':'hello y'},'RPC result disposal and pipeline')
 elif name=='dynamic-worker-tails':
  ok(req('/')['body']=='Hello from a Dynamic Worker!\n','loaded response')
  deadline=time.monotonic()+8
  while time.monotonic()<deadline:
   log=(rt.out/'runtime.log').read_text()
   if 'dynamic-worker-tail: hello from loaded code' in log:break
   time.sleep(.1)
  else:raise AssertionError('loaded worker tail record absent')
 elif name=='queues':
  ok(req('/okay')['body']['queued']['path']=='/okay','queue acknowledgement');ok(req('/fail')['body']['queued']['path']=='/fail','retry acknowledgement')
  deadline=time.monotonic()+30
  while time.monotonic()<deadline:
   log=(rt.out/'runtime.log').read_text()
   if all(x in log for x in ['processing job','retrying job','dead job']):break
   time.sleep(.2)
  else:raise AssertionError('queue processing/retry/dead-letter witnesses missing')
  seen.append({'log_witnesses':{x:log.count(x) for x in ['processing job','retrying job','dead job']}})
 elif name=='cron':
  ok(req('/')['status']==200,'fetch readiness');deadline=time.monotonic()+75
  while time.monotonic()<deadline:
   log=(rt.out/'runtime.log').read_text()
   if __import__('re').search(r'cron [0-9]{13}',log):break
   time.sleep(.25)
  else:raise AssertionError('minute scheduled event absent by 75-second bound')
  seen.append({'scheduled_log':__import__('re').findall(r'cron [0-9]{13}',log)})
 elif name=='static-assets':ok(req('/')['body']==(rt.stage/'public/index.html').read_text(),'asset bytes match source')
 elif name=='workflow':
  from .peer import Peer
  with Peer() as peer:
   value=req('/create?url='+urllib.parse.quote(peer.url+'/source',safe=''))['body'];ok(isinstance(value,dict) and isinstance(value.get('id'),str),'workflow id');deadline=time.monotonic()+20
   while time.monotonic()<deadline:
    state=req('/status?id='+value['id'])['body']
    if state.get('status')=='complete':break
    time.sleep(.2)
   else:raise AssertionError('workflow did not complete')
   ok(state.get('output')=={'bytes':len(peer.body),'lines':peer.body.count(b'\n')+1},'workflow step output')
 elif name=='wsclient':
  from .peer import Peer
  with Peer() as peer:
   ok(req('/connect?url='+urllib.parse.quote(peer.url.replace('http:','ws:')+'/echo',safe=''))['status']==202,'outbound websocket accepted');deadline=time.monotonic()+10
   while time.monotonic()<deadline:
    if req('/')['body']=={'message':'hello'}:break
    time.sleep(.15)
   else:raise AssertionError('outbound echo not persisted')
 elif name in ['actor-io','ws-session-loop','ws-relay']:
  if name=='ws-session-loop':ok(req('/put')['body']=='ok','session KV seeded')
  paths=['/direct?n=direct','/front?n=front','/returned?n=returned'] if name=='ws-relay' else ['/']
  for i,path in enumerate(paths):
   arg=str(rt.port) if name=='actor-io' else 'ws://127.0.0.1:'+str(rt.port)+path
   log=rt.out/f'client-{i}.log';code,_=command(['node',rt.stage/'client.mjs',arg],rt.stage,log,22,clean_env());value=log.read_text().strip();seen.append({'client_exit':code,'stdout':value})
   ok(code==0,'bounded WebSocket client exit')
   if name=='ws-session-loop':ok(json.loads(value).get('ok') is True,'four websocket I/O answers')
   else:ok(value==('answer:slow-done' if name=='actor-io' else 'echo:hi'),'websocket reply after cancellation/relay')
 elif name=='mailbox-ownership':
  ok(req('/park')['body']=='parked','retired event parked');sock=socket.create_connection(('127.0.0.1',rt.port),timeout=3)
  try:
   sock.sendall(b'GET /hold HTTP/1.1\r\nHost: suite.test\r\nConnection: close\r\n\r\n');time.sleep(.2);ok(req('/release')['body']=='released','other event released continuation');time.sleep(.8)
  finally:sock.close()
  time.sleep(3.2);ok(req('/result')['body']=='worked','retired event I/O survives recipient cancellation')
 elif name=='bindings':
  value=req('/?n=phase2')['body'];ok(isinstance(value.get('id'),str) and bool(value['id']),'durable identity');ok({k:v for k,v in value.items() if k!='id'}=={'viaBinding':'written-through-binding','viaOwner':'written-through-binding','props':{'tenant':'t1','n':[1,2]},'plainProps':{},'jsonVar':[3,{'a':'b'}],'jsonVarType':'array','stringVar':'plain'},'cross-script namespace, props and vars')
 elif name=='self-forward':
  ok(req('/normal')['body']=={'run':'bound','fire':'recorded 7:planet bob says hi'},'three-script persistent self');ok(req('/loaded')['body']=={'run':'function:true:bound','fire':'recorded 8:loaded bob says hi'},'loaded authored self')
 elif name=='core-fidelity':
  restore=req('/restore')['body'];ok(restore=={'static':'static:worker:value','staticRedirectRestores':1,'staticInnerRestores':2,'topDo':'top-do:actor:value','topDoRedirectRestores':1,'topDoInnerRestores':2},'new restore chain boundaries')
  ok(req('/waituntil')['body']=={'answer':'answered','answeredFast':True,'doneAtAnswer':0,'doneLater':1},'waitUntil outlives RPC answer');ok(req('/keep')['body']=={'keep':'kept'},'retained capability');time.sleep(65);ok(req('/use')['body']=={'use':'pong'},'retained origin remains live');ok(req('/slow?ms=65000',timeout=80)['body']=={'slow':'waited:65000'},'live capability duration')
 elif name=='dup-lifetime':
  for kind in ['fetch','rpc','wrapped','lazy-env','lazy-exports']:
   ok(req('/'+kind+'/keep')['body']=='kept','retain '+kind)
   expected=('wrapped:' if kind=='wrapped' else 'lazy:' if kind.startswith('lazy') else '')+'resolved:later'
   ok(req('/'+kind+'/use')['body']==expected,'use independently retained '+kind)
  log=rt.out/'socket-client.log';code,_=command(['node',rt.stage/'client.mjs','ws://127.0.0.1:'+str(rt.port)+'/socket'],rt.stage,log,35,clean_env());value=log.read_text().strip();seen.append({'websocket':value});ok(code==0 and value=='lazy:resolved:hi','retained websocket callback lease')
 elif name=='placement':
  for n in range(5):fetch(9830+n,{'path':'/rebalance/pause','json':{}})
  deadline=time.monotonic()+60
  while time.monotonic()<deadline:
   if 'fleet_sample_refreshed' in (rt.out/'node-0-1.log').read_text():break
   time.sleep(.25)
  else:raise AssertionError('live fleet sample absent')
  for i in range(20):ok(req('/pinned?n=p'+str(i))['body']=='pinned','pinned call')
  for i in range(5):ok(req('/free?n=f'+str(i))['body']=='free','free call')
  placed={}
  for n in range(5):
   for scope in fetch(9830+n,{'path':'/state'})['body']['residents']:
    cls=scope.split(':')[0];placed.setdefault(cls,{});placed[cls][n]=placed[cls].get(n,0)+1
  seen.append({'placed':placed});ok(set(placed.get('Pinned',{}))=={1,2} and sum(placed['Pinned'].values())==20 and placed.get('Free')=={0:5},'class placement constraints and distribution')
 elif name=='facet-clone':
  a=[{'k':'late','v':'after-clone-call'},{'k':'one','v':'a1'},{'k':'two','v':'a2-after-clone'}];child=[{'k':'nested','v':'c1'}];b=[{'k':'one','v':'a1'},{'k':'three','v':'b3'}]
  initial=req('/prepare')['body'];ok('Facet was cloned-over.' in initial['destinationAborted'] and 'Facet was cloned-over.' in initial['selfAborted'],'destination and self aborts')
  ok(initial['sourceDuring']==a[:2] and initial['sourceAfter']==a and initial['selfAfter']==a,'source survives clone and self data retained')
  if hasattr(rt,'fleet'):
   for n in list(rt.fleet.nodes):
    try:fetch(9830+n,{'path':'/shutdown?handoff=preserve','method':'POST','body':'','timeout':20})
    except Exception:pass
    rt.fleet.stop_node(n,False)
   time.sleep(5);rt.fleet.start(1);rt.port=9821
  else:
   from common import Process
   args=rt.process.args;rt.process.stop();rt.process=Process(args,rt.out,rt.out/'restart.log',rt.env);time.sleep(1)
  ok(req('/reclone')['body']=={'e':a,'eChild':child},'nested bucket-only source cloned after cold restart')
  ok(req('/report')['body']=={'a':a,'aChild':child,'b':b,'bChildCopied':child,'bChildReplaced':[]},'clone subtree replacement survives restart')
 elif name in ['timeout-implicit-cancel','unhandled-rejection-handler4','web-socket-url-validation']:
  endpoint=case['requests'][0]['path'];ok(req(endpoint)['status']==200,'unchanged upstream assertions')
  delay=101 if name=='timeout-implicit-cancel' else 1;time.sleep(delay)
  ok(rt.process.p.poll() is None,'runtime survives after original I/O context returns');ok(req('/validateGlobalThis')['status']==200,'fresh I/O context responds after observation window')
  if name=='timeout-implicit-cancel':ok('boom' not in (rt.out/'runtime.log').read_text(),'100-second exception was implicitly cancelled')
 elif name=='wsecho':
  import base64,hashlib,os,struct
  key=base64.b64encode(os.urandom(16)).decode();s=socket.create_connection(('127.0.0.1',rt.port),timeout=5)
  try:
   s.sendall(('GET / HTTP/1.1\r\nHost: suite.test\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: '+key+'\r\nSec-WebSocket-Version: 13\r\n\r\n').encode());headers=b''
   while b'\r\n\r\n' not in headers:headers+=s.recv(1)
   ok(headers.startswith(b'HTTP/1.1 101'),'websocket handshake')
   def frame(op,payload):
    mask=os.urandom(4);s.sendall(bytes([128|op,128|len(payload)])+mask+bytes(b^mask[i%4] for i,b in enumerate(payload)))
   frame(1,b'phase2');head=s.recv(2);length=head[1]&127;body=b''
   while len(body)<length:body+=s.recv(length-len(body))
   seen.append({'websocket':body.decode()});ok(json.loads(body)=={'echo':'phase2','count':1},'websocket echo and durable count');frame(8,struct.pack('!H',1000))
  finally:s.close()
 else:raise RuntimeError('unknown example check '+name)
 return seen

def run(case,runtimes,out):
 rows=[]
 for runtime in runtimes:
  rt=None;fleet=None;peer=None;directory=out/runtime;art=directory/'observations.json';t=time.monotonic()
  try:
   source=ROOT/case['fixture'];name=case['id'].split('/')[-1]
   if name=='wasm':
    from .fleet import BASE
    from common import sha
    built=BASE/'tools/wasm-example';source=out/('built-wasm-'+runtime);shutil.copytree(ROOT/case['fixture'],source)
    for p in (ROOT/case['fixture']).rglob('*'):
     if p.is_file() and p.name!='README.md':assert sha(p)==sha(built/p.relative_to(ROOT/case['fixture'])),'WASM source build mismatch'
    shutil.copytree(built/'build',source/'build');shutil.copy2(built/'Cargo.lock',source/'Cargo.lock');dump(out/('wasm-build-'+runtime+'.json'),{'input':str(built),'receipt':json.loads((BASE/'tools/wasm-build-receipt.json').read_text())})
   if name=='do-environment':
    if runtime=='workerd':raise Unavailable('Wrangler environment selector validation belongs to celld deployment CLI')
    from runtime import executable
    directory.mkdir(parents=True);log=directory/'rejection.log';code,_=command([executable('celld'),'deploy',source,'--dry-run'],ROOT,log,30,clean_env());message=log.read_text()
    if code==0 or not all(word.lower() in message.lower() for word in ['environment','no Wrangler environments']):raise AssertionError('unsupported named environment was not explicitly rejected')
    values=[{'exit':code,'deployment_rejected':True}]
   else:
    if name=='placement' and runtime=='workerd':raise Unavailable('CELLD_PLACEMENT and shared capacity samples are celld-specific')
    if name=='web-socket-url-validation':
     from .peer import Peer
     from common import sha
     source=out/('relocated-'+runtime);shutil.copytree(ROOT/case['fixture'],source);p=source/'upstream.js';before=sha(p);p.write_text(p.read_text().replace('ws://username@domain.com','ws://username@127.0.0.1:9870/echo'));dump(out/('relocation-'+runtime+'.json'),{'source_sha256':before,'staged_sha256':sha(p),'change':'only valid websocket authority relocated; assertions unchanged'});peer=Peer();peer.__enter__()
    if runtime=='celld' and name in ['ws-relay','dup-lifetime','placement','facet-clone']:
     from .fleet import Fleet
     settings={'CELLD_REBALANCE_INTERVAL_MS':'1000'}
     if name=='ws-relay':settings['CELLD_PLACEMENT']=json.dumps({'Room':['suite-node-1']})
     if name=='dup-lifetime':settings['CELLD_PLACEMENT']=json.dumps({'Gate':['suite-node-0'],'Planet':['suite-node-1']})
     if name=='placement':settings['CELLD_PLACEMENT']=json.dumps({'Pinned':['suite-node-1','suite-node-2']})
     fleet=Fleet.__new__(Fleet);fleet.__init__(source,directory,settings);rt=types.SimpleNamespace(port=9820,stage=source,out=directory,fleet=fleet);time.sleep(2)
    else:rt=Runtime(source,runtime,directory)
    values=check(case,rt)
    if fleet:
     residents={n:fetch(9830+n,{'path':'/state'})['body']['residents'] for n in fleet.nodes};values.append({'process_residents':residents})
     if name in ['ws-relay','dup-lifetime']:
      expected={'Room':1} if name=='ws-relay' else {'Planet':1,'Gate':0}
      for cls,node in expected.items():
       actual={n for n,scopes in residents.items() if any(scope.startswith(cls+':') for scope in scopes)}
       if actual!={node}:raise AssertionError('cross-process placement witness failed for '+cls+': '+str(actual))
   dump(art,values);status='pass';reason='finite behaviour assertions and teardown passed' 
  except Exception as e:
   status='not-applicable' if isinstance(e,Unavailable) else 'fail';reason=str(e);dump(art,{'error':str(e),'traceback':traceback.format_exc()})

  finally:
   if rt and hasattr(rt,'stop'):rt.stop()
   if fleet:fleet.close()
   if peer:peer.__exit__()
  rows.append(result(case,runtime,status,reason,int((time.monotonic()-t)*1000),[art,directory/'trace.json',directory/'runtime.json',directory/'runtime.log',directory/'bundle.log']))
 return rows
