#!/usr/bin/env python3
"""Export VM evidence without environment/credentials or console dumps."""
import hashlib,json,shutil
from pathlib import Path
B=Path.home()/'celld-tests-20261010/phase2';out=B/'gate-exports';out.mkdir(exist_ok=True)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def scrub(v):
 if isinstance(v,list):return [scrub(x) for x in v]
 if isinstance(v,dict):return {k:scrub(x) for k,x in v.items() if k.lower() not in {'environment','env','credentials','authorization','log_tail','diff'} and not any(t in k.upper() for t in ['SECRET','PASSWORD','ACCESS_KEY'])}
 if isinstance(v,str) and any(s in v for s in ['AWS_SECRET_ACCESS_KEY','AWS_ACCESS_KEY_ID']):return '<operational text omitted; raw hash/location retained>'
 return v
rows=[]
for p in sorted((B/'vm').glob('*/**/runs/*/receipt.json')):
 r=json.loads(p.read_text());rel=p.relative_to(B/'vm');dest=out/rel
 cleaned=scrub(r);cleaned['export_redaction']='Environment, credential fields, log tails and relocation diff bodies omitted. Raw receipt retained on the fleet host.';cleaned['raw_receipt_sha256']=sha(p);cleaned['raw_receipt']=str(p);dump(dest,cleaned)
 terminal=[]
 def scan(v):
  if isinstance(v,dict):
   if 'forced_kill' in v:terminal.append({k:v[k] for k in ['status','generation','node','forced_kill','exit_code','reaped','survivors','cleanup_errors','outer_term_grace_seconds'] if k in v})
   for x in v.values():scan(x)
  elif isinstance(v,list):
   for x in v:scan(x)
 scan(r.get('cleanup',{}))
 g=r.get('generations',{}).get('1',{})
 inputs=p.parents[2]/'INPUTS.json';qualification=r.get('qualification') or json.loads(inputs.read_text())['qualification']
 rows.append({'column':rel.parts[0],'gate':rel.parts[1],'run_id':r.get('run_id',p.parent.name),'status':r['status'],'source_commit':qualification.get('source_build',{}).get('commit') if qualification.get('source_build') else None,'binary_sha256':qualification.get('binary_sha256'),'receipt':str(dest.relative_to(out)),'remote_receipt':str(p),'receipt_sha256':sha(p),'elapsed_seconds':r.get('elapsed_seconds'),'checks':scrub(r.get('checks')),'acknowledged_four':scrub(g.get('acknowledged_four')),'durability':scrub(g.get('durability')),'released_owner':scrub(g.get('released_owner')),'terminal':terminal,'error':scrub(r.get('error')),'generation2_entered':'2' in r.get('generations',{})})
 # Raw state stays remote. Disk sizes/hashes are preserved without copying it.
 files=[]
 for f in sorted(p.parent.iterdir()):
  if f.is_file():files.append({'remote':str(f),'bytes':f.stat().st_size,'sha256':sha(f)})
 dump(dest.parent/'RAW-FILES.json',files)
for directory in sorted((B/'vm').iterdir()):
 if (directory/'RELOCATION.json').exists():
  p=directory/'RELOCATION.json';dump(out/directory.name/'RELOCATION.json',{'raw':str(p),'raw_sha256':sha(p),'record':scrub(json.loads(p.read_text()))})
 for p in directory.glob('*/INPUTS.json'):
  target=out/directory.name/p.parent.name/'INPUTS.json';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
dump(out/'GATES.json',rows)
print('Exported',len(rows),'gate attempts with operational environments omitted')
