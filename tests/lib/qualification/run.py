#!/usr/bin/env python3
"""Fail-closed operator-adapter protocol; never launch unbounded runtimes implicitly.
Adapter is trusted reviewed control code, not authenticated evidence. No adapter exists
in this program yet. It must establish actual guest limits, witnesses and cleanup.
"""
import argparse,hashlib,json,subprocess,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REQUIRED={'binary_sha256','source_manifest_sha256','profile_sha256','limit_witness','owner_witness','readiness_witness','layer'}
def main():
    p=argparse.ArgumentParser();p.add_argument('--adapter',nargs='+');p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    rows=sum([json.loads(x.read_text()) for x in sorted((ROOT/'cases').glob('*.json'))],[])
    report={'run_id':str(uuid.uuid4()),'fixture_sha256':hashlib.sha256((ROOT/'fixture/index.js').read_bytes()).hexdigest(),'events':[],'cleanup':'NOT_RUN'}
    def call(action,**kw):
        request={'action':action,'run_id':report['run_id'],'fixture':str(ROOT/'fixture'),**kw}
        completed=subprocess.run(a.adapter,input=json.dumps(request),capture_output=True,text=True,timeout=150,check=True)
        return json.loads(completed.stdout)
    try:
        if not a.adapter:raise RuntimeError('BLOCKED: no reviewed bounded deployment adapter supplied; runtime not launched')
        setup=call('start')
        if setup.get('status')!='ok':raise RuntimeError('BLOCKED: adapter setup did not succeed')
        if not REQUIRED<=setup.keys():raise RuntimeError('BLOCKED: missing immutable inputs, limits, ownership or readiness witnesses')
        report['setup']=setup
        for row in rows:
            started=time.monotonic();value=call('case',id=row['id'],timeout_seconds=30)
            if value.get('status') not in {'PASS','FAIL','BLOCKED','NOT_RUN'}:raise RuntimeError('invalid case status')
            # PASS requires assertion-bearing fixture identity and both endpoint witnesses.
            if value['status']=='PASS':
                result=value.get('result',{})
                if result.get('id')!=row['id'] or not {'origin','owner','evidence'}<=result.keys():raise RuntimeError('PASS lacks actual fixture result')
                if result['origin']['isolate']==result['owner']['isolate']:raise RuntimeError('PASS lacks remote recipient context')
            report['events'].append({'id':row['id'],'seconds':time.monotonic()-started,**value})
    except Exception as e:
        report['blocker']=str(e)
    finally:
        if a.adapter:
            try:report['cleanup']=call('stop')
            except Exception as e:report['cleanup']={'status':'FAIL','error':str(e)}
        completed={x['id'] for x in report['events']}
        for row in rows:
            if row['id'] not in completed:report['events'].append({'id':row['id'],'status':'BLOCKED','reason':report.get('blocker','adapter incomplete')})
        a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2)+'\n')
    return 0 if all(x['status']=='PASS' for x in report['events']) and isinstance(report['cleanup'],dict) and report['cleanup'].get('status')=='ok' else 1
if __name__=='__main__':raise SystemExit(main())
