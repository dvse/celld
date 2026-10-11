#!/usr/bin/env python3
"""Source-only checks. Never imports or launches production, Cargo, rustc or a test."""
import ast,hashlib,json,pathlib,re,sys,tomllib
W=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
errors=[]
def check(ok, msg):
    if not ok:errors.append(msg)
for p in (W/'validate.py',W/'author_manifest.py'):ast.parse(p.read_text(),str(p))
m=json.loads((W/'manifest.json').read_text()); pins=json.loads((W/'source-pins.json').read_text())
profile=json.loads((W/'profile.json').read_text()); adapter=json.loads((W/'adapter-plan.json').read_text())
code=(W/'tests/routing_acquisition.rs').read_text(); names=re.findall(r'#\[test\]\s*fn (n\d{3}_[a-z0-9_]+)\(',code)
check(len(m)==36 and len(names)==36, 'expected exactly 36 manifests and Rust test bodies')
check([c['id'] for c in m]==[f'N{i:03}' for i in range(1,37)],'IDs must be N001-N036')
check(len(set(names))==36,'duplicate Rust function name')
check(set(names)=={c['test_function'] for c in m},'manifest/function bijection')
check(len({c['intent'] for c in m})==36 and len({c['failure_hypothesis'] for c in m})==36,'duplicate intent/hypothesis')
for c in m:
    for key in ('id','intent','failure_hypothesis','preconditions','initial_state','trace','stress','oracle','safety_oracle','liveness_oracle','terminal_witness','cleanup','implementation','test_function','layer','classification'):
        check(bool(c.get(key)),c['id']+': missing '+key)
    check(isinstance(c['trace'],list) and len(c['trace'])>=4,c['id']+': finite ordered trace required')
    check(c['implementation']=='tests/routing_acquisition.rs:'+c['test_function'],c['id']+': implementation mapping mismatch')
    check(c['layer']=='native-component' and c['sublayer']=='state-trace',c['id']+': wrong evidence layer')
    check(c['promotion'] is False and not c['reviewed'] and not c['run'] and not c['passed'],c['id']+': unearned execution/review/promotion claim')
    check(c['classification']==('characterization' if c['id'] in ('N020','N023') else 'promotion-candidate'),c['id']+': classification changed')
for name,digest in pins['test_files'].items():check(sha(W/name)==digest,'artifact pin '+name)
root=pathlib.Path(pins['source_root'])
for name,digest in pins['production_files'].items():check(sha(root/name)==digest,'production pin '+name)
rmp=pathlib.Path(pins['runtime_manifest']['path']); check(sha(rmp)==pins['runtime_manifest']['sha256'],'runtime manifest pin')
rm=json.loads(rmp.read_text());check(rm['binary_sha256']==pins['delivered_runtime_sha256'],'runtime digest lineage')
for name,digest in pins['production_files'].items():check(rm['source_hashes']['celld/crates/logic/'+name]==digest,'frozen lineage '+name)
for name,digest in pins['comparison_manifest_hashes'].items():check(sha(W.parent/name/'manifest.json')==digest,'comparison manifest changed '+name)
cargo=tomllib.loads((W/'Cargo.toml').read_text()); lock=tomllib.loads((W/'Cargo.lock').read_text())
check(cargo['dependencies']['celld-logic']['path']==str(root),'production path dependency missing')
check(len(lock['package'])==2 and {p['name'] for p in lock['package']}=={'celld-logic','celld-routing-acquisition-stress'},'lock has unexpected package')
check('on_event(&mut self.s, event)' in code,'actual production transition missing')
check('self.s.validate()' in code or re.search(r'self\.s\s*\.validate\(\)',code),'production validation missing')
check('#[ignore]' not in code and '#[should_panic]' not in code,'ignored/panic test found')
check('self.count <= 120' in code,'finite event guard missing')
check('let op = op(' not in code,'known operation-helper shadowing hazard')
check(not re.search(r'\bh\.s\.\w+\s*=',code),'test mutates State fields directly')
check(not any(x in code for x in ('std::process','std::net','thread::spawn','unsafe {','DurableReached','AwaitDurable')),'out-of-scope I/O or copied output proof cases')
# Each test must own its explicit body and terminate in the accounting oracle.
starts=list(re.finditer(r'#\[test\]\s*fn (n\d{3}_[a-z0-9_]+)\(',code)); body_hashes=[]
for i,v in enumerate(starts):
    body=code[v.end():starts[i+1].start() if i+1<len(starts) else len(code)]
    check('h.done();' in body,v.group(1)+': missing terminal accounting oracle')
    check('h.req(' in body or 'h.handoff(' in body or 'h.activate(' in body,v.group(1)+': no concrete demand')
    check('assert' in body or 'h.local(' in body or 'h.remote(' in body,v.group(1)+': missing assertion')
    body_hashes.append(hashlib.sha256(body.encode()).hexdigest())
check(len(set(body_hashes))==36,'duplicate test body')
syntax=json.loads((W/'syntax-check.json').read_text());check(syntax['returncode']==0,'Rust parse/format check failed')
check(syntax['input_sha256']==sha(W/'tests/routing_acquisition.rs'),'syntax evidence is stale')
check(profile['counts']['run']==0 and profile['counts']['passed']==0,'profile overstated execution')
check(profile['build']['offline'] and profile['build']['jobs']==1 and profile['build']['linker_threads']==1,'bounded offline single-thread build profile absent')
check(profile['test']['threads']==1 and profile['test']['wall_seconds']==10,'bounded single-thread test profile absent')
check(adapter['status']=='PLAN_ONLY_NOT_AUTHORIZED' and adapter['parent_run_slot_required'] and adapter['independent_review_required'],'adapter authorization gate absent')
files=['README.md','source-contract.md','Cargo.toml','Cargo.lock','tests/routing_acquisition.rs','manifest.json','source-pins.json','profile.json','adapter-plan.json','author_manifest.py','validate.py','syntax-check.json']
out={'status':'FAIL' if errors else 'PASS','kind':'source-only static checks; no build or test execution','authored':36,'mapped_test_functions':len(names),'reviewed':0,'promotion_candidates':34,'nonpromoting_characterization':2,'compiler_launches':0,'sut_launches':0,'run':0,'passed':0,'errors':errors,'files':{n:sha(W/n) for n in files}}
(W/'static-evidence.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2));sys.exit(bool(errors))
