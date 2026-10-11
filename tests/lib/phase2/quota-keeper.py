#!/usr/bin/env python3
"""Unprivileged private mount namespace; exactly one bounded owned tmpfs."""
import os,signal,subprocess,sys
from pathlib import Path
path=Path(sys.argv[1]).resolve();size=int(sys.argv[2])
root=Path(sys.argv[3]).resolve()
assert path.is_relative_to(root/'tests/artifacts') and path.name=='working'
subprocess.run(['mount','--make-rprivate','/'],check=True)
subprocess.run(['mount','-t','tmpfs','-o','size='+str(size)+',mode=700','celld-owned-quota',str(path)],check=True)
(path/'.quota-ready').write_text(str(os.getpid())+'\n')
while True:signal.pause()
