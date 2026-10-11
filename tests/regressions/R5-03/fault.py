"""Late destination-copy failure must hold an ordinary root response."""
import io,json,os,pathlib,runpy,time,urllib.request,urllib.error
original=urllib.request.urlopen
art=pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS'])
port=int(os.environ.get('CELLD_TEST_PORT_BASE','9740'))
def call(url,*args,**kwargs):
 if url != f'http://127.0.0.1:{port}/':return original(url,*args,**kwargs)
 with original(f'http://127.0.0.1:{port}/init-failure',timeout=30) as r:assert json.load(r)==1
 directories=[p for p in (art/'.celld').rglob('*') if p.is_dir() and 'facets' in p.parts]
 assert directories,'fault requires initialized facet directories'
 modes=[(p,p.stat().st_mode&0o777) for p in directories]
 try:
  for p,mode in modes:p.chmod(mode&~0o222)
  try:
   with original(f'http://127.0.0.1:{port}/failure',timeout=30) as r:status=r.status;body=r.read().decode()
  except urllib.error.HTTPError as e:status=e.code;body=e.read().decode()
  # On the baseline the handler may answer before the unawaited copy starts.
  # Keep the fault installed across that continuation, too.
  time.sleep(.5)
  (art/'copy-failure.json').write_text(json.dumps({'status':status,'body':body,'directories':len(modes)},indent=2)+'\n')
  return io.BytesIO(json.dumps({'blocked':status>=500}).encode())
 finally:
  for p,mode in modes:
   if p.exists():p.chmod(mode)
urllib.request.urlopen=call
runpy.run_path(str(pathlib.Path(__file__).resolve().parent.parent/'http_case.py'),run_name='__main__')
