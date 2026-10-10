"""C6-03: idle peer connections are evicted by the client before the server's header timeout."""
import json,os,re,subprocess,sys,time,pathlib,threading
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent))
import lab_fleet
if os.environ.get('CELLD_TEST_RUNTIME','celld')!='celld':
    print('celld peer HTTP keep-alive between nodes; no stock workerd counterpart');sys.exit(77)
if lab_fleet.available():print(lab_fleet.available());sys.exit(77)
if sys.platform!='linux':print('requires Linux ss(8)');sys.exit(77)
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);base=int(os.environ.get('CELLD_TEST_PORT_BASE','9900'))
cycles=2 if os.environ.get('CELLD_TEST_PROFILE')=='quick' else 4
f=lab_fleet.Fleet(os.environ['CELLD_BIN'],pathlib.Path(__file__).resolve().parent,art,['planet','edge'],placement={'Target':['edge']},base=base)
def established():
    ports={f.public(1),f.internal(1)};n=0
    for line in subprocess.run(['ss','-tnH','state','established'],capture_output=True,text=True).stdout.splitlines():
        c=line.split()
        if len(c)>=4 and int(c[3].rsplit(':',1)[1]) in ports and int(c[2].rsplit(':',1)[1]) not in ports:n+=1
    return n
rows=[]
try:
    f.start()
    for _ in range(200):
        if f.get(0,'/init')[0]==200:break
        time.sleep(.2)
    edge=f'http://127.0.0.1:{f.public(1)}'
    for c in range(cycles):
        s,v,ms=f.get(0,f'/burst?n=120&edge={edge}',timeout=120)
        time.sleep(2);settled=established()
        time.sleep(35)  # beyond the server's 30 s header-read timeout
        rows.append({'cycle':c,'status':s,'result':v,'idle_pooled_after_burst':settled,'after_idle':established()})
    log=f.log('edge')
    timeouts=max([int(x) for x in re.findall(r'cause="timeout" cause_total=(\d+)',log)],default=0)
finally:
    f.stop()
ok=timeouts==0 and all(r['status']==200 and r['idle_pooled_after_burst']<=40 for r in rows)
summary={'pass':ok,'edge_header_timeouts':timeouts,'cycles':rows}
(art/'summary.json').write_text(json.dumps(summary,indent=1));print(json.dumps(summary))
sys.exit(0 if ok else 1)
