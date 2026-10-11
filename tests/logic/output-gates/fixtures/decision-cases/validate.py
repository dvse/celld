#!/usr/bin/env python3
"""Static only: census, implementation mapping, source pins, finite authored traces."""
import hashlib,json,pathlib,re,sys
W=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
errors=[]
m=json.loads((W/'manifest.json').read_text());pins=json.loads((W/'source-pins.json').read_text());code=(W/'tests/output_gate.rs').read_text()
names=re.findall(r'#\[test\]\s*fn (g\d{3}_[a-z0-9_]+)\(',code)
ids=[c['id'] for c in m]
if len(ids)!=len(set(ids)) or len(names)!=len(set(names)):errors.append('duplicate test ID or function')
if len(names)!=len(m):errors.append('manifest/test count mismatch')
if set(names)!={c['test_function'] for c in m}:errors.append('function mapping mismatch')
for case in m:
    for field in ['intent','failure_hypothesis','preconditions','initial_state','trace','stress','safety_oracle','liveness_oracle','cleanup','implementation','layer','sublayer','qualification']:
        if not case.get(field):errors.append(case['id']+': empty '+field)
    if case['implementation']!='tests/output_gate.rs:'+case['test_function']:errors.append(case['id']+': implementation mismatch')
    if case['layer']!='native-component' or case['sublayer']!='state-trace':errors.append(case['id']+': overstated layer')
    if not case['test_function'].startswith(case['id'].lower()+'_'):errors.append(case['id']+': unstable function ID')
    if case['id'] in ['G021','G022'] and case['qualification']!='characterization':errors.append(case['id']+': diagnostic promoted')
for name,digest in pins['test_files'].items():
    if sha(W/name)!=digest:errors.append('test pin mismatch '+name)
for name,digest in pins['production_files'].items():
    if sha(pathlib.Path(pins['source_root'])/name)!=digest:errors.append('source pin mismatch '+name)
if sha(pathlib.Path(pins['runtime_manifest']['path']))!=pins['runtime_manifest']['sha256']:errors.append('runtime manifest lineage mismatch')
if 'on_event(&mut self.s, event)' not in code:errors.append('actual production entry point missing')
if '#[ignore]' in code:errors.append('ignored test not executable')
if len(set(c['failure_hypothesis'] for c in m))!=len(m):errors.append('duplicate failure hypotheses')
result={'status':'FAIL' if errors else 'PASS','kind':'static validation only','authored':len(m),'mapped_rust_test_functions':len(names),'promotion_candidates':sum(c['qualification']=='promotion-candidate' for c in m),'nonpromoting_characterization':sum(c['qualification']=='characterization' for c in m),'run':0,'passed':0,'errors':errors,'files':{str(p.relative_to(W)):sha(p) for p in [W/'Cargo.toml',W/'Cargo.lock',W/'tests/output_gate.rs',W/'manifest.json',W/'profile.json',W/'source-pins.json',W/'author_manifest.py',W/'run_selected.py',W/'validate.py']}}
(W/'static-evidence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));sys.exit(bool(errors))
