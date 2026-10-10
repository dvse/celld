import os,json,pathlib,subprocess,sys
case=pathlib.Path.cwd();art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);rows=[]
for mode in ['duplicate','transfer']:
 fixture=art/mode;fixture.mkdir(parents=True)
 for name in ['index.js','expected.json','http_runner.py']:(fixture/name).write_bytes((case/name).read_bytes())
 config=json.loads((case/'wrangler.jsonc').read_text())
 if mode=='transfer':config['compatibility_flags'].append('rpc_params_transfer_stubs')
 (fixture/'wrangler.jsonc').write_text(json.dumps(config))
 run=fixture/'run';run.mkdir()
 p=subprocess.run(['python3','http_runner.py'],cwd=fixture,env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(run)))
 rows.append({'mode':mode,'exit':p.returncode})
(art/'parts.json').write_text(json.dumps(rows,indent=2)+'\n');sys.exit(int(any(r['exit'] for r in rows)))
