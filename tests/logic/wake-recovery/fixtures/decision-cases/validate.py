#!/usr/bin/env python3
"""Small source/hash/parser-evidence checks only. Never launches native code."""
import ast,hashlib,json,pathlib,re,sys,tomllib
W=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
errors=[]
def ck(ok,label):
 if not ok:errors.append(label)
for name in ['author_manifest.py','pin_sources.py','validate.py']:ast.parse((W/name).read_text(),name)
manifest=json.loads((W/'manifest.json').read_text());pins=json.loads((W/'source-pins.json').read_text())
profile=json.loads((W/'profile.json').read_text());inventory=json.loads((W/'inventory.json').read_text())
adapter=json.loads((W/'adapter-plan.json').read_text());receipts=json.loads((W/'trace-receipt-contract.json').read_text())
code=(W/'tests/wake_recovery.rs').read_text()
starts=list(re.finditer(r'#\[test\]\s*fn (k\d{3}_[a-z0-9_]+)\(',code));names=[m.group(1) for m in starts]
ck(len(manifest)==len(names)==24,'exactly 24 handwritten case bodies')
ck([c['id'] for c in manifest]==[f'K{i:03}' for i in range(1,25)],'K001-K024 IDs')
ck(len(set(names))==24 and set(names)=={c['test_function'] for c in manifest},'test mapping bijection')
ck(len({c['intent'] for c in manifest})==len({c['failure_hypothesis'] for c in manifest})==24,'unique causal descriptions')
characterizations={'K011','K016','K017','K019','K024'}
for c in manifest:
 for field in ['initial_state','preconditions','trace','stress','safety_oracle','liveness_oracle','cleanup','terminal_witness','source_contract']:
  ck(bool(c.get(field)),c['id']+': missing '+field)
 ck(len(c['trace'])>=4,c['id']+': incomplete finite trace')
 ck(c['implementation']=='tests/wake_recovery.rs:'+c['test_function'],c['id']+': implementation mismatch')
 ck(c['classification']==('characterization' if c['id'] in characterizations else 'promotion-candidate'),c['id']+': classification')
 ck(c['layer']=='native-component',c['id']+': mislabeled layer')
 ck(c['status']=='NOT_RUN' and not any(c[k] for k in ['reviewed','compiler_verified','promotion','run','passed']),c['id']+': overstated counters')
bodies={};receipt_sites={}
for i,m in enumerate(starts):
 body=code[m.end():starts[i+1].start() if i+1<len(starts) else len(code)]
 id=m.group(1).split('_')[0].upper();n=int(id[1:])
 ck((('H::new("'+id+'"' in body) or ('H::with_deadline("'+id+'"' in body)) if 7<=n<=13 else ('Receipt::new("'+id+'")' in body),id+': missing ID in fixture')
 ck('h.done();' in body if 7<=n<=13 else 'r.done();' in body,id+': no terminal witness')
 ck(body.count('assert')>=2,id+': lacks explicit independent assertions')
 if not 7<=n<=13:
  count=len(re.findall(r'obs!\s*\(',body))+len(re.findall(r'cron_plan\s*\(',body))
  ck(4<=count<=100,id+': completed production call receipt sites');receipt_sites[id]=count
 else:receipt_sites[id]='explicit on_event calls plus full activation helper calls; no native receipt claimed'
 stripped=re.sub(r'"(?:\\.|[^"\\])*"','""',re.sub(r'//[^\n]*','',body))
 ck(not re.search(r'\b(for|while|loop)\b',stripped),id+': unreviewed loop')
 bodies[id]=hashlib.sha256(re.sub(r'\s+','',stripped).encode()).hexdigest()
