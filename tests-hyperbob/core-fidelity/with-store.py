#!/usr/bin/env python3
"""with-store.py INSTANCE_DIR CELLD_BINARY [PATH]: run run-node.py against a fresh bucket in the
instance's own MinIO object store (credentials from the instance, never printed)."""
import importlib.util, os, subprocess, sys, time
instance_dir, binary = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("host", os.path.join(instance_dir, "celld-host.py"))
host = importlib.util.module_from_spec(spec); spec.loader.exec_module(host)
instance = host.Instance(instance_dir)
env = {**os.environ, **instance.store_env()}
name = f"celld-fixture-{int(time.time())}"
mc = os.path.expanduser(instance.config["mc"])
subprocess.run([mc, "mb", f"hb/{name}"], env={**os.environ, "MC_CONFIG_DIR": str(instance.dir / "mc")}, check=True, stdout=subprocess.DEVNULL)
here = os.path.dirname(os.path.abspath(__file__))
sys.exit(subprocess.run([sys.executable, os.path.join(here, "run-node.py"), binary, f"s3://{name}", *sys.argv[3:]], env=env).returncode)
