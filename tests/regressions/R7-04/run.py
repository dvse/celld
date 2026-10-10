import os,pathlib,subprocess,json,sys
root=pathlib.Path(__file__).resolve().parent;art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);results=[]
for mode in ['duplicate','transfer']:
 env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(art/mode));p=subprocess.run(['python3',str(root/'http_runner.py')],cwd=root/mode,env=env);results.append({'mode':mode,'exit':p.returncode})
art.mkdir(exist_ok=True,parents=True);(art/'parts.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results));sys.exit(any(x['exit'] for x in results))
