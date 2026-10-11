"""Finite original case protocols over an owned five-process fleet."""
import importlib.util,json,os,re,shutil,time,traceback,uuid
from pathlib import Path
from common import ROOT,TESTS,dump,result,safe_id,sha
from runtime import Runtime,fetch,Unavailable,load_config
from .fleet import Fleet
BASE_FIXTURE=TESTS/'conformance/rpc/fixtures/object-capabilities/fixture'
def stage(source,out,wave):
 dest=out/'staging/waves'/wave;shutil.copytree(source,dest)
 base=out/'staging/fixture';shutil.copytree(BASE_FIXTURE,base)
 shutil.copy2(TESTS/'conformance/durable-objects/persistent-stubs/fixtures/transient-storage-rejection/rpc.js',base/'rpc.js')
 if wave=='base':shutil.copy2(base/'rpc.js',dest/'rpc.js')
 if wave=='do-visibility-regression':shutil.copy2(base/'index.js',dest/'base-index.js');shutil.copy2(base/'rpc.js',dest/'rpc.js')
 changes=[]
 # Defer global random identity creation until the first real DO constructor.
 # This preserves one identity per isolate and permits stock workerd startup.
 for p in list(dest.rglob('*.js'))+list(base.rglob('*.js')):
  before=p.read_text();s=before
  for name in re.findall(r'const\s+(\w+)\s*=\s*crypto.randomUUID\(\)\s*;',s):
   if name.upper()!=name:continue
   s=re.sub(r'const\s+'+name+r'\s*=\s*crypto.randomUUID\(\)\s*;', 'let '+name+';',s)
   # Initial assignment occurs on ordinary construction, once for this module.
   s=re.sub(r'(super\([^;]*\);)',r'\1 '+name+' ??= crypto.randomUUID();',s)
  if wave in ['http-stream-stress','fetch-redirect-stress','active-websocket-stress']:
   s=s.replace('192.168.77.1','127.0.0.1').replace('18080','9821')
  s=s.replace('http://192.168.77.2:19000','http://127.0.0.1:9840')
  if s!=before:p.write_text(s);changes.append({'file':str(p),'original_sha256':__import__('hashlib').sha256(before.encode()).hexdigest(),'staged_sha256':sha(p),'reason':'defer isolate identity until constructor / owned private origin relocation'})
 for cfg in [*dest.glob('wrangler.json'),*dest.glob('wrangler.jsonc')]:
  before=cfg.read_text();s=before.replace('http://192.168.77.1:18080','http://127.0.0.1:9821')
  if s!=before:cfg.write_text(s);changes.append({'file':str(cfg),'original_sha256':__import__('hashlib').sha256(before.encode()).hexdigest(),'staged_sha256':sha(cfg),'reason':'owned private streaming origin'})
 # Metadata exports are useful to the source corpus but are not legal
 # Workers named entrypoints. Keep their definitions/imports untouched and
 # use a wrapper exposing only the authored Worker and DO entrypoints.
 for cfg in [*dest.glob('wrangler.json'),*dest.glob('wrangler.jsonc')]:
  config=load_config(cfg);entry=dest/config['main'];text=entry.read_text()
  metadata=re.findall(r'^export const (WAVE|PROFILE)\s*=',text,re.M)
  if metadata:
   names=re.findall(r'^export class (\w+)',text,re.M)
   wrapper=dest/'phase2-entry.js';wrapper.write_text('export {default, '+', '.join(names)+'} from '+json.dumps('./'+config['main'])+';\n')
   before=sha(cfg);config['main']=wrapper.name;cfg.write_text(json.dumps(config,indent=2)+'\n')
   changes.append({'file':str(cfg),'original_sha256':before,'staged_sha256':sha(cfg),'reason':'entry wrapper excludes non-handler metadata exports '+','.join(metadata),'wrapper_sha256':sha(wrapper),'source_assertions':'unchanged'})
 if wave=='os-git-codec-semantics':
  built=Path.home()/'celld-tests-20261010/phase2/tools/pako-3.0.2/built';receipt=json.loads((built.parent/'BUILD.json').read_text())
  for name,digest in receipt['built_files'].items():assert sha(built/name)==digest
  shutil.copytree(built,dest/'node_modules/pako');dump(out/'pako-build.json',receipt)
 dump(out/'staging.json',changes);return dest

def require_response(r):
 if r['status']!=200:raise AssertionError('HTTP '+str(r['status'])+': '+json.dumps(r['body'])[:600])
 return r['body']
