#!/usr/bin/env python3
"""Small text/JSON/TOML/hash preflight. Never compiles, imports or runs the SUT."""
import ast,hashlib,json,pathlib,re,sys,tomllib
W=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
errors=[]
def check(ok,msg):
    if not ok: errors.append(msg)
for name in ['author_manifest.py','validate.py']: ast.parse((W/name).read_text(),name)
m=json.loads((W/'manifest.json').read_text()); pins=json.loads((W/'source-pins.json').read_text())
profile=json.loads((W/'profile.json').read_text()); adapter=json.loads((W/'adapter-plan.json').read_text())
code=(W/'tests/pressure_recovery.rs').read_text()
starts=list(re.finditer(r'#\[test\]\s*fn (p\d{3}_[a-z0-9_]+)\(',code)); names=[v.group(1) for v in starts]
check(len(m)==len(names)==26,'expected26 explicit Rust test bodies and manifests')
check([c['id'] for c in m]==[f'P{i:03}' for i in range(1,27)],'stable ID range')
check(len(set(names))==26 and set(names)=={c['test_function'] for c in m},'function mapping')
check(len({c['intent'] for c in m})==26 and len({c['failure_hypothesis'] for c in m})==26,'intent/hypothesis text duplicates')
char={'P009','P010','P013','P021'}
for c in m:
    for key in ('id','intent','failure_hypothesis','preconditions','initial_state','trace','stress','safety_oracle','liveness_oracle','terminal_witness','cleanup','implementation','test_function','classification'):
        check(bool(c.get(key)),c['id']+': missing '+key)
    check(isinstance(c['trace'],list) and len(c['trace'])>=4,c['id']+': finite ordered trace')
    check(c['implementation']=='tests/pressure_recovery.rs:'+c['test_function'],c['id']+': wrong source mapping')
    check(c['layer']=='native-component',c['id']+': wrong layer')
    check(c['sublayer']==('public-drain-policy' if c['id'] in {'P025','P026'} else 'state-trace'),c['id']+': wrong sublayer')
    check(c['classification']==('characterization' if c['id'] in char else 'promotion-candidate'),c['id']+': characterization changed')
    check(c['authored'] and c['executable'] and not any(c[k] for k in ['reviewed','compiled','run','passed','promotion']),c['id']+': unearned review/run claim')
    check(c['status']=='NOT_RUN',c['id']+': status not source-only')
body_hashes=[]
for i,v in enumerate(starts):
    body=code[v.end():starts[i+1].start() if i+1<len(starts) else len(code)]
    case=v.group(1)[:4].upper()
    check('assert' in body or 'h.local(' in body,case+': missing explicit assertion')
    if case not in {'P025','P026'}:
        check('h.done();' in body,case+': missing terminal fixture accounting')
        check('H::new("'+case+'")' in body,case+': wrong receipt identity')
        check('h.sample(' in body or 'h.sample_at(' in body,case+': no production load sample')
    else:
        check('TRACE_END '+case in body and 'fleet(' in body,case+': policy receipt missing')
    body_hashes.append(hashlib.sha256(body.encode()).hexdigest())
check(len(set(body_hashes))==26,'duplicate source bodies')
check('on_event(&mut self.s, event)' in code,'production on_event absent')
check('self.s.validate()' in code,'per-step production validation absent')
check('self.count <= 100' in code,'event cap missing')
check('drain::fleet_status(token, "join", now, peers, 2)' in code,'production drain function absent')
check('#[ignore]' not in code and '#[should_panic]' not in code,'ignored/expected-panic test')
check(not re.search(r'\bh\.s\.\w+\s*=',code),'direct State mutation')
check(not any(x in code for x in ('std::process','std::net','thread::spawn','unsafe {','DurableReached','AwaitDurable')),'out-of-scope test code')
for name,digest in pins['test_files'].items(): check(sha(W/name)==digest,'artifact pin '+name)
root=pathlib.Path(pins['source_root'])
for name,digest in pins['production_files'].items():check(sha(root/name)==digest,'production pin '+name)
rmp=pathlib.Path(pins['runtime_manifest']['path']);check(sha(rmp)==pins['runtime_manifest']['sha256'],'delivered manifest pin')
rm=json.loads(rmp.read_text());check(rm['binary_sha256']==pins['delivered_runtime_sha256'],'binary lineage')
for name,digest in pins['production_files'].items():check(rm['source_hashes']['celld/crates/logic/'+name]==digest,'frozen source lineage '+name)
for name,digest in pins['comparison_manifest_hashes'].items():check(sha(W.parent/name/'manifest.json')==digest,'comparison manifest changed '+name)
cargo=tomllib.loads((W/'Cargo.toml').read_text());lock=tomllib.loads((W/'Cargo.lock').read_text())
check(cargo['dependencies']['celld-logic']['path']==str(root),'wrong production path')
check({p['name'] for p in lock['package']}=={'celld-logic','celld-pressure-recovery-stress'} and len(lock['package'])==2,'unexpected dependency')
syntax=json.loads((W/'syntax-check.json').read_text())
check(syntax['returncode']==0 and syntax['input_sha256']==sha(W/'tests/pressure_recovery.rs'),'syntax evidence failed/stale')
check(adapter['status']=='PLAN_ONLY_NOT_AUTHORIZED' and adapter['parent_run_slot_required'] and adapter['independent_review_required'],'run authorization gate absent')
check(profile['counts']['compiled']==profile['counts']['run']==profile['counts']['passed']==0,'profile execution claim')
check(profile['build']['offline'] and profile['build']['jobs']==profile['build']['linker_threads']==1 and profile['test']['threads']==1,'bounded offline profile')
receipt=json.loads((W/'trace-receipt-contract.json').read_text());check(receipt['status']=='NOT_RUN_NO_NATIVE_RECEIPTS','invented trace receipts')
files=['README.md','source-contract.md','duplicate-audit.md','Cargo.toml','Cargo.lock','tests/pressure_recovery.rs','manifest.json','source-pins.json','profile.json','adapter-plan.json','author_manifest.py','validate.py','syntax-check.json','trace-receipt-contract.json','inventory.json']
out=dict(status='FAIL' if errors else 'PASS',kind='source-only metadata, lexical source and SHA256 checks; no type check or SUT execution',authored=26,mapped_test_functions=len(names),state_cases=24,public_drain_policy_cases=2,reviewed=0,accepted=0,compiled=0,compiler_launches=0,sut_launches=0,run=0,passed=0,production_files_pinned=len(pins['production_files']),errors=errors,files={n:sha(W/n) for n in files})
(W/'static-evidence.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2));sys.exit(bool(errors))
