"""C7-01: a stateless fetch handler returns a Response it received over RPC.

Two nodes (ingress, owner). The router's service binding route() returns the
gatekeeper's Response; the router returns it as its own response, so the node
pumps an RPC body stream after the handler returned. Every ingress must answer
the published statuses with complete bodies, never an empty reply."""
import json,os,sys,time,pathlib,http.client
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent))
import lab_fleet
if os.environ.get('CELLD_TEST_RUNTIME','celld')!='celld':
    print('celld multi-node fleet (service binding + placed Durable Object)');sys.exit(77)
if lab_fleet.available():print(lab_fleet.available());sys.exit(77)
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);base=int(os.environ.get('CELLD_TEST_PORT_BASE','9900'))
f=lab_fleet.Fleet(os.environ['CELLD_BIN'],pathlib.Path(__file__).resolve().parent,art,['ingress','owner'],placement={'Owner':['owner'],'Routes':['owner']},base=base)
def get(i,path):
    c=http.client.HTTPConnection('127.0.0.1',f.public(i),timeout=30)
    try:
        c.request('GET',path);r=c.getresponse();body=r.read().decode(errors='replace')
        return [r.status,body]
    except Exception as e:return ['error',type(e).__name__]
    finally:c.close()
expected={'/p/nosuch':[404,'Published application not found.'],'/p/stream':[200,'local0;local1;local2;'],
          '/p/owner/x':[200,'owner0;owner1;owner2;'],'/p/owner/unauth':[401,'auth required'],
          '/do/stream':[200,'local0;local1;local2;'],'/do/owner/x':[200,'owner0;owner1;owner2;'],
          '/read?path=/p/nosuch':[200,json.dumps({'status':404,'text':'Published application not found.'},separators=(',',':'))]}
results={};ok=True
try:
    f.start()
    # The owner node may need a moment to take the placed objects.
    for _ in range(150):
        if get(0,'/read?path=/p/owner/x')[0]==200:break
        time.sleep(.2)
    for i in (0,1):
        for path,want in expected.items():
            got=get(i,path);results[f'{f.names[i]} {path}']=got
            if got!=want:ok=False
            print(json.dumps({'node':f.names[i],'path':path,'got':got,'pass':got==want}),flush=True)
finally:
    f.stop()
(art/'result.json').write_text(json.dumps({'pass':ok,'results':results,'expected':expected},indent=1))
sys.exit(0 if ok else 1)
