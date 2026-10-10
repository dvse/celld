"""Run one regression in fresh, retained state. Never touches a shared fleet."""
import json, os, pathlib, signal, subprocess, sys, time, urllib.request
processes=[];logs=[]

case = pathlib.Path.cwd()
runtime = os.environ.get('CELLD_TEST_RUNTIME', 'celld')
port = int(os.environ.get('CELLD_TEST_PORT_BASE', '9740'))
art = pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve()
art.mkdir(parents=True, exist_ok=True)
config = json.loads((case / 'wrangler.jsonc').read_text())
for name in ('index.js', 'wrangler.jsonc'):
    (art / name).write_bytes((case / name).read_bytes())
if runtime == 'celld':
    root=pathlib.Path(os.environ.get('CELLD_TEST_TOOLS_ROOT',str(pathlib.Path.home()/'celld-suite-20261010')))
    if sys.platform!='linux' or any(not (root/'bin'/name).is_file() for name in ['minio','mc']):
        print(json.dumps({'unavailable':'Requires the fleet host's private MinIO/mc in $CELLD_TEST_TOOLS_ROOT/bin (default ~/celld-suite-20261010/bin)'}));sys.exit(77)
    assert 9700 <= port and port+7 <= 9949
    endpoint=f'http://127.0.0.1:{port+6}'
    for key in list(os.environ):
        if key.startswith(('AWS_','MINIO_','S3_')):os.environ.pop(key)
    os.environ.update(AWS_ACCESS_KEY_ID='suite-public',AWS_SECRET_ACCESS_KEY='suite-public-password',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',MINIO_ROOT_USER='suite-public',MINIO_ROOT_PASSWORD='suite-public-password',CELLD_TOKIO_THREADS='2',CELLD_SHUTDOWN_TOTAL_MS='5000')
    os.environ['CELLD_TEST_DATA_DIR']=str(art/'node-data');(art/'node-data').mkdir()
    cmd=[os.environ['CELLD_BIN'],'--bucket','s3://regression','--endpoint',endpoint,'--listen',f'127.0.0.1:{port}','--internal-listen',f'127.0.0.1:{port+1}']
else:
    quote = json.dumps
    bindings = []
    namespaces = []
    for item in config.get('durable_objects', {}).get('bindings', []):
        bindings.append('(name = %s, durableObjectNamespace = %s)' % (quote(item['name']), quote(item['class_name'])))
        namespaces.append('(className = %s, uniqueKey = %s, enableSql = true)' % (quote(item['class_name']), quote(item['class_name'])))
    for item in config.get('worker_loaders', []):
        bindings.append('(name = %s, workerLoader = ())' % quote(item['binding']))
    cfg = '''using Workerd = import "/workerd/workerd.capnp";
const config :Workerd.Config = (
 services = [(name = "test", worker = (
 modules = [(name = "index.js", esModule = embed "index.js")],
 compatibilityDate = %s, compatibilityFlags = %s,
 bindings = [%s], durableObjectNamespaces = [%s],
 durableObjectStorage = (localDisk = "state")
 )), (name = "state", disk = (path = "db", writable = true))],
 sockets = [(name = "http", address = "127.0.0.1:%d", http = (), service = "test")]
);
''' % (quote(config['compatibility_date']), '[' + ','.join(map(quote, config.get('compatibility_flags', []))) + ']', ','.join(bindings), ','.join(namespaces), port)
    (art / 'db').mkdir(exist_ok=True)
    (art / 'test.capnp').write_text(cfg)
    cmd = [os.environ['WORKERD_BIN'], 'serve', '--experimental', str(art / 'test.capnp')]
try:
    if runtime=='celld':
        (art/'store').mkdir()
        store_log=(art/'minio.log').open('w');logs.append(store_log)
        store=subprocess.Popen([str(root/'bin/minio'),'server',str(art/'store'),'--address',f'127.0.0.1:{port+6}','--console-address',f'127.0.0.1:{port+7}'],stdout=store_log,stderr=subprocess.STDOUT,start_new_session=True);processes.append(store)
        for _ in range(200):
            try:urllib.request.urlopen(endpoint+'/minio/health/ready',timeout=.2).close();break
            except OSError:time.sleep(.1)
        mc=[str(root/'bin/mc'),'--config-dir',str(art/'mc')]
        with (art/'setup.log').open('w') as setup:
            subprocess.run(mc+['alias','set','private',endpoint,'suite-public','suite-public-password'],stdout=setup,stderr=setup,check=True)
            subprocess.run(mc+['mb','private/regression'],stdout=setup,stderr=setup,check=True)
            subprocess.run([os.environ['CELLD_BIN'],'deploy',str(art),'--bucket','s3://regression','--endpoint',endpoint],stdout=setup,stderr=setup,check=True)
    log = (art / 'server.log').open('w');logs.append(log)
    proc = subprocess.Popen(cmd, cwd=art, stdout=log, stderr=subprocess.STDOUT, start_new_session=True);processes.append(proc)
    import socket
    for _ in range(300):
        if proc.poll() is not None:
            raise RuntimeError('runtime exited; see ' + str(art / 'server.log'))
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2): break
        except OSError: time.sleep(.1)
    with urllib.request.urlopen(('http://127.0.0.1:%d' % port)+os.environ.get('CELLD_TEST_PATH','/'), timeout=45) as response:
        actual = json.load(response)
    expected = json.loads((case / 'expected.json').read_text())
    result = {'runtime': runtime, 'actual': actual, 'expected': expected, 'pass': actual == expected}
    (art / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    sys.exit(0 if result['pass'] else 1)
finally:
    for process in reversed(processes):
        if process.poll() is None:os.killpg(process.pid, signal.SIGTERM)
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    for log in logs:log.close()
