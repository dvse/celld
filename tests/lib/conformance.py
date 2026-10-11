from pathlib import Path
import difflib,json,time,shutil
from common import ROOT,dump,result,safe_id
from runtime import Runtime,Unavailable,fetch

def canonical(value):
    # Only runtime-generated identity fields, proven equal/distinct by fixture
    # assertions, are renamed. Payloads, error strings and timing stay exact.
    if not isinstance(value,dict):return value
    identities={}
    for role in ('origin','owner'):
        obj=value.get(role)
        if isinstance(obj,dict):
            for key in ('isolate','root'):
                if isinstance(obj.get(key),str):identities[obj[key]]=f'<{role}.{key}>'
    def walk(v):
        if isinstance(v,str):return identities.get(v,v)
        if isinstance(v,list):return [walk(x) for x in v]
        if isinstance(v,dict):return {k:walk(x) for k,x in v.items()}
        return v
    return walk(value)
def run_group(cases,runtimes,out):
    if cases[0].get("campaign"):
        from phase2.campaign import run_group as run_campaign
        return run_campaign(cases,runtimes,out)
    observations={};rows=[]
    for runtime in runtimes:
        rt=None;directory=out/runtime;started=time.monotonic()
        try:
            source=ROOT/cases[0]['fixture']
            if cases[0].get('corpus_wave')=='base':
                source=out/'accepted-base';shutil.copytree(ROOT/cases[0]['fixture'],source,dirs_exist_ok=True)
                # Current accepted R027 replaces its historical body, once.
                shutil.copy2(ROOT/'tests/conformance/durable-objects/persistent-stubs/fixtures/transient-storage-rejection/rpc.js',source/'rpc.js')
            rt=Runtime(source,runtime,directory,cases[0].get('split_isolates',False))
            for case in cases:
                t=time.monotonic();art=directory/(safe_id(case['id'])+'.json')
                try:
                    steps=case.get('requests',[{'path':'/'}]);observed=[]
                    for step in steps:
                        if step.get('delay_before'):time.sleep(step['delay_before'])
                        observed.append(fetch(rt.port,step))
                    dump(art,observed);observations[(case['id'],runtime)]=observed
                    bad=any(x['status']!=200 or (isinstance(x['body'],dict) and x['body'].get('status') in ('FAIL','BLOCKED')) for x in observed)
                    status='fail' if bad else 'pass';why='fixture observation captured; comparison pending' if not bad else 'fixture assertion, prerequisite, or HTTP execution failed (see observation)'
                    # Fixture BLOCKED means trace was not entered; retain the
                    # precise explanation instead of converting it to a pass.
                    if any(isinstance(x['body'],dict) and x['body'].get('status')=='BLOCKED' for x in observed):status='not-applicable';why=json.dumps(observed[-1]['body'])[:700]
                    rows.append(result(case,runtime,status,why,round((time.monotonic()-t)*1000),[art,directory/'runtime.log',directory/'runtime.json']))
                except Exception as e:
                    failure={'status':None,'body':{'transport_error':f'{type(e).__name__}: {e}'}}
                    observations[(case['id'],runtime)]=[failure];dump(art,[failure])
                    rows.append(result(case,runtime,'fail',f'{type(e).__name__}: {e}',round((time.monotonic()-t)*1000),[directory/'runtime.log',art]))
        except Exception as e:
            for case in cases:rows.append(result(case,runtime,'not-applicable' if isinstance(e,Unavailable) else 'fail',str(e),round((time.monotonic()-started)*1000),[directory/'runtime.log',directory/'bundle.log',directory/'deploy.log']))
        finally:
            if rt:rt.stop()
    for case in cases:
        pair=[r for r in rows if r['id']==case['id']]
        if len(runtimes)==1:
            for row in pair:
                if row['status']=='pass':row['reason']='single-runtime observation/assertions passed; differential comparison not requested'
            continue
        a=observations.get((case['id'],'celld'));b=observations.get((case['id'],'workerd'))
        if a is None or b is None:
            for row in pair:
                if row['status']=='pass':row.update(status='not-applicable',reason='reference or candidate unavailable; differential verdict requires both observations')
            continue
        a=[{**x,'body':canonical(x['body'])} for x in a];b=[{**x,'body':canonical(x['body'])} for x in b]
        if a!=b:
            diff=out/(safe_id(case['id'])+'.diff');diff.write_text(''.join(difflib.unified_diff(json.dumps(b,indent=2,sort_keys=True).splitlines(True),json.dumps(a,indent=2,sort_keys=True).splitlines(True),fromfile='stock-workerd',tofile='celld')))
            for row in pair:
                # Both executions carry the pair verdict. Raw local statuses
                # remain in the observation artifact.
                row.update(status='fail',reason='differential mismatch versus stock workerd');row['artifacts'].append(str(diff))
        elif all(r['status']=='pass' for r in pair):
            for row in pair:row['reason']='identical candidate/reference observations and fixture assertions passed'
    return rows
