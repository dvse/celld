#!/usr/bin/env python3
"""Make bounded review exports; raw state and earlier exports remain untouched."""
import argparse,gzip,hashlib,json,shutil,sys
from pathlib import Path
B=Path.home()/'celld-tests-20261010/phase2'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def safe(p):
 parts=p.parts
 if any(x in {'fixture','staging','s3-store','store','contract-store','celld-storage','workerd-storage','data','meta','tmp','__pycache__','cases'} or x.startswith(('node-0-generation','node-1-generation','node-2-generation','node-3-generation','node-4-generation','built-wasm','relocated-')) for x in parts[:-1]):return False
 return p.suffix in {'.json','.log','.diff','.md'} and p.name!='s3-auth.json' and 'environment' not in p.name.lower()
def main():
 parser=argparse.ArgumentParser();parser.add_argument('roots',nargs='*',type=Path);parser.add_argument('--export-name');args=parser.parse_args()
 roots=args.roots or sorted((B/'matrix').iterdir())
 if args.export_name:assert len(roots)==1 and Path(args.export_name).name==args.export_name
 for matrix in roots:
  meta=json.loads((matrix/'MATRIX.json').read_text());out=B/'exports'/(args.export_name or matrix.name)
  if out.exists():
   if (out/'COMPLETE.json').exists():continue
   raise SystemExit('Incomplete existing export retained; choose a fresh export directory before retrying: '+str(out))
  out.mkdir(parents=True);dump(out/'MATRIX.json',meta)
  shutil.copy2(Path(__file__),out/'export-matrix.py')
  dump(out/'EXPORTER.json',{'source':str(Path(__file__).resolve()),'artifact':'export-matrix.py','sha256':sha(Path(__file__)),'policy':'Regular files and file symlink referents are hashed; symlink targets are recorded without copying linked content into the review export.'})
  if (matrix/'TOOLS.json').exists():shutil.copy2(matrix/'TOOLS.json',out/'TOOLS.json')
  for label,info in meta['columns'].items():
   root=Path(info['root']);result=root/'tests/RESULTS.json'
   if not result.exists():continue
   x=json.loads(result.read_text());raw=root/'tests/artifacts'/x['run_id'];dest=out/label;dest.mkdir();mapping={};inventory=[]
   raw_roots=[raw,*[Path(p) for p in x.get('ancestor_raw_runs',[])]]
   for p in sorted(set(p for r in raw_roots for p in r.rglob('*'))):
    if not p.is_file():continue
    if p.is_symlink():assert B in p.resolve().parents,('symlink leaves owned root',p)
    origin=next(r for r in raw_roots if r in p.parents);rel=p.relative_to(origin);export_rel=rel if origin==raw else Path('prior-'+origin.name)/rel;item={'remote_path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
    if p.is_symlink():item.update(kind='file-symlink',target=str(p.readlink()),resolved_target=str(p.resolve()))
    if safe(rel) and not p.is_symlink():
     target=dest/'observations'/export_rel;target.parent.mkdir(parents=True,exist_ok=True)
     if p.stat().st_size>512*1024:
      target=target.with_name(target.name+'.gz')
      with p.open('rb') as src,gzip.GzipFile(filename=str(target),mode='wb',mtime=0) as dst:shutil.copyfileobj(src,dst)
     else:shutil.copy2(p,target)
     item['export']=str(target.relative_to(out));mapping[str(p)]=item['export']
    inventory.append(item)
   unresolved={}
   for row in x['results']:
    prior=row['artifacts']
    for original in prior:
     p=Path(original)
     origin=next((r for r in raw_roots if r in p.parents),None)
     if p.is_dir() and origin is not None:
      rel=p.relative_to(origin);export_rel=rel if origin==raw else Path('prior-'+origin.name)/rel
      target=dest/'observations'/export_rel
      if target.exists():mapping[original]=str(target.relative_to(out))
    row['artifacts']=[mapping[p] for p in prior if p in mapping]
    # Link diagnostic siblings captured after a partially written observation.
    for original in prior:
     sibling=str(Path(original).with_suffix('.error.json'))
     if sibling in mapping and mapping[sibling] not in row['artifacts']:row['artifacts'].append(mapping[sibling])
    omitted=[p for p in prior if p not in mapping]
    if omitted:unresolved[row['id']+'@'+row['runtime']]=omitted
   for origin in raw_roots[1:]:
    source=origin.parents[2]/'SOURCE-RECEIPT.json';target=dest/'lineage'/origin.name/'SOURCE-RECEIPT.json';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,target)
   if (root/'CACHE-LAYOUT.json').exists():shutil.copy2(root/'CACHE-LAYOUT.json',dest/'CACHE-LAYOUT.json')
   x.update(remote_raw=str(raw),evidence_transform='Artifact paths mapped to review exports and existing error-diagnostic siblings linked; original raw results remain on the fleet host.')
   dump(dest/'RESULTS.json',x);dump(dest/'ARTIFACTS.json',{'files':inventory,'unexported_references':unresolved});shutil.copy2(root/'SOURCE-RECEIPT.json',dest/'SOURCE-RECEIPT.json')
  dump(out/'COMPLETE.json',{'matrix':str(matrix),'columns_exported':[k for k in meta['columns'] if (out/k/'RESULTS.json').exists()]})
  print(out,flush=True)
if __name__=='__main__':main()
