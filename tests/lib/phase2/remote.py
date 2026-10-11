#!/usr/bin/env python3
"""Publish a fresh suite snapshot to our fleet-host root and collect matrix evidence."""
import datetime,os,shlex,subprocess,sys
CELLD_FLEET_HOST=os.environ.get('CELLD_FLEET_HOST','celld-fleet')
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))).strftime('%Y%m%d-%H%M%S-AEST')+'-'+str(os.getpid())
dest='celld-tests-20261010/phase2/snapshots/'+stamp
subprocess.run(['ssh','-o','BatchMode=yes',CELLD_FLEET_HOST,'mkdir -p '+shlex.quote(dest)],check=True)
subprocess.run(['rsync','-az','--exclude=.git','--exclude=target','--exclude=node_modules','--exclude=tests/artifacts','--exclude=tests/evidence','--exclude=tests/.tools',str(ROOT)+'/', CELLD_FLEET_HOST+':'+dest+'/'],check=True)
args=list(sys.argv[1:])
if '--profile' in args:
 index=args.index('--profile');assert args[index+1]=='full';args[index:index+2]=[]
cmd=['systemd-run','--user','--pipe','--wait','--unit=celld-tests-20261010-matrix-'+stamp,'python3',str(Path.home()/dest/'tests/lib/phase2/matrix.py'),*args]
process=subprocess.Popen(['ssh','-o','BatchMode=yes',CELLD_FLEET_HOST,shlex.join(cmd)],stdout=subprocess.PIPE,text=True)
matrix=None
for line in process.stdout:
 print(line,end='',flush=True)
 if line.startswith('MATRIX '):matrix=line.strip().split(' ',1)[1]
code=process.wait()
if matrix is None:raise SystemExit('Matrix did not complete; all remote partial state retained at '+dest)
subprocess.run(['ssh','-o','BatchMode=yes',CELLD_FLEET_HOST,shlex.join(['python3',dest+'/tests/lib/phase2/export-matrix.py',matrix])],check=True)
local=ROOT/'tests/evidence'/('phase2-full-'+Path(matrix).name);local.mkdir(parents=True,exist_ok=False)
subprocess.run(['rsync','-az',CELLD_FLEET_HOST+':celld-tests-20261010/phase2/exports/'+Path(matrix).name+'/',str(local)+'/'],check=True)
if '--layer' not in args and '--case' not in args and ('--runtime' not in args or args[args.index('--runtime')+1]=='both'):
 subprocess.run(['python3',ROOT/'tests/lib/phase2/report.py',local],check=True)
 subprocess.run(['python3',ROOT/'tests/lib/phase2/audit-results.py',ROOT/'tests/evidence/full-r4-02-05-20261010-171500-AEST-3117998/RESULTS.json',ROOT/'tests/RESULTS.json','--output',ROOT/'tests/NA-AUDIT.json'],check=True)
print('Matrix review export:',local)
raise SystemExit(code)
