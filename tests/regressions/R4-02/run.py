import os,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
if os.environ.get('CELLD_TEST_RUNTIME','celld')=='celld':
 r=subprocess.call(['node','run.mjs'],cwd=root)
 if r:sys.exit(r)
sys.exit(subprocess.call([sys.executable,str(root.parent/'http_case.py')],cwd=root/'http'))
