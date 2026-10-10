import os,subprocess,sys,pathlib,json
case=pathlib.Path.cwd();art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']);parts=[]
for part in ['enabled','disabled']:
 run=art/part;run.mkdir()
 if part=='enabled':
  cmd=['python3','http_runner.py' if os.environ['CELLD_TEST_RUNTIME']=='workerd' else 'fleet.py'];cwd=case
 else:
  cwd=art/'disabled-fixture';cwd.mkdir()
  for name in ['index.js','http_runner.py']:(cwd/name).write_bytes((case/name).read_bytes())
  config=json.loads((case/'wrangler.jsonc').read_text());config['compatibility_flags']=[]
  (cwd/'wrangler.jsonc').write_text(json.dumps(config));(cwd/'expected.json').write_text('{"gated":true}\n');cmd=['python3','http_runner.py']
 p=subprocess.run(cmd,cwd=cwd,env=dict(os.environ,CELLD_TEST_ARTIFACTS=str(run),CELLD_TEST_PATH='/gate' if part=='disabled' else '/'))
 parts.append({'part':part,'exit':p.returncode})
(art/'parts.json').write_text(json.dumps(parts,indent=2)+'\n');sys.exit(int(any(p['exit'] for p in parts)))
