import json,os,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);art.mkdir(parents=True,exist_ok=True)
parts=[]
code=subprocess.run(['python3',str(root/'http_runner.py')],cwd=root,env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(art/'snapshot'))).returncode
parts.append({'part':'snapshot','exit':code})
if os.environ.get('CELLD_TEST_RUNTIME','celld')=='celld':
 fixture=art/'fault-fixture';fixture.mkdir()
 for name in ['index.js','wrangler.jsonc']:(fixture/name).write_bytes((root/name).read_bytes())
 (fixture/'expected.json').write_text('{"blocked":true}\n')
 code=subprocess.run(['python3',str(root/'fault.py')],cwd=fixture,env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(art/'output-fault'))).returncode
 parts.append({'part':'output-fault','exit':code})
(art/'parts.json').write_text(json.dumps(parts,indent=2)+'\n');print(json.dumps({'id':'R5-03','parts':parts}))
sys.exit(0 if all(p['exit']==0 for p in parts) else 1)
