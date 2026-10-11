#!/usr/bin/env python3
"""Recreate immutable source-relative paths for inspecting historical runners."""
import argparse,json,shutil
from pathlib import Path
from common import ROOT,TESTS,dump,sha
p=argparse.ArgumentParser();p.add_argument('--origin-prefix',default='guarded-source-archive/celld-os-stress/');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
# Deliberately create a new directory; never replace state or execute a legacy runner.
a.output.mkdir(parents=True,exist_ok=False);records=[]
for item in json.loads((TESTS/'lib/SOURCES.json').read_text())['files']:
    if not item['origin'].startswith(a.origin_prefix):continue
    rel=Path(item['origin'][len(a.origin_prefix):]);assert not rel.is_absolute() and '..' not in rel.parts
    source=ROOT/item['path'];assert sha(source)==item['sha256']
    target=a.output/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);records.append(item)
dump(a.output/'MATERIALIZED.json',{'origin_prefix':a.origin_prefix,'files':records,'executed':False})
print(f'{len(records)} unchanged files materialized in {a.output}; no runner executed')
