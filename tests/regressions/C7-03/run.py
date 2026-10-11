"""C7-03: one node (`celld dev`, or stock workerd for the differential). /hold keeps the stubs it
made or received for up to 8 s; /use (another live request) and /later (after /hold finished)
try them. Ports: CELLD_TEST_PORT_BASE."""
import concurrent.futures,http.client,json,os,pathlib,shutil,signal,subprocess,sys,time
case=pathlib.Path(__file__).resolve().parent
runtime=os.environ.get('CELLD_TEST_RUNTIME','celld');port=int(os.environ.get('CELLD_TEST_PORT_BASE','9840'))
art=pathlib.Path(os.environ.get('CELLD_TEST_ARTIFACTS') or case/'artifacts').resolve();art.mkdir(parents=True,exist_ok=True)
for name in ('index.js','wrangler.jsonc','y.js','y.json'):shutil.copy(case/name,art/name)
env=dict(os.environ)
if runtime=='celld':
    esbuild=env.get('CELLD_ESBUILD') or shutil.which('esbuild')
    if not esbuild:print('celld dev needs esbuild (CELLD_ESBUILD)');sys.exit(77)
    env['CELLD_ESBUILD']=esbuild;cmd=[env['CELLD_BIN'],'dev',str(art/'wrangler.jsonc'),'--port',str(port),'--no-watch']
    # The second script is deployed first into the same dev store.
    y=subprocess.Popen([env['CELLD_BIN'],'dev',str(art/'y.json'),'--port',str(port),'--no-watch'],cwd=art,env=env,stdout=(art/'y.log').open('w'),stderr=subprocess.STDOUT,start_new_session=True)
    for _ in range(300):
        try:
            c=http.client.HTTPConnection('127.0.0.1',port,timeout=2);c.request('GET','/');c.getresponse().read();c.close();break
        except Exception:time.sleep(.1)
    os.killpg(y.pid,signal.SIGINT);y.wait(timeout=15);time.sleep(1)
else:
    (art/'db').mkdir(exist_ok=True)
    (art/'test.capnp').write_text('using Workerd = import "/workerd/workerd.capnp";\nconst config :Workerd.Config = (services = [(name = "c7-03", worker = (modules = [(name = "index.js", esModule = embed "index.js")], compatibilityDate = "2026-08-14", compatibilityFlags = ["enable_ctx_exports", "experimental"], bindings = [(name = "LOADER", workerLoader = ()), (name = "SELF", service = (name = "c7-03", entrypoint = "Ent")), (name = "Y", service = (name = "c7-03y", entrypoint = "Ent")), (name = "D", durableObjectNamespace = "D")], durableObjectNamespaces = [(className = "D", uniqueKey = "D", enableSql = true)], durableObjectStorage = (localDisk = "state"))), (name = "c7-03y", worker = (modules = [(name = "y.js", esModule = embed "y.js")], compatibilityDate = "2026-08-14", compatibilityFlags = ["enable_ctx_exports", "experimental"])), (name = "state", disk = (path = "db", writable = true))], sockets = [(name = "http", address = "127.0.0.1:%d", http = (), service = "c7-03")]);\n'%port)
    cmd=[env['WORKERD_BIN'],'serve','--experimental',str(art/'test.capnp')]
log=(art/'server.log').open('w');proc=subprocess.Popen(cmd,cwd=art,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
def get(path):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=30)
    try:
        c.request('GET',path);r=c.getresponse();body=r.read().decode(errors='replace')
        try:body=json.loads(body)
        except ValueError:pass
        return [r.status,body]
    except Exception as e:return ['error',type(e).__name__]
    finally:c.close()
try:
    for _ in range(300):
        if proc.poll() is not None:print('runtime exited; see',art/'server.log');sys.exit(1)
        if get('/')[0]==200:break
        time.sleep(.1)
    actual={}
    with concurrent.futures.ThreadPoolExecutor(1) as pool:
        holding=pool.submit(get,'/hold')
        for _ in range(200):
            if get('/held')[1]=='yes':break
            time.sleep(.05)
        actual['/own']=get('/own');actual['/use']=get('/use');actual['/hold']=holding.result(timeout=30)
    actual['/later']=get('/later');actual['/keep']=get('/keep');actual['/actors']=get('/actors');actual['/handles']=get('/handles')
    actual['/park']=get('/park');time.sleep(.3);actual['/wake']=get('/wake');time.sleep(.3);actual['/late']=get('/late')
    expected=json.loads((case/'expected.json').read_text()) if (case/'expected.json').exists() else None
    ok=actual==expected
    (art/'result.json').write_text(json.dumps({'runtime':runtime,'pass':ok,'actual':actual,'expected':expected},indent=1)+'\n')
    for path in actual:print(json.dumps({'path':path,'actual':actual[path],'pass':expected is not None and actual[path]==expected.get(path)}))
    sys.exit(0 if ok else 1)
finally:
    if proc.poll() is None:os.killpg(proc.pid,signal.SIGINT)
    try:proc.wait(timeout=10)
    except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
    log.close()
