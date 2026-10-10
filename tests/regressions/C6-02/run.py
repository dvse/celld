"""C6-02: an ordered call that never reaches its callee must not stall or break the lane."""
import json,os,pathlib,sys,time
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent))
import lab_fleet
if os.environ.get('CELLD_TEST_RUNTIME','celld')!='celld':
    print('celld multi-process ordering lanes; stock workerd has one Cap\'n Proto connection');sys.exit(77)
if lab_fleet.available():print(lab_fleet.available());sys.exit(77)
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);base=int(os.environ.get('CELLD_TEST_PORT_BASE','9900'))
f=lab_fleet.Fleet(os.environ['CELLD_BIN'],pathlib.Path(__file__).resolve().parent,art,['caller','owner'],placement={'Sink':['owner']},base=base)
rounds=[];ok=True
try:
    f.start()
    for _ in range(150):
        if f.get(1,'/init')[0]==200:break
        time.sleep(.2)
    for r in range(5 if os.environ.get('CELLD_TEST_PROFILE')=='quick' else 20):
        fire=f.get(0,f'/fire?n=3&tag={r}')
        call=f.get(0,f'/call?tag={r}&wait=8000',timeout=30)
        good=fire[0]==200 and call[0]==200 and isinstance(call[1],dict) and isinstance(call[1].get('result'),int) and call[2]<3000
        rounds.append({'round':r,'fire':fire[1],'call':call[1],'call_ms':call[2],'pass':good});ok&=good
        if not good:break
    errors=f.log('caller').count('ordering channel')
    ok&=errors==0
finally:
    f.stop()
summary={'pass':ok,'rounds':rounds,'ordering_errors':errors}
(art/'summary.json').write_text(json.dumps(summary,indent=1));print(json.dumps(summary))
sys.exit(0 if ok else 1)