def protocol(case,request):
 wave=case.get('corpus_wave');id=case['selector'];run=os.urandom(8).hex();caller=id+'-caller-'+run;peer=id+'-peer-'+run;second=id+'-second-'+run
 def req(node,path,payload=None):return require_response(request(node,{'path':path,**({'json':payload} if payload is not None else {}),'timeout':32}))
 if wave in ['base','rpc-codec','capability-order','bounded-load','do-visibility-regression']:
  origin=req(0,'/identity',{'root':caller});owner=req(1,'/identity',{'root':peer})
  value=request(0,{'path':'/run','json':{'id':id,'root':caller,'peer':peer,'requestId':str(uuid.uuid4())},'timeout':40})
  return {'identities':{'origin':origin,'owner':owner},'response':value}
 if wave in ['sqlite-concurrency','native-transform-stress']:
  origin=req(0,'/identity',{'name':caller,'role':'caller'});primary=req(1,'/identity',{'name':peer,'role':'recipient'});secondary=req(2,'/identity',{'name':second,'role':'recipient'})
  return {'identities':{'caller':origin,'primary':primary,'secondary':secondary},'response':request(0,{'path':'/run','json':{'id':id,'run':run,'name':caller,'primary':peer,'secondary':second,'expectedCaller':origin,'expectedPrimary':primary,'expectedSecondary':secondary},'timeout':60})}
 if wave=='loader-props':return {'response':request(0,{'path':'/run','json':{'id':id,'tag':id+':'+str(uuid.uuid4())},'timeout':30})}
 if wave=='bounded-resource':return {'response':request(0,{'path':'/run','json':{'id':id,'root':caller,'requestId':str(uuid.uuid4())},'timeout':40})}
 if wave in ['http-stream-stress','fetch-redirect-stress','active-websocket-stress']:
  origin=req(0,'/root/'+caller+'/identity');owner=req(1,'/root/'+peer+'/identity')
  return {'identities':{'caller':origin,'recipient':owner},'response':request(0,{'path':'/root/'+caller+'/run','json':{'id':id,'run':run,'recipient':peer,'expectedCaller':origin,'expectedRecipient':owner},'timeout':40})}
 raise RuntimeError('unimplemented protocol '+str(wave))

def classify(observation):
 response=observation['response'];body=response['body']
 if not isinstance(body,dict):return 'fail','non-JSON fixture response'
 status=body.get('status',body.get('fixtureStatus'))
 if status in ['PASS','ASSERTIONS_SATISFIED'] and response['status']==200:
  if any(isinstance(x,dict) and x.get('satisfied') is False for x in body.get('assertions',[])):return 'fail','fixture reports a false assertion'
  if isinstance(body.get('cleanup'),dict) and body['cleanup'].get('status') in ['FAIL','UNKNOWN']:return 'fail','fixture cleanup did not complete'
  return 'pass','original finite trace and assertions completed; owned process evidence retained'
 # A supplied harness attempting a supported feature is a failing runtime
 # observation, not a reason to exclude the case before execution.
 return 'fail','fixture '+str(status)+': '+str(body.get('error',body.get('blocker',body.get('reason','see observation'))))[:700]

def run_group(cases,runtimes,out):
 out.mkdir(parents=True,exist_ok=True);wave=cases[0]['corpus_wave'];source=stage(ROOT/cases[0]['fixture'],out,wave);rows=[]
 for runtime in runtimes:
  directory=out/runtime;rt=None;fleet=None
  try:
   if runtime=='celld':
    fleet=Fleet.__new__(Fleet);fleet.__init__(source,directory);request=fleet.req
   else:
    rt=Runtime(source,runtime,directory,True,True);request=lambda n,step:fetch(9810 if n==0 else 9813,step)
   for case in cases:
    guard=fleet.guard if fleet else rt.guard;guard.begin(case['id'],90)
    t=time.monotonic();art=directory/(safe_id(case['id'])+'.json')
    try:
     observation=protocol(case,request);dump(art,observation)
     if fleet and observation.get('identities'):
      owners={role:fleet.owner(value['root']) for role,value in observation['identities'].items()}
      observation['process_owners']=owners
      # Corroborate fixture identities against actual bucket ownership.
      expected={role:'suite-node-'+str(n) for n,role in enumerate(observation['identities'])}
      observation['placement_matches']=all(owners[k]['node']==v for k,v in expected.items())
      if not observation['placement_matches']:raise AssertionError('recipient owner placement differs from separately witnessed ingress allocation')
     dump(art,observation);status,reason=classify(observation)
    except Exception as e:
     dump(art.with_suffix('.error.json') if art.exists() else art,{'error':str(e),'traceback':traceback.format_exc()});status='fail';reason=str(e)[:700]
    guard.end()
    rows.append(result(case,runtime,status,reason,int((time.monotonic()-t)*1000),[art,directory/'fleet.json',directory/'runtime.json',directory/'oracle-routing.json',directory/'runtime.log',out/'staging.json']))
    print(status,runtime,case['id'],flush=True)
  except Exception as e:
   art=directory/'setup-error.json';dump(art,{'error':str(e),'traceback':traceback.format_exc()})
   rows.extend(result(c,runtime,'not-applicable' if isinstance(e,Unavailable) else 'fail',str(e),artifacts=[art,out/'staging.json']) for c in cases)
  finally:
   if fleet:
    try:fleet.close()
    except Exception as e:
     dump(directory/'cleanup-error.json',{'error':str(e)})
     for row in rows:
      if row['runtime']==runtime:row.update(status='fail',reason='owned cleanup failed: '+str(e))
   if rt:rt.stop()
 for row in rows:
  guard_file=out/row['runtime']/'resource-guard.json'
  if guard_file.exists():
   row['artifacts'].append(str(guard_file))
   if json.loads(guard_file.read_text())['violations']:row.update(status='fail',reason='independent resource/deadline guard rejected qualification; see resource-guard.json')
 for case in cases:
  pair={r['runtime']:{'status':r['status'],'reason':r['reason']} for r in rows if r['id']==case['id']}
  if set(pair)=={'celld','workerd'}:
   artifact=out/(safe_id(case['id'])+'.comparison.json');dump(artifact,{'source_contract':case.get('contract'),'outcomes':pair,'same_source_assertion_verdict':pair['celld']['status']==pair['workerd']['status'],'policy':'source-authored assertions evaluated independently; generated identities and timestamps are witnesses, not paired payloads'})
   for row in rows:
    if row['id']==case['id']:row['artifacts'].append(str(artifact))
 return rows
