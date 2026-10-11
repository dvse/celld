#!/usr/bin/env python3
"""run-node.py CELLD_BINARY BUCKET [PATH]: the core-fidelity checks (or the fixture in $FIXTURE_DIR, GET PATH only) on a fleet node (bucket durability, one
node), where stateless entrypoints and Durable Objects run in separate isolate pools, so a
returned stub crosses isolates through the live-capability transport. /keep, then /use after
two 30 s reap passes (D2); /slow?ms=65000 (D1). BUCKET is an empty S3 bucket (s3://name), reached
with the S3_ENDPOINT and AWS_* variables of the environment; `celld deploy` needs a real bucket,
so the dev store cannot hold the second script."""
import os, shutil, signal, socket, subprocess, sys, tempfile, time, urllib.request
binary = os.path.abspath(sys.argv[1]); bucket = sys.argv[2]
here = os.environ.get("FIXTURE_DIR") or os.path.dirname(os.path.abspath(__file__))
state = tempfile.mkdtemp()
for name in ("index.js", "wrangler.json"): shutil.copy(os.path.join(here, name), state)
def port():
    with socket.socket() as s: s.bind(("127.0.0.1", 0)); return s.getsockname()[1]
def get(url, timeout=150):
    with urllib.request.urlopen(url, timeout=timeout) as r: return r.read().decode()
def healthy(url, child):
    for _ in range(120):
        if child.poll() is not None: raise RuntimeError("node exited")
        try: get(url + "/.well-known/celld/health", 2); return
        except Exception: time.sleep(.5)
    raise RuntimeError("not healthy")
env = {k: v for k, v in os.environ.items() if not k.startswith("CELLD_") or k == "CELLD_ESBUILD"}
# Sibling scripts first (each subdirectory with a wrangler.json), the main script last, so the
# main one is the ingress.
siblings = sorted(d for d in os.listdir(here) if os.path.isfile(os.path.join(here, d, "wrangler.json")))
for d in siblings: shutil.copytree(os.path.join(here, d), os.path.join(state, d))
for project in [os.path.join(state, d) for d in siblings] + [state]:
    r = subprocess.run([binary, "deploy", project, "--bucket", bucket], env=env, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-2000:] + r.stdout[-1000:])
public, internal = port(), port()
e = dict(env, CELLD_WATCH=os.path.join(state, "a"), CELLD_NODE="a", CELLD_DURABILITY="bucket")
os.makedirs(e["CELLD_WATCH"])
log = os.path.join(state, "a.log")
child = subprocess.Popen([binary, "--no-control-plane", "--bucket", bucket, "--listen", f"127.0.0.1:{public}", "--internal-listen", f"127.0.0.1:{internal}"], env=e, stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True)
try:
    url = f"http://127.0.0.1:{public}"
    healthy(url, child)
    if len(sys.argv) > 3:
        print(sys.argv[3], get(url + sys.argv[3])); sys.exit(0)
    for path in ("/restore", "/waituntil", "/keep", "/slow?ms=65000"):
        print(path, get(url + path), flush=True)
    time.sleep(40)
    print("/use", get(url + "/use"))
    print("isolates freed during run:", open(log).read().count("isolate freed"))
finally:
    child.send_signal(signal.SIGINT)
    try: child.wait(45)
    except subprocess.TimeoutExpired: child.kill()
    os.rename(state, state + ".done")
