#!/usr/bin/env python3
"""Exercise real kernel limits, namespace preservation, and escaped-PGID cleanup."""
import json,os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from common import Process,dump
from phase2.guard import Guard
out=Path(sys.argv[1]);out.mkdir(parents=True)
profile={'rss_bytes':64*1024**2,'disk_bytes':1024**2,'pids':32,'wave_seconds':30,'cpu_seconds':10}
results={}
for name,script,expected in [
 ('normal',"from pathlib import Path;Path('proof').write_text('preserved');print('ok')",False),
 ('deadline','import time;time.sleep(10)',True),
 ('memory','x=bytearray(128*1024**2);print(len(x))',True),
 ('filesystem',"import errno;from pathlib import Path\ntry:Path('large').write_bytes(b'x'*(2*1024**2))\nexcept OSError as e:assert e.errno==errno.ENOSPC\nelse:raise Exception('quota absent')",False),
 ('escaped-pgid',"import os,time\npid=os.fork()\nif not pid:os.setsid();time.sleep(30)\nelse:print(pid)",True)]:
 g=Guard(out/name,profile);p=Process(['/usr/bin/python3','-c',script],g.workspace,g.workspace/'child.log',g.environment(os.environ));g.register(name,p,64)
 if name=='deadline':g.begin(name,.15)
 p.p.wait(timeout=5);p.stop();r=g.finish();assert bool(r['violations'])==expected,(name,r['violations']);assert not r['kernel_domain']['remaining_pids'];assert (out/name/'retained/child.log').exists()
 if name=='filesystem':assert p.p.returncode==0 and (out/name/'retained/large').stat().st_size<2*1024**2
 results[name]={'pass':True,'violations':r['violations'],'kernel':r['kernel_domain']['final']}
dump(out/'CHECKS.json',results);print(json.dumps(results,indent=2))
