#!/usr/bin/env python3
"""Read-only import from the sibling's committed fixes branch; never edit cases."""
from pathlib import Path
import argparse,hashlib,json,subprocess,datetime,shutil
from common import ROOT,TESTS,dump
p=argparse.ArgumentParser();p.add_argument('--source',default='$LAB/celld-suite-20261010/celld');p.add_argument('--commit',help='pin a read-only fixes snapshot instead of following HEAD');a=p.parse_args()
src=Path(a.source)
if not (src/'.git').exists():raise SystemExit('fix-lane clone is not present on this host; retain last imported snapshot')
def git(*args):return subprocess.check_output(['git','-C',str(src),*args])
commit=git('rev-parse',a.commit or 'fixes').decode().strip();files=git('ls-tree','-r','--name-only',commit,'--','tests/regressions','tests/vendor').decode().splitlines();records=[]
for path in files:
 if path=='tests/regressions/CONTRACT.md':continue
 data=git('show',f'{commit}:{path}');dst=ROOT/path
 if dst.exists() and dst.read_bytes()!=data:
  archive=TESTS/'regressions-imports'/hashlib.sha256(dst.read_bytes()).hexdigest()/path;archive.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(dst,archive)
 dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 mode=git('ls-tree',commit,'--',path).decode().split()[0]
 if mode=='100755':dst.chmod(0o755)
 records.append({'path':path,'sha256':hashlib.sha256(data).hexdigest()})
dump(TESTS/'regressions/IMPORT.json',{'source_clone':str(src),'commit':commit,'branch':'fixes','files':records})
print(f'Imported {len(records)} regression/vendor files from fixes {commit[:12]}')
