#!/usr/bin/env python3
"""run-bucket.py CELLD_BINARY: the facet-clone fixture with bucket durability. Seed with `celld
dev`, run /prepare on node a, stop it, then on node b (an empty local directory, so every stream
restores from the bucket) run /reclone and /report."""
import os, shutil, signal, socket, subprocess, sys, tempfile, time, urllib.request
binary = os.path.abspath(sys.argv[1])
here = os.path.dirname(os.path.abspath(__file__))
state = tempfile.mkdtemp()
for name in ("index.js", "wrangler.json"):
    shutil.copy(os.path.join(here, name), state)
def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
def get(url, timeout=60):
    with urllib.request.urlopen(url, timeout=timeout) as r: return r.read().decode()
def healthy(url, child):
    for _ in range(120):
        if child.poll() is not None: raise RuntimeError("node exited")
        try: get(url + "/.well-known/celld/health", 2); return
        except Exception: time.sleep(.5)
    raise RuntimeError("not healthy")
env = {k: v for k, v in os.environ.items() if not k.startswith("CELLD_") or k == "CELLD_ESBUILD"}
seed_port = port()
seed = subprocess.Popen([binary, "dev", state, "--port", str(seed_port), "--no-watch"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
healthy(f"http://127.0.0.1:{seed_port}", seed)
seed.send_signal(signal.SIGINT); seed.wait(30)
def node(name):
    public, internal = port(), port()
    node_env = dict(env, CELLD_INTERNAL_DEV_STORE=os.path.join(state, ".celld/dev/objects.sqlite3"), CELLD_WATCH=os.path.join(state, name), CELLD_NODE=name, CELLD_DURABILITY="bucket")
    os.makedirs(node_env["CELLD_WATCH"])
    child = subprocess.Popen([binary, "--no-control-plane", "--bucket", "celld-dev", "--listen", f"127.0.0.1:{public}", "--internal-listen", f"127.0.0.1:{internal}"],
                             env=node_env, stdout=open(os.path.join(state, name + ".log"), "w"), stderr=subprocess.STDOUT, start_new_session=True)
    url = f"http://127.0.0.1:{public}"
    healthy(url, child)
    return child, url, f"http://127.0.0.1:{internal}"
def stop(child, internal):
    try: urllib.request.urlopen(urllib.request.Request(internal + "/shutdown?handoff=preserve", data=b""), timeout=60)
    except Exception: child.send_signal(signal.SIGINT)
    try: child.wait(60)
    except subprocess.TimeoutExpired: child.kill()
try:
    a, url, internal = node("a")
    print("/prepare", get(url + "/prepare"))
    stop(a, internal)
    time.sleep(16)  # the stopped node's lease lapses
    b, url, internal = node("b")
    print("/reclone", get(url + "/reclone"))
    print("/report", get(url + "/report"))
    stop(b, internal)
finally:
    os.rename(state, state + ".done")
