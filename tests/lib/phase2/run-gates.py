#!/usr/bin/env python3
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
base=Path.home()/'celld-tests-20261010/phase2';records=json.loads((base/'GATES.json').read_text()) if (base/'GATES.json').exists() else []
for label in sys.argv[1:] or ['fixes','candidate002']:
 root=base/'vm'/label
 if not root.exists():subprocess.run(['python3',str(base/'relocate-vm.py'),label],check=True)
 for name in ['gate-v3','cold-restart-v1']:
  p=root/name;runid=os.urandom(8).hex();start=time.monotonic()
  code=subprocess.call(['python3',str(p/'supervisor.py'),'--run','--run-id',runid,'--expected-inputs-sha256',hashlib.sha256((p/'INPUTS.json').read_bytes()).hexdigest()])
  receipt=p/'runs'/runid/'receipt.json';d=json.loads(receipt.read_text())
  records.append({'column':label,'gate':name,'status':d['status'],'receipt':str(receipt),'exit_code':code,'duration_seconds':round(time.monotonic()-start,3),'error':d.get('error')})
  (base/'GATES.json').write_text(json.dumps(records,indent=2)+'\n')
