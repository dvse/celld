#!/usr/bin/env python3
"""run.py CELLD_BINARY: nodes a and b on one store, Gate placed on a and Planet on b. Planet keeps a
dup() of a Gate capability made in one event (fetch or RPC) and uses it in a later event."""
import json, os, shutil, signal, socket, subprocess, sys, tempfile, time, urllib.request
binary = os.path.abspath(sys.argv[1]); here = os.path.dirname(os.path.abspath(__file__))
state = tempfile.mkdtemp()
for name in ("index.js", "wrangler.json"): shutil.copy(os.path.join(here, name), state)
def port():
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
def healthy(url, child):
    for _ in range(120):
        if child.poll() is not None: raise RuntimeError("node exited")
        try: urllib.request.urlopen(url + "/.well-known/celld/health", timeout=2); return
        except Exception: time.sleep(.5)
    raise RuntimeError("not healthy")
env = {k: v for k, v in os.environ.items() if not k.startswith("CELLD_") or k == "CELLD_ESBUILD"}
p = port(); seed = subprocess.Popen([binary, "dev", state, "--port", str(p), "--no-watch"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
healthy(f"http://127.0.0.1:{p}", seed); seed.send_signal(signal.SIGINT); seed.wait(30)
nodes = {}
try:
    for name in ("a", "b"):
        public, internal = port(), port()
        e = dict(env, CELLD_INTERNAL_DEV_STORE=os.path.join(state, ".celld/dev/objects.sqlite3"), CELLD_WATCH=os.path.join(state, name), CELLD_NODE=name,
                 CELLD_DURABILITY="bucket", CELLD_PLACEMENT=json.dumps({"Gate": ["a"], "Planet": ["b"]}), CELLD_REBALANCE_INTERVAL_MS="1000")
        os.makedirs(e["CELLD_WATCH"])
        nodes[name] = (subprocess.Popen([binary, "--no-control-plane", "--bucket", "celld-dev", "--listen", f"127.0.0.1:{public}", "--internal-listen", f"127.0.0.1:{internal}"],
                       env=e, stdout=open(os.path.join(state, name + ".log"), "w"), stderr=subprocess.STDOUT, start_new_session=True), public, internal)
    for child, public, internal in nodes.values(): healthy(f"http://127.0.0.1:{public}", child)
    time.sleep(2)
    a = nodes["a"][1]
    def get(path): return urllib.request.urlopen(f"http://127.0.0.1:{a}{path}", timeout=60).read().decode()
    out = {}
    for kind in ("fetch", "rpc", "wrapped", "lazy-env", "lazy-exports"):
        out[kind] = [get(f"/{kind}/keep"), get(f"/{kind}/use")]
    client = os.path.join(here, "client.mjs")
    socket = subprocess.run(["node", client, f"ws://127.0.0.1:{a}/socket"], capture_output=True, text=True, timeout=60)
    out["socket"] = socket.stdout.strip()
    residents = {name: json.loads(urllib.request.urlopen(f"http://127.0.0.1:{internal}/state").read()).get("residents", []) for name, (_, _, internal) in nodes.items()}
    print(json.dumps({"results": out, "residents": residents}))
finally:
    for child, _, _ in nodes.values(): child.send_signal(signal.SIGINT)
    for child, _, _ in nodes.values():
        try: child.wait(45)
        except subprocess.TimeoutExpired: child.kill()
    os.rename(state, state + ".done")
