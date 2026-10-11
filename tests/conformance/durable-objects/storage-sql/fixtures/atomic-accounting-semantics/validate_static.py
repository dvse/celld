#!/usr/bin/env python3
"""Static packaging/source checks only. Never imports case code or executes SQL."""
import argparse,hashlib,json,pathlib,re,subprocess,sys
H=pathlib.Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--write-report',action='store_true');args=parser.parse_args()
checks=[]
def check(value,label):
    if not value:raise AssertionError(label)
    checks.append(label)
def read(name):return json.loads((H/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
manifest=read('manifest.json');pins=read('source-pins.json');schedule=read('schedule.json');audit=read('overlap-audit.json');config=read('wrangler.jsonc')
source_root=pathlib.Path(pins['source_root']);cases=(H/'cases.js').read_text();fixture=(H/'fixture.js').read_text()
expected=[f'T{i}' for i in range(201,216)]
check(re.findall(r'^  (T2\d\d): \{',cases,re.M)==expected,'15 handwritten exact case IDs T201-T215')
check([r['id'] for r in manifest['cases']]==expected,'manifest and executable case ordering/identity match')
check(manifest['authored']==15 and manifest['independently_reviewed']==0,'author metadata awards no independent review credit')
check(manifest['runtime_executions']==manifest['runtime_passes']==0,'zero self-reported runtime evidence')
for row in manifest['cases']:
    check(row['runtime_status']=='NOT_RUN' and row['actual_runs']==row['runtime_passes']==0,row['id']+' remains NOT_RUN')
    block=cases.split('  '+row['id']+': {',1)[1].split('\n  T2',1)[0]
    for method in ['seed','left','right','verify']:check('async '+method+'(c)' in block,row['id']+' explicit '+method+' body')
    check(block.count('await c.pause()')==1,row['id']+' one literal left checkpoint')
    check(row['literal_assertion_call_sites']==len(re.findall(r'c\.eq\(',block)) and row['literal_assertion_call_sites']>=3,row['id']+' literal case assertions counted separately')
    check(bool(row['oracle']) and bool(row['source_refs']) and bool(row['nearest_existing']),row['id']+' fixed oracle/source/overlap metadata')
    for ref in row['source_refs']:
        path=source_root/ref['path'];check(ref['path'] in pins['files'],row['id']+' source reference is SHA pinned')
        check(1<=ref['line_start']<=ref['line_end']<=len(path.read_text().splitlines()),row['id']+' source range exists')
for path,expected_sha in pins['files'].items():check(sha(source_root/path)==expected_sha,'immutable source pin '+path)
check(len(pins['retained_os_evidence'])==2,'two retained OS context records only')
for item in pins['retained_os_evidence']:
    check(item['status']=='RETAINED_PROVENANCE_NOT_REREAD','OS checkout absence is explicit')
    for origin in item['retained_from']:
        check(item['retained_sha256'] in (source_root/origin).read_text(),'retained OS SHA appears in '+origin)
check(audit['reviewed_baseline_ids']==[f'T{i:03d}' for i in range(1,33)],'all32 T baseline IDs audited')
check(audit['reviewed_d_ids']==[f'D{i}' for i in range(201,221)],'all20 D baseline IDs audited')
check(sha(pathlib.Path(audit['d_cases_file']))==audit['d_cases_sha256'],'D baseline implementation comparison pin')
check(config['main']=='fixture.js' and config['durable_objects']['bindings']==[{'name':'CASE','class_name':'AccountingCase'}],'real SQLite DO binding configured')
check(config['migrations'][0]['new_sqlite_classes']==['AccountingCase'],'SQLite class migration configured')
check(schedule['runtime_status']=='NOT_RUN' and schedule['limits']['internal_do_fetches']==4,'finite four-fetch schedule declared')
for marker in ["Promise.allSettled([send('act/left'),send('act/right')])","this.pendingTransactions.size!==0","this.state.storage.deleteAll()","host.held.resolve()","this.queued.resolve()","this.state.storage.transaction(async storage=>"]:
    check(marker in fixture,'real storage/schedule/cleanup marker '+marker)
check('sqlite3' not in cases+fixture,'no alternate SQL implementation in fixture')
for forbidden in ['eval(', 'new Function(', 'Math.random(', '__storage_', '__sql_', '_transactionRoot', 'setAlarm(', 'WebSocket(', 'process.', 'require(']:check(forbidden not in cases+fixture,'excluded executable feature '+forbidden)
for filename in ['fixture.js','cases.js']:
    result=subprocess.run(['node','--input-type=module','--check'],input=(H/filename).read_text(),text=True,capture_output=True)
    check(result.returncode==0,'syntax only, no execution: '+filename+': '+result.stderr)
report=dict(status='STATIC_CHECKS_PASSED',runtime_status='NOT_RUN',runtime_executions=0,runtime_passes=0,case_count=15,case_literal_assertion_call_sites=sum(r['literal_assertion_call_sites'] for r in manifest['cases']),shared_fixture_assertion_call_sites=len(re.findall(r'(?:this\.eq\(|^\s+host\.eq\()',fixture,re.M)),checks=len(checks),source_hashes_verified=len(pins['files']),mechanism_oracle_review='Independent reviewer required; static checker does not prove runtime correctness, deployability, SQL semantics or actual gate placement.',check_names=checks)
if args.write_report:(H/'static-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items() if key!='check_names'},indent=2))
