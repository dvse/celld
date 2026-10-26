"""H26-01: Dynamic Worker loads are admitted without a live-count cap, as in workerd."""
import json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from upstream_issue import Runtime,request

LOADS=300  # above celld's former 255-per-script / 256-per-process admission caps

def main():
 out=Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve();out.mkdir(parents=True,exist_ok=True)
 project=out/'project';shutil.copytree(Path(__file__).resolve().parent,project,ignore=shutil.ignore_patterns('__pycache__'))
 runtime=os.environ.get('CELLD_TEST_RUNTIME','celld');port=int(os.environ.get('CELLD_TEST_PORT_BASE','9860'))
 observations={};passed=False
 try:
  with Runtime(project,out/runtime,runtime,port=port) as rt:
   observations['stateless']=request(rt.port,'/?n=%d'%LOADS,timeout=120)
   observations['object']=request(rt.port,'/object?name=a&n=%d'%LOADS,timeout=120)
   observations['object-again']=request(rt.port,'/object?name=a&n=%d'%LOADS,timeout=120)
  passed=all(value=={'done':LOADS} for value in observations.values())
 finally:
  result={'finding':'H26-01','runtime':runtime,'pass':passed,'observations':observations}
  (out/'observation.json').write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps(result),flush=True)
 return 0 if passed else 1

raise SystemExit(main())
