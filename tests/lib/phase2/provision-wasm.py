#!/usr/bin/env python3
"""Build worker tooling and fixture from Cargo sources; never download build binaries."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
B=Path.home()/'celld-tests-20261010/phase2';T=B/'tools';source=T/'wasm-example'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
env={**os.environ,'PATH':str(Path.home()/'.local/share/mise/shims')+':'+str(Path.home()/'.cargo/bin')+':'+os.environ['PATH'],'RUSTUP_TOOLCHAIN':'1.98.1','CARGO_BUILD_JOBS':'8','CARGO_INCREMENTAL':'0','ESBUILD_BIN':str(T/'esbuild'),'WASM_BINDGEN_BIN':str(T/'wasm-bindgen/bin/wasm-bindgen'),'XDG_CACHE_HOME':str(T/'worker-cache')}
if not source.exists():shutil.copytree(B/'suite/tests/conformance/languages/fixtures/wasm-worker',source)
lock=Path(__file__).with_name('wasm-Cargo.lock');shutil.copy2(lock,source/'Cargo.lock')
commands=[(['cargo','install','--locked','--version','0.8.7','worker-build','--root',str(T/'worker-build')],T/'worker-build-install.log'),(['cargo','install','--locked','--version','0.2.129','wasm-bindgen-cli','--root',str(T/'wasm-bindgen')],T/'wasm-bindgen-build.log'),(['rustup','target','add','wasm32-unknown-unknown'],T/'wasm-target.log'),([str(T/'worker-build/bin/worker-build'),'--release','--no-opt','--','--locked'],T/'wasm-example-build.log')]
# --receipt-only records the completed same commands without rebuilding.
if '--receipt-only' not in __import__('sys').argv:
 for args,log in commands:
  with log.open('ab') as f:subprocess.run(args,cwd=source,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=900)
pins={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file() and 'target' not in p.relative_to(source).parts}
receipt={'commands':[x[0] for x in commands],'rust':'1.98.1','source_files':pins,'tools':{str(p):sha(p) for p in [T/'worker-build/bin/worker-build',T/'wasm-bindgen/bin/wasm-bindgen',T/'esbuild']},'policy':'all build binaries compiled from pinned Cargo/Go source; wasm-opt disabled; explicit binary overrides prevent prebuilt downloads'}
(T/'wasm-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
