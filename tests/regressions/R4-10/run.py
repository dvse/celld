import os, pathlib, subprocess, sys
root=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS'])
results=[]
for mode in ['disabled','enabled']:
 env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(art/mode))
 results.append(subprocess.call([sys.executable,str(root.parent/'http_case.py')],cwd=root/mode,env=env))
sys.exit(0 if all(r==0 for r in results) else 1)
