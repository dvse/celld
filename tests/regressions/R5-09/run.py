import os,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS'])
codes=[]
for mode in ('prototype','instance'):
 env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(art/mode))
 codes.append(subprocess.run(['python3',str(root.parent/'http_case.py')],cwd=root/mode,env=env).returncode)
sys.exit(0 if codes==[0,0] else 1)
