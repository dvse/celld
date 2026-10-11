#!/usr/bin/env python3
"""run.py CELLD_BINARY: seed with `celld dev`, start nodes a, b, c on one SQLite store with
CELLD_PLACEMENT {"Pinned": ["b", "c"]}, route 20 Pinned and 5 Free cells through node a and
report which node owns each. Pinned cells must land on b and c (both used); Free ones on a."""
import json, os, shutil, signal, socket, subprocess, sys, tempfile, time, urllib.request
binary = os.path.abspath(sys.argv[1])
here = os.path.dirname(os.path.abspath(__file__))
state = tempfile.mkdtemp()
for name in ("index.js", "wrangler.json"):
    shutil.copy(os.path.join(here, name), state)
def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
def get(url, timeout=30):
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
nodes = {}
try:
    for name in ("a", "b", "c"):
        public, internal = port(), port()
        node_env = dict(env, CELLD_INTERNAL_DEV_STORE=os.path.join(state, ".celld/dev/objects.sqlite3"), CELLD_WATCH=os.path.join(state, name), CELLD_NODE=name,
                        CELLD_DURABILITY="bucket", CELLD_PLACEMENT=json.dumps({"Pinned": ["b", "c"]}), CELLD_REBALANCE_INTERVAL_MS="1000")
        os.makedirs(node_env["CELLD_WATCH"])
        child = subprocess.Popen([binary, "--no-control-plane", "--bucket", "celld-dev", "--listen", f"127.0.0.1:{public}", "--internal-listen", f"127.0.0.1:{internal}"],
                                 env=node_env, stdout=open(os.path.join(state, name + ".log"), "w"), stderr=subprocess.STDOUT, start_new_session=True)
        nodes[name] = (child, f"http://127.0.0.1:{public}", f"http://127.0.0.1:{internal}")
    for child, url, internal in nodes.values():
        healthy(url, child)
        urllib.request.urlopen(urllib.request.Request(internal + "/rebalance/pause", data=b"{}"), timeout=5)
    # Placement reads the shared fleet capacity sample; wait until node a has
    # refreshed it with every live node (the seed's claim must expire first).
    deadline = time.monotonic() + 60
    while "fleet_sample_refreshed" not in open(os.path.join(state, "a.log")).read():
        if time.monotonic() > deadline: raise RuntimeError("no fleet sample")
        time.sleep(.5)
    a = nodes["a"][1]
    for i in range(20): get(f"{a}/pinned?n=p{i}")
    for i in range(5): get(f"{a}/free?n=f{i}")
    placed = {}
    for name, (_, _, internal) in nodes.items():
        for scope in json.loads(get(internal + "/state")).get("residents", []):
            placed.setdefault(scope.split(":")[0], {}).setdefault(name, 0)
            placed[scope.split(":")[0]][name] += 1
    pinned, free = placed.get("Pinned", {}), placed.get("Free", {})
    ok = set(pinned) == {"b", "c"} and sum(pinned.values()) == 20 and free == {"a": 5}
    print(json.dumps({"ok": ok, "placed": placed}))
    sys.exit(0 if ok else 1)
finally:
    for child, _, _ in nodes.values():
        child.send_signal(signal.SIGINT)
    for child, _, _ in nodes.values():
        try: child.wait(45)
        except subprocess.TimeoutExpired: child.kill()
    os.rename(state, state + ".done")
