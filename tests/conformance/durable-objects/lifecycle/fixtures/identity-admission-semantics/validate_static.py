#!/usr/bin/env python3
"""Syntax, packaging and source-pin checks only; never executes the SUT/fixture."""
import argparse,hashlib,json,pathlib,re,subprocess
H=pathlib.Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--write-report',action='store_true');args=p.parse_args()
def read(name):return json.loads((H/name).read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
checks=[]
def check(value,label):
 if not value:raise AssertionError(label)
 checks.append(label)
m=read('manifest.json');pins=read('source-pins.json');schedule=read('schedule.json');audit=read('overlap-audit.json');config=read('wrangler.jsonc')
S=pathlib.Path(pins['source_root']);cases=(H/'cases.js').read_text();fixture=(H/'fixture.js').read_text();expected=['A201','A202','A203','A204','A205']
check(re.findall(r'^  async (A\d+)\(c\)',cases,re.M)==expected,'five handwritten IDs in independent A201-A205 scope')
check([r['id']for r in m['cases']]==schedule['run_order']==expected,'manifest/executable/schedule identity agreement')
check(m['authored_case_count']==5 and m['independently_reviewed']==0,'five author candidates, zero self-awarded independent review credit')
check(m['runtime_status']=='UNRUN' and m['runtime_executions']==m['runtime_passes']==0,'all runtime evidence stays UNRUN')
check(not m['actual_os_checkout_available'] and not pins['actual_os_checkout_available'],'OS checkout absence explicit')
for row in m['cases']:
 block=cases.split('  async '+row['id']+'(c) {',1)[1].split('\n  async A',1)[0]
 assertions=[line.strip()for line in block.splitlines()if 'c.eq(' in line]
 check(row['fixed_assertions']==assertions and row['literal_assertion_call_sites']==len(assertions)>=5,row['id']+' exact fixed nonempty assertion text')
 check(row['runtime_status']=='UNRUN' and row['actual_runtime_executions']==row['runtime_passes']==0,row['id']+' zero runtime credit')
 check(row['review_status']=='PENDING_INDEPENDENT_REVIEW',row['id']+' independent review not self-awarded')
 check(bool(row['distinct']) and bool(row['nearest']) and row['os_relevance']['evidence_status']=='INFERRED_COMPONENT_RELEVANCE_ONLY',row['id']+' overlap and OS limits present')
 for ref in row['primary_contract_refs']+row['runtime_source_refs']:
  check(ref['path']in pins['files'],row['id']+' source reference pinned')
  check(1<=ref['line_start']<=ref['line_end']<=len((S/ref['path']).read_text().splitlines()),row['id']+' exact source line range exists')
for path,digest in pins['files'].items():check(sha(S/path)==digest,'immutable source pin '+path)
for path,digest in audit['new_wave_baseline_pins'].items():check(sha(H.parent/path)==digest,'nearest authored baseline pin '+path)
check(m['cases'][2]['static_source_assessment']=='SOURCE_PREDICTED_COMPATIBILITY_FAILURE','A203 intended client contract preserved despite source-predicted gap')
check("c.eq(stubs.map(s=>s.name),names," in cases,'full client stub-name oracle, never shortened to source behavior')
check(len(audit['oracle_review_notes'])==2,'review ambiguity and corrected client-name oracle are recorded')
check(audit['selected_count']==5 and len(audit['case_distinctions'])==5,'one compound mechanism per five audited rows')
check(config['main']=='fixture.js' and config['compatibility_date']=='2026-09-04','explicit fixture and compatibility date')
check(config['durable_objects']['bindings']==[{'name':'RECORD','class_name':'Record'},{'name':'CONTROL','class_name':'Control'},{'name':'INIT','class_name':'InitTarget'},{'name':'EVENT','class_name':'EventTarget'}],'real public DO bindings')
check(config['migrations'][0]['new_sqlite_classes']==['Record','Control','InitTarget','EventTarget'],'four real migrated SQLite classes')
check(schedule['runtime_status']=='UNRUN' and schedule['limits']['max_created_roots']==3,'bounded real-root schedule stays UNRUN')
for marker in ["state.blockConcurrencyWhile(async()=>","this.state.blockConcurrencyWhile(async()=>","this.timer=setTimeout(()=>this.release(false),2500)","if(settled){try{cleanup=", "await bounded(Promise.allSettled([...this.pending])", "state.storage.deleteAll()", "i<60", "this.owned.length>=3", "this.calls>100", "this.waiters||this.timer", "c.env.EVENT.getByName(c.run+':peer')"]:
 check(marker in fixture+cases,'finite genuine schedule/cleanup marker '+marker)
check((fixture+cases).count('blockConcurrencyWhile(async()=>')==2,'exactly one constructor and one ordinary request block; no nested or contended additions')
for forbidden in ['__do_', '__gate_', '__storage_', '__io_context', 'new Map(', 'newUniqueId({', '.abort(', '.facets', '.transaction(', 'new Worker(', 'process.', 'require(', 'setAlarm(', 'WebSocket(', 'eval(', 'new Function(']:
 check(forbidden not in fixture+cases,'excluded executable feature '+forbidden)
for file in ['fixture.js','cases.js']:
 result=subprocess.run(['node','--input-type=module','--check'],input=(H/file).read_text(),text=True,capture_output=True)
 check(result.returncode==0,'syntax only, no execution: '+file+': '+result.stderr)
report={'status':'STATIC_CHECKS_PASSED','runtime_status':'UNRUN','runtime_executions':0,'runtime_passes':0,'case_count':5,'literal_case_assertion_call_sites':sum(r['literal_assertion_call_sites']for r in m['cases']),'source_hashes_verified':len(pins['files']),'checks':len(checks),'not_proven':'Deployability, runtime gate behavior, process placement, replication durability, cleanup and actual OS behavior remain unexecuted; independent review is separate.','check_names':checks}
if args.write_report:(H/'static-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='check_names'},indent=2))
