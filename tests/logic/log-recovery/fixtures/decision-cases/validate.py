#!/usr/bin/env python3
"""Static integrity, source census and duplicate checks only. No native execution."""
import ast
import hashlib
import json
import pathlib
import re
import sys
import tomllib

W=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
errors=[]
def check(ok, message):
    if not ok: errors.append(message)
for name in ['validate.py','author_manifest.py']:
    ast.parse((W/name).read_text(),str(W/name))
manifest=json.loads((W/'manifest.json').read_text())
pins=json.loads((W/'source-pins.json').read_text())
profile=json.loads((W/'profile.json').read_text())
adapter=json.loads((W/'adapter-plan.json').read_text())
receipt=json.loads((W/'trace-receipt-contract.json').read_text())
code=(W/'tests/log_recovery.rs').read_text()
starts=list(re.finditer(r'#\[test\]\s*fn (j\d{3}_[a-z0-9_]+)\(',code))
names=[m.group(1) for m in starts]
check(len(manifest)==len(names)==24,'exactly 24 explicit bodies and manifest cases required')
check([c['id'] for c in manifest]==[f'J{i:03}' for i in range(1,25)],'IDs must be J001-J024')
check(len(set(names))==24,'duplicate function names')
check(set(names)=={c['test_function'] for c in manifest},'manifest/function bijection')
check(len({c['intent'] for c in manifest})==24,'duplicate intent')
check(len({c['failure_hypothesis'] for c in manifest})==24,'duplicate hypothesis')
for c in manifest:
    for key in ['intent','failure_hypothesis','preconditions','initial_state','trace','stress','safety_oracle','liveness_oracle','oracle','terminal_witness','cleanup','implementation','source_contract']:
        check(bool(c.get(key)),c['id']+': missing '+key)
    check(len(c['trace'])>=4,c['id']+': trace too short')
    check(c['implementation']=='tests/log_recovery.rs:'+c['test_function'],c['id']+': mapping mismatch')
    check(c['layer']=='native-component' and c['sublayer']=='public-component-model-trace',c['id']+': wrong layer')
    check(c['classification']==('characterization' if c['id']=='J022' else 'promotion-candidate'),c['id']+': classification mismatch')
    check(not any(c[k] for k in ['reviewed','promotion','compiler_verified','run','passed']),c['id']+': overstated status')
    check(c['status']=='NOT_RUN',c['id']+': incorrect run status')

bodies={}
observation_counts={}
for i,m in enumerate(starts):
    body=code[m.end():starts[i+1].start() if i+1<len(starts) else len(code)]
    cid=m.group(1).split('_')[0].upper()
    check(f'Receipt::new("{cid}")' in body,cid+': wrong receipt ID')
    check('r.done();' in body,cid+': missing final receipt')
    check(body.count('assert')>=3,cid+': insufficient explicit assertions')
    executable_text=re.sub(r'"(?:\\.|[^"\\])*"','""',re.sub(r'//[^\n]*','',body))
    check(not re.search(r'\b(for|while|loop)\b',executable_text),cid+': trace loop requires review')
    count=len(re.findall(r'obs!\s*\(',body))
    check(4<=count<=100,cid+': expected bounded receipt observations')
    observation_counts[cid]=count
    bodies[cid]=hashlib.sha256(re.sub(r'\s+','',re.sub(r'//[^\n]*','',body)).encode()).hexdigest()
check(len(set(bodies.values()))==24,'duplicate normalized body digest')
check('self.events <= 100' in code,'receipt guard missing')
check(not any(x in code for x in ['#[ignore]','#[should_panic]','std::process','std::net','std::fs','thread::spawn','unsafe {']), 'out-of-scope code or nonasserting test attribute')
for module in ['durability','epoch_gc','log_evict','log_tier']:
    check('use celld_logic::'+module in code,'missing actual production module import '+module)

root=pathlib.Path(pins['source_root'])
runtime_path=pathlib.Path(pins['runtime_manifest']['path'])
check(sha(runtime_path)==pins['runtime_manifest']['sha256'],'runtime-manifest digest mismatch')
runtime=json.loads(runtime_path.read_text())
check(runtime['binary_sha256']==pins['delivered_runtime_sha256'],'binary lineage mismatch')
for name,digest in pins['production_files'].items():
    check(sha(root/name)==digest,'changed production file '+name)
    check(runtime['source_hashes'].get('celld/crates/logic/'+name)==digest,'unfrozen production source '+name)
