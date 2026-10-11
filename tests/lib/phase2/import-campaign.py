#!/usr/bin/env python3
"""Import frozen accepted designs; preserve sources and all provenance aliases."""
import hashlib,json,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import ROOT,TESTS,dump,sha
INPUT=Path(sys.argv[1])
ADD=INPUT/'bodyfix/historical-checkpoint/additions'
AREAS={'headers-semantics':'fetch-and-http','url-semantics':'web-platform','kv-semantics':'bindings','storage-sql-semantics':'durable-objects/storage-sql','d1-semantics':'bindings','body-form-semantics':'fetch-and-http','r2-semantics':'bindings','facet-root-semantics':'durable-objects/facets','pipe-cleanup-semantics':'fetch-and-http','atomic-accounting-semantics':'durable-objects/storage-sql','identity-admission-semantics':'durable-objects/lifecycle','stream-backpressure-semantics':'fetch-and-http','os-typed-storage-semantics':'durable-objects/storage-kv','os-action-file-store-semantics':'durable-objects/storage-sql','os-git-codec-semantics':'web-platform','response-clone-chunk-semantics':'fetch-and-http'}
records=[];designs=[];inventories=[]
for invpath in sorted(ADD.glob('TRANCHE-*.json')):
 inv=json.loads(invpath.read_text());inventories.append({'source':str(invpath),'sha256':sha(invpath),'counts':inv['counts']})
 for rel,digest in inv['files_sha256'].items():
  assert sha(ADD/rel)==digest,(invpath,rel)
 for wave in inv['accepted_waves']:
  name=wave['name'];src=ADD/wave['path'];area=AREAS[name];dest=TESTS/'conformance'/area/'fixtures'/name
  for p in sorted(src.rglob('*')):
   if not p.is_file():continue
   q=dest/p.relative_to(src);q.parent.mkdir(parents=True,exist_ok=True)
   if q.exists():assert sha(p)==sha(q),q
   else:shutil.copy2(p,q)
   aliases=[str(p)]
   for alternate in [INPUT/'ready-functional/celld-campaign-next'/name/p.relative_to(src),INPUT/'bodyfix/candidate-evidence/celld-campaign-next'/name/p.relative_to(src)]:
    if alternate.exists() and sha(alternate)==sha(p):aliases.append(str(alternate))
   records.append({'path':str(q.relative_to(ROOT)),'sha256':sha(q),'origins':aliases})
  review=ADD/wave['review_path'];q=TESTS/'lib/phase2/provenance'/review.name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(review,q)
  manifest=json.loads((src/'manifest.json').read_text());rows=manifest if isinstance(manifest,list) else manifest['cases'];rows={r['id']:r for r in rows}
  config=next(iter([*dest.glob('wrangler.json'),*dest.glob('wrangler.jsonc')]))
  cfg=json.loads(config.read_text());source=dest/cfg['main']
  for id in wave['case_ids']:
   row=rows[id];characterization=id=='V216';slug=name.replace('-semantics','')+'-'+id.lower()
   c=dict(id='conformance/'+area+'/'+slug,layer='conformance',behaviour=area,title=row.get('title',row.get('intent',id)),origins=[{'source':str(src),'legacy_id':'campaign/'+name+'/'+id,'manifest_sha256':sha(src/'manifest.json'),'review_sha256':sha(review),'tranche':inv['tranche']}],legacy_ids=['campaign/'+name+'/'+id],source=str(source.relative_to(ROOT)),source_sha256=sha(source),fixture=str(dest.relative_to(ROOT)),corpus_wave=name,corpus_id=id,selector=id,campaign=True,reviewed=not characterization,characterization=characterization,profiles=['full'],adapter='http',runnable=not characterization,reason='Characterization design V216 has no primary conformance credit.' if characterization else None,requests=[{'path':'/case/'+id,'timeout':30}],contract=row)
   if characterization:
    c['runnable']=False;dump(TESTS/'conformance'/area/(slug+'.design.json'),c)
   else:dump(TESTS/'conformance'/area/(slug+'.case.json'),c)
   designs.append({'wave':name,'id':id,'classification':'characterization' if characterization else 'primary','header':str((TESTS/'conformance'/area/(slug+('.design.json' if characterization else '.case.json'))).relative_to(ROOT))})
 q=TESTS/'lib/phase2/provenance'/invpath.name;shutil.copy2(invpath,q)
assert len(designs)==211 and len([r for r in designs if r['classification']=='primary'])==210
for p in [INPUT/'celld-vm-checkpoint-20261009/provenance',INPUT/'celld-cold-restart-source-checkpoint-20261009']:
 pass
dump(TESTS/'lib/phase2/CAMPAIGN.json',{'schema':1,'baseline_primary':461,'baseline_characterization':114,'total_designs':786,'primary':671,'characterization':115,'designs':designs,'files':records,'inventories':inventories})
print('Imported 211 additional designs: 210 primary + 1 characterization;',len(records),'unchanged files')
