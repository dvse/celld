import os,pathlib,subprocess,json,sys
root=pathlib.Path(__file__).resolve().parent;art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);results=[]
for destination in ['2']:
 env=dict(os.environ,DESTINATION=destination,CELLD_TEST_ARTIFACTS=str(art/('owner-'+destination)))
 p=subprocess.run(['python3',str(root/'fleet.py')],env=env);results.append({'destination':destination,'exit':p.returncode})
(art/'parts.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results));sys.exit(any(x['exit'] for x in results))
