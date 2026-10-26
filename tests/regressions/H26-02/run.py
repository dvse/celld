"""H26-02: `name in stub` answers as workerd's JSG wildcard property query does."""
import json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from upstream_issue import Runtime,request

def main():
 here=Path(__file__).resolve().parent
 out=Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();out.mkdir(parents=True,exist_ok=True)
 project=out/'project';shutil.copytree(here,project,ignore=shutil.ignore_patterns('__pycache__'))
 runtime=os.environ.get('CELLD_TEST_RUNTIME','celld');port=int(os.environ.get('CELLD_TEST_PORT_BASE','9860'))
 expected=json.loads((here/'expected.json').read_text());observed=None;passed=False
 try:
  with Runtime(project,out/runtime,runtime,port=port) as rt:observed=request(rt.port,'/',timeout=30)
  passed=observed==expected
 finally:
  result={'finding':'H26-02','runtime':runtime,'pass':passed,'observed':observed,
   'mismatch':None if observed is None else {k:{'expected':expected.get(k),'observed':v} for k,v in observed.items() if expected.get(k)!=v}}
  (out/'observation.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result),flush=True)
 return 0 if passed else 1

raise SystemExit(main())
