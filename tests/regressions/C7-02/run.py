"""C7-02: one node (`celld dev`, or stock workerd for the differential). Each path is a separate
HTTP request whose response body the runtime pumps; /use is a second live request that must be
refused the stream and target /hold received. Ports: CELLD_TEST_PORT_BASE."""
import concurrent.futures,http.client,json,os,pathlib,shutil,signal,subprocess,sys,time
case=pathlib.Path(__file__).resolve().parent
runtime=os.environ.get('CELLD_TEST_RUNTIME','celld');port=int(os.environ.get('CELLD_TEST_PORT_BASE','9840'))
art=pathlib.Path(os.environ.get('CELLD_TEST_ARTIFACTS') or case/'artifacts').resolve();art.mkdir(parents=True,exist_ok=True)
for name in ('index.js','wrangler.jsonc'):shutil.copy(case/name,art/name)
env=dict(os.environ)
if runtime=='celld':
    esbuild=env.get('CELLD_ESBUILD') or shutil.which('esbuild')
    if not esbuild:print('celld dev needs esbuild (CELLD_ESBUILD)');sys.exit(77)
    env['CELLD_ESBUILD']=esbuild;cmd=[env['CELLD_BIN'],'dev',str(art),'--port',str(port),'--no-watch']
else:
    (art/'test.capnp').write_text('using Workerd = import "/workerd/workerd.capnp";\nconst config :Workerd.Config = (services = [(name = "test", worker = (modules = [(name = "index.js", esModule = embed "index.js")], compatibilityDate = "2026-08-14", compatibilityFlags = ["enable_ctx_exports"]))], sockets = [(name = "http", address = "127.0.0.1:%d", http = (), service = "test")]);\n'%port)
    cmd=[env['WORKERD_BIN'],'serve','--experimental',str(art/'test.capnp')]
log=(art/'server.log').open('w');proc=subprocess.Popen(cmd,cwd=art,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
def get(path):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
    try:c.request('GET',path);r=c.getresponse();return [r.status,r.read().decode(errors='replace')]
    except Exception as e:return ['error',type(e).__name__]
    finally:c.close()
def ws(path):
    # Node's WebSocket client sends 0, 1, 2 and collects three replies.
    r=subprocess.run(['node',str(case/'ws.mjs'),str(port),path],capture_output=True,text=True,timeout=30)
    try:return ['ws',json.loads(r.stdout)]
    except ValueError:return ['ws','error: '+(r.stdout+r.stderr).strip()[-200:]]
try:
    for _ in range(300):
        if proc.poll() is not None:print('runtime exited; see',art/'server.log');sys.exit(1)
        if get('/')[0]==200:break
        time.sleep(.1)
    expected=json.loads((case/'expected.json').read_text());actual={}
    for path in expected:
        if path=='/use':continue
        actual[path]=ws(path) if expected[path][0]=='ws' else get(path)
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        holding=pool.submit(get,'/hold')
        for _ in range(100):
            if get('/held')[1]=='yes':break
            time.sleep(.05)
        actual['/use']=get('/use');holding.result(timeout=30)
    ok=actual==expected
    (art/'result.json').write_text(json.dumps({'runtime':runtime,'pass':ok,'actual':actual,'expected':expected},indent=1)+'\n')
    for path in expected:print(json.dumps({'path':path,'actual':actual[path],'pass':actual[path]==expected[path]}))
    sys.exit(0 if ok else 1)
finally:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGINT)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    log.close()
