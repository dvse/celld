#!/usr/bin/env python3
"""Run suite with explicitly pinned source-built binaries; no implicit bootstrap."""
import json,os,subprocess,sys,time
from pathlib import Path
base=Path.home()/'celld-tests-20261010/phase2';label=sys.argv[1];r=json.loads((base/'builds/BUILD-RECEIPTS.json').read_text())[label]
env={**os.environ,'PATH':str(Path.home()/'.local/share/mise/shims')+':'+str(Path.home()/'.cargo/bin')+':'+os.environ['PATH'],'RUSTUP_TOOLCHAIN':'1.98.1','CELLD_BIN':r['binary'],'CELLD_ESBUILD':str(base/'tools/esbuild'),'WORKERD_BIN':str(base/'tools/stock-workerd/package/bin/workerd'),'CELLD_TEST_SOURCE_COMMIT':r['commit'],'CARGO_BUILD_JOBS':'8'}
raise SystemExit(subprocess.call(['systemd-run','--user','--scope','--unit=celld-tests-20261010-focused-'+str(time.time_ns()),'python3',str(base/'suite/tests/lib/runner.py'),*sys.argv[2:],'--remote-worker'],env=env,cwd=base/'suite'))
