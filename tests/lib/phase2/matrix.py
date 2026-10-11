#!/usr/bin/env python3
"""Freeze source-matched columns; run them serially with only owned pinned tools."""
import argparse,fcntl,datetime,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
BASE=Path.home()/'celld-tests-20261010/phase2'
SUITE=Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
def main():
 parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--resume-baseline',type=Path);parser.add_argument('--resume-fixes',type=Path);parser.add_argument('--rerun-wave',action='append',default=[]);options,runner_args=parser.parse_known_args()
 lock=(BASE/'ports.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))).strftime('%Y%m%d-%H%M%S-AEST')
 out=BASE/'matrix'/stamp;out.mkdir(parents=True)
 builds=json.loads((BASE/'builds/BUILD-RECEIPTS.json').read_text());columns={}
 pinned=json.loads((SUITE/'tests/lib/phase2/PINS.json').read_text())
 assert {k:v['commit'] for k,v in builds.items()}==pinned['source_columns'],'build receipts differ from reviewed source pins'
 tools={}
 for name,binary,receipt in [('esbuild',BASE/'tools/esbuild',BASE/'tools/esbuild-build.json'),('workerd',BASE/'tools/stock-workerd/package/bin/workerd',BASE/'tools/stock-workerd/RECEIPT.json')]:
  record=json.loads(receipt.read_text());assert sha(binary)==record['binary_sha256'];tools[name]={'binary':str(binary),'sha256':sha(binary),'receipt':record}
 tools['seaweedfs']={'binary':str(BASE/'tools/seaweedfs/weed'),'sha256':sha(BASE/'tools/seaweedfs/weed')}
 assert tools['seaweedfs']['sha256']=='8c07a1ccc4ec058cd90989ac0533c30436832e41c63de2b26f37253d9f744c4d'
 dump(out/'TOOLS.json',tools)
 for label,record in builds.items():
  root=out/label;root.mkdir();(root/'target').symlink_to(BASE/'target',target_is_directory=True);source=BASE/'builds'/record['commit']
  for file in ['Cargo.toml','Cargo.lock']:shutil.copy2(source/file,root/file)
  shutil.copytree(source/'crates',root/'crates')
  shutil.copytree(SUITE/'tests',root/'tests',ignore=shutil.ignore_patterns('artifacts','evidence','.tools','__pycache__'))
  shutil.copytree(SUITE/'tests-hyperbob',root/'tests-hyperbob')
  for name,expected in record['files'].items():
   assert sha(root/name)==expected,(label,name,'source drift')
  assert sha(Path(record['binary']))==record['sha256'],'binary drift'
  harness={str(p.relative_to(root)):sha(p) for p in (root/'tests').rglob('*') if p.is_file()}
  dump(root/'SOURCE-RECEIPT.json',{'build':record,'harness':harness,'harness_source':str(SUITE),'source_tree':pinned['source_trees'][label]})
  dump(root/'CACHE-LAYOUT.json',{'target_alias':str(root/'target'),'target':str(BASE/'target'),'source_receipt_sha256':sha(root/'SOURCE-RECEIPT.json'),'kind':'owned dependency cache only; immutable source inputs unchanged'})
  columns[label]={'root':str(root),'source_commit':record['commit'],'binary_sha256':record['sha256'],'source_tree':pinned['source_trees'][label]}
 dump(out/'MATRIX.json',{'started_aest':stamp,'columns':columns})
 env={**os.environ,'PATH':str(Path.home()/'.local/share/mise/shims')+':'+str(Path.home()/'.cargo/bin')+':'+os.environ['PATH'],'RUSTUP_TOOLCHAIN':'1.98.1','CARGO_BUILD_JOBS':'8','CARGO_TARGET_DIR':str(BASE/'target'),'CELLD_ESBUILD':str(BASE/'tools/esbuild'),'WORKERD_BIN':str(BASE/'tools/stock-workerd/package/bin/workerd')}
 for label,info in columns.items():
  root=Path(info['root']);record=builds[label];print('COLUMN',label,record['commit'],flush=True)
  extra=[]
  previous=options.resume_baseline if label=='def239b' else options.resume_fixes
  if previous:
   extra=['--resume-results',str(previous),*[v for wave in options.rerun_wave for v in ['--rerun-wave',wave]]]
  with (out/(label+'.log')).open('w') as log:
   code=subprocess.call(['python3',root/'tests/lib/runner.py','--profile','full','--remote-worker',*runner_args,*extra],cwd=root,env={**env,'CELLD_BIN':record['binary'],'CELLD_TEST_SOURCE_COMMIT':record['commit']},stdout=log,stderr=subprocess.STDOUT)
  info['exit']=code
  if (root/'tests/RESULTS.json').exists():
   results=json.loads((root/'tests/RESULTS.json').read_text());info['results']=str(root/'tests/RESULTS.json');info['counts']=results['counts'];info['run_id']=results['run_id']
  dump(out/'MATRIX.json',{'started_aest':stamp,'columns':columns});print(label,info,flush=True)
 print('MATRIX',out,flush=True)
 return 1 if any(x['exit'] for x in columns.values()) else 0
if __name__=='__main__':raise SystemExit(main())