ck(len(set(bodies.values()))==24,'duplicate normalized case body')
ck('self.calls <= 100' in code and 'self.calls >= 4' in code,'receipt ceiling/minimum missing')
ck('let effects = on_event(&mut self.s, event)' in code and '.validate()' in code,'production State wrapper missing')
ck(not any(x in code for x in ['#[ignore]','#[should_panic]','std::process','std::net','std::fs','thread::spawn','unsafe {','take_retired','Retirement','settlement_matches','Failure::Unavailable']), 'forbidden scope or fake API')
root=pathlib.Path(pins['source_root']);runtimepath=pathlib.Path(pins['runtime_manifest']['path'])
ck(sha(runtimepath)==pins['runtime_manifest']['sha256'],'frozen runtime manifest changed')
runtime=json.loads(runtimepath.read_text())
ck(runtime['binary_sha256']==pins['delivered_runtime_sha256'],'runtime lineage mismatch')
for name,digest in pins['production_files'].items():
 ck(sha(root/name)==digest,'production changed '+name)
 ck(runtime['source_hashes'].get('celld/crates/logic/'+name)==digest,'source not frozen '+name)
for name,digest in pins['context_files'].items():
 ck(sha(pathlib.Path(pins['context_root'])/name)==digest,'context changed '+name)
 ck(runtime['source_hashes'].get(name)==digest,'context not frozen '+name)
for name,digest in pins['test_files'].items():ck(sha(W/name)==digest,'test source changed '+name)
for wave,files in pins['comparison_files'].items():
 for name,digest in files.items():ck(sha(W.parent/wave/name)==digest,'comparison changed '+wave+'/'+name)
ck(sha(pathlib.Path(pins['counting_policy']['path']))==pins['counting_policy']['sha256'],'counting policy changed')
cargo=tomllib.loads((W/'Cargo.toml').read_text());lock=tomllib.loads((W/'Cargo.lock').read_text())
ck(cargo['dependencies']=={'celld-logic':{'path':str(root)}},'local production dependency')
ck({p['name'] for p in lock['package']}=={'celld-logic','celld-wake-recovery-stress'},'lock identities')
ck(len(lock['package'])==2,'unexpected dependency graph')
ck(cargo['test'][0]['path']=='tests/wake_recovery.rs','test source binding')
for d in [profile['counts'],inventory['counts'],receipts['counts']]:
 ck(d['authored']==24 and d['reviewed']==d['compiled']==d['run']==d['passed']==0,'source-only counters')
ck(profile['counts']['promotion_candidates']==19 and profile['counts']['nonpromoting_characterization']==5,'candidate split')
ck(profile['build']['jobs']==profile['test']['threads']==1 and profile['build']['offline'],'bounded future profile')
ck(adapter['status']=='PLAN_ONLY_NOT_AUTHORIZED' and adapter['independent_review_required'] and adapter['parent_run_slot_required'],'future execution gates')
ck(not receipts['execution_receipts_present'],'native receipts absent')
syntax=json.loads((W/'syntax-check.json').read_text())
ck(syntax['returncode']==0 and syntax['input_sha256']==sha(W/'tests/wake_recovery.rs'),'syntax check failed/stale')
collisions=[]
for p in W.parent.glob('*/manifest.json'):
 if p.parent==W:continue
 a=json.loads(p.read_text());a=a if isinstance(a,list) else a.get('cases',[])
 for c in a:
  if isinstance(c,dict) and c.get('id') in {x['id'] for x in manifest}:collisions.append([c['id'],str(p)])
ck(not collisions,'stable ID collision '+str(collisions))
files=['README.md','source-contract.md','duplicate-audit.md','Cargo.toml','Cargo.lock','tests/wake_recovery.rs','manifest.json','source-pins.json','profile.json','adapter-plan.json','trace-receipt-contract.json','author_manifest.py','pin_sources.py','validate.py','syntax-check.json','inventory.json']
out=dict(schema=1,status='FAIL' if errors else 'PASS',kind='Source metadata/hash/parser-evidence checks only; not native test execution',
 authored=24,reviewed=0,executable_implementations=24,compiler_launches=0,sut_launches=0,compiled=0,run=0,passed=0,
 promotion_candidates=19,nonpromoting_characterizations=5,production_state_cases=7,public_component_cases=17,
 normalized_body_sha256=bodies,receipt_sites=receipt_sites,stable_id_collisions=collisions,
 corpus_limits='Available pinned A/B/G/N/P/J bodies and public component sources only; author audit is not independent semantic review',
 files={name:sha(W/name) for name in files},errors=errors)
(W/'static-evidence.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ['status','authored','reviewed','compiled','run','passed','errors']},indent=2))
sys.exit(bool(errors))