for name,digest in pins['context_files'].items():
    check(sha(pathlib.Path(pins['context_root'])/name)==digest,'changed context source '+name)
    check(runtime['source_hashes'].get(name)==digest,'unfrozen context source '+name)
for name,digest in pins['test_files'].items():check(sha(W/name)==digest,'changed test source '+name)
for name,digest in pins['comparison_manifest_hashes'].items():check(sha(W.parent/name/'manifest.json')==digest,'comparison manifest changed '+name)
check(sha(pathlib.Path(pins['counting_policy']['path']))==pins['counting_policy']['sha256'],'counting policy changed')

cargo=tomllib.loads((W/'Cargo.toml').read_text())
lock=tomllib.loads((W/'Cargo.lock').read_text())
check(cargo['dependencies']['celld-logic']['path']==str(root),'production path dependency missing')
check(set(cargo['dependencies'])=={'celld-logic'},'unexpected dependency')
check(len(lock['package'])==2,'unexpected lock dependency count')
check({p['name'] for p in lock['package']}=={'celld-logic','celld-log-recovery-stress'},'wrong lock identities')
check(profile['counts']['run']==profile['counts']['passed']==profile['counts']['compiled']==0,'profile overstates execution')
check(profile['test']['threads']==1 and profile['test']['wall_seconds']==10,'test limits missing')
check(profile['build']['offline'] and profile['build']['jobs']==profile['build']['linker_threads']==1,'offline bounded build absent')
check(adapter['status']=='PLAN_ONLY_NOT_AUTHORIZED' and adapter['parent_run_slot_required'] and adapter['independent_review_required'],'authorization gates missing')
check(not receipt['execution_receipts_present'],'source-only wave cannot claim native receipts')
syntax=json.loads((W/'syntax-check.json').read_text())
check(syntax['returncode']==0,'rustfmt parser check failed')
check(syntax['input_sha256']==sha(W/'tests/log_recovery.rs'),'syntax evidence stale')

# Audit the available corpus only. A digest nonmatch cannot establish semantic novelty.
other_ids={}
comparison_files={}
for p in sorted(W.parent.glob('*/manifest.json')):
    if p.parent==W:continue
    data=json.loads(p.read_text())
    rows=data if isinstance(data,list) else data.get('cases',[])
    for c in rows:
        if isinstance(c,dict) and c.get('id') in {x['id'] for x in manifest}:
            other_ids.setdefault(c['id'],[]).append(str(p))
check(not other_ids,'stable ID collision: '+str(other_ids))
for name in pins['comparison_manifest_hashes']:
    wave=W.parent/name
    paths=list((wave/'tests').glob('*.rs')) if (wave/'tests').exists() else list(wave.glob('*.py'))
    for p in paths:
        comparison_files[str(p)]=sha(p)
        check(not any(fn in p.read_text() for fn in names),'matching function name in '+str(p))
component_test_attributes={name:len(re.findall(r'#\[test\]',(root/name).read_text())) for name in ['log_tier.rs','log_evict.rs','epoch_gc.rs','durability.rs']}

files=['README.md','source-contract.md','duplicate-audit.md','Cargo.toml','Cargo.lock','tests/log_recovery.rs','manifest.json','source-pins.json','profile.json','adapter-plan.json','trace-receipt-contract.json','author_manifest.py','validate.py','syntax-check.json','inventory.json']
out=dict(status='FAIL' if errors else 'PASS',kind='Source-only metadata, pin, census, syntax-receipt and available-corpus checks; not a native run',
    authored=24,reviewed=0,compiler_launches=0,sut_launches=0,run=0,passed=0,promotion_candidates=23,nonpromoting_characterization=1,
    mapped_functions=len(names),body_sha256_normalized=bodies,observation_counts=observation_counts,
    comparison_implementation_sha256=comparison_files,stable_id_collisions=other_ids,
    available_component_unit_test_attributes=component_test_attributes,
    upstream_scope='Available delivered component sources only; no separate upstream test archive exists in task context; semantic audit is author-side and requires independent review',
    errors=errors,files={name:sha(W/name) for name in files})
(W/'static-evidence.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(dict(status=out['status'],authored=24,mapped_functions=len(names),run=0,passed=0,errors=errors),indent=2))
sys.exit(bool(errors))
