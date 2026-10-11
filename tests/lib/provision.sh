#!/usr/bin/env bash
# Source builds and official checksum-verification; no npm build-tool binaries.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
if [[ $(uname -s) != Linux ]]; then
  echo 'Phase-2 tools are built in the owned fleet-host root. See tests/lib/phase2/README.md.' >&2
  exit 2
fi
export PATH="$HOME/.local/share/mise/shims:$HOME/.cargo/bin:$PATH"
python3 "$ROOT/tests/lib/phase2/provision.py" packages
python3 "$ROOT/tests/lib/phase2/complete-sysroot.py"
python3 "$ROOT/tests/lib/phase2/provision.py" esbuild
python3 "$ROOT/tests/lib/phase2/build-pako.py"
python3 "$ROOT/tests/lib/phase2/provision.py" celld
python3 "$ROOT/tests/lib/phase2/verify-workerd.py"
python3 "$ROOT/tests/lib/phase2/provision-wasm.py"
