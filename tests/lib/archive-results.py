#!/usr/bin/env python3
"""Create a small, reviewable evidence export; retain every raw artifact in place."""
import argparse,hashlib,json,shutil
from pathlib import Path
from common import ROOT,TESTS,dump,sha,safe_id
p=argparse.ArgumentParser();p.add_argument('--results',type=Path,default=TESTS/'RESULTS.json');p.add_argument('--raw',type=Path,required=True);p.add_argument('--label',default='full');a=p.parse_args()
x=json.loads(a.results.read_text());raw=a.raw.resolve();dest=TESTS/'evidence'/(a.label+'-'+x['run_id']);dest.mkdir(parents=True,exist_ok=False)
# JSON and logs under staged fixture/runtime state are omitted from the small
# export. Their hashes and raw locations remain in ARTIFACTS.json.
records=[];mapped={}
for f in sorted(raw.rglob('*')):
    if not f.is_file() or f.is_symlink():continue
    rel=f.relative_to(raw);excluded=any(part in ['fixture','accepted-base','s3-store','store','contract-store','celld-storage','workerd-storage','mutated-logic'] or part.startswith(('node-','killed-node-')) for part in rel.parts[:-1])
    include=not excluded and (f.suffix in ['.json','.log','.diff','.md'] or f.name=='workerd.capnp') and not ('cases' in rel.parts)
    # Native fixture output can be large; it is still immutable evidence.
    target=dest/'observations'/rel
    if include:
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,target);mapped[f.resolve()]=target
    records.append({'path':str(f.relative_to(ROOT)),'sha256':sha(f),'bytes':f.stat().st_size,'export':str(target.relative_to(ROOT)) if include else None})
for row in x['results']:
    artifacts=[]
    for art in row['artifacts']:
        src=Path(art);src=src if src.is_absolute() else ROOT/src
        if src.resolve() in mapped:artifacts.append(str(mapped[src.resolve()].relative_to(ROOT)))
        elif src.is_dir() and raw in src.resolve().parents:
            exported=dest/'observations'/src.resolve().relative_to(raw)
            artifacts.append(str((exported if exported.exists() else src).relative_to(ROOT)))
        else:artifacts.append(str(src.relative_to(ROOT)) if ROOT in src.parents else str(src))
    row['artifacts']=artifacts
    dump(dest/'cases'/row['layer']/safe_id(row['id'])/(row['runtime']+'.json'),row)
x['evidence_export']=str(dest.relative_to(ROOT));x['raw_evidence']=str(raw.relative_to(ROOT));x['evidence_transform']='Artifact paths mapped to the committed subset; raw outputs retained unchanged. ARTIFACTS.json hashes all raw files.'
dump(dest/'RESULTS.json',x);dump(dest/'ARTIFACTS.json',{'files':records})
shutil.copy2(TESTS/'lib/SOURCES.json',dest/'SOURCES.json')
readme=f'''# {a.label} evidence: {x['run_id']}

Profile `{x['profile']}`, host `{x['host']}`, source `{x['source_commit']}`.
Counts: {json.dumps(x['counts'],sort_keys=True)}.

`cases/` contains one common-schema JSON result per selected case/runtime.
`observations/` contains logs, response bodies, diffs, configuration and pins.
`ARTIFACTS.json` hashes every raw file, including retained binary/database files
that are too large or operational for this small Git export. Raw evidence stays
at `{raw.relative_to(ROOT)}`. Nothing is deleted or substituted for old evidence.
'''
(dest/'README.md').write_text(readme)
print(dest.relative_to(ROOT));print(json.dumps(x['counts'],sort_keys=True))
