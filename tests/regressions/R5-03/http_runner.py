"""Run one regression in fresh, retained state. Never touches a shared fleet."""
import json, os, pathlib, signal, subprocess, sys, time, urllib.request

case = pathlib.Path.cwd()
runtime = os.environ.get('CELLD_TEST_RUNTIME', 'celld')
port = int(os.environ.get('CELLD_TEST_PORT_BASE', '9740'))
art = pathlib.Path(os.environ['CELLD_TEST_ARTIFACTS']).resolve()
art.mkdir(parents=True, exist_ok=True)
config = json.loads((case / 'wrangler.jsonc').read_text())
for name in ('index.js', 'wrangler.jsonc'):
    (art / name).write_bytes((case / name).read_bytes())
if runtime == 'celld':
    cmd = [os.environ['CELLD_BIN'], 'dev', str(art), '--port', str(port), '--no-watch']
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
log = (art / 'server.log').open('w')
proc = subprocess.Popen(cmd, cwd=art, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
try:
    import socket
    for _ in range(300):
        if proc.poll() is not None:
            raise RuntimeError('runtime exited; see ' + str(art / 'server.log'))
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=.2): break
        except OSError: time.sleep(.1)
    with urllib.request.urlopen('http://127.0.0.1:%d/' % port, timeout=45) as response:
        actual = json.load(response)
    expected = json.loads((case / 'expected.json').read_text())
    result = {'runtime': runtime, 'actual': actual, 'expected': expected, 'pass': actual == expected}
    (art / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
    sys.exit(0 if result['pass'] else 1)
finally:
    os.killpg(proc.pid, signal.SIGTERM) if proc.poll() is None else None
    try: proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait()
    log.close()
