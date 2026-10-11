"""C6-01: bounded memory under cross-node calls, lease churn and held exports across pool churn."""
import json,os,sys,time,pathlib,concurrent.futures as cf
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent))
import lab_fleet
if os.environ.get('CELLD_TEST_RUNTIME','celld')!='celld':
    print('celld isolate pool retirement; stock workerd runs one isolate per worker');sys.exit(77)
if lab_fleet.available():print(lab_fleet.available());sys.exit(77)
if sys.platform!='linux':print('requires /proc RSS sampling');sys.exit(77)
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);base=int(os.environ.get('CELLD_TEST_PORT_BASE','9900'))
cycles=2 if os.environ.get('CELLD_TEST_PROFILE')=='quick' else 5
f=lab_fleet.Fleet(os.environ['CELLD_BIN'],pathlib.Path(__file__).resolve().parent,art,['ingress','owner'],placement={'Holder':['owner']},base=base)
samples=[];calls=0;errors=0
def services():
    iso=f.state(1)['deployment']['isolates']
    return iso.get('services',{}).get('lab-memory-svc',{})
try:
    f.start()
    for _ in range(200):
        if f.get(0,'/stats')[0]==200:break
        time.sleep(.2)
    with cf.ThreadPoolExecutor(8) as ex:
        for cycle in range(cycles):
            # Busy: the owner's stateless service pool grows; every request
            # also opens a session the actor holds for its whole life.
            end=time.monotonic()+20
            while time.monotonic()<end:
                for s,v,ms in ex.map(lambda _:f.get(0,'/burst?n=200&open=1',120),range(8)):
                    if s==200 and isinstance(v,dict):calls+=v['calls']+2*v['leases']+1
                    else:errors+=1
            # Idle: four 30 s reaper passes retire the grown isolates.
            time.sleep(125)
            pool=services()
            samples.append({'cycle':cycle,'calls':calls,'errors':errors,'rss_kb_owner':f.rss_kb('owner'),'retiring':pool.get('retiring'),'live':pool.get('live'),'heap_bytes':pool.get('heap_bytes'),'held':f.get(0,'/stats')[1]})
            print(json.dumps(samples[-1]),flush=True)
    pings=f.get(0,'/pingall')[1]
finally:
    f.stop()
held=samples[-1]['held']['held'] if samples else 0
ok=errors==0 and all(s['retiring']==0 for s in samples) and pings.get('ok')==held and not pings.get('err')
summary={'pass':ok,'calls':calls,'errors':errors,'samples':samples,'pingall':{'ok':pings.get('ok'),'errors':len(pings.get('err',[]))}}
(art/'summary.json').write_text(json.dumps(summary,indent=1));print(json.dumps({k:summary[k] for k in ('pass','calls','errors')}))
sys.exit(0 if ok else 1)
