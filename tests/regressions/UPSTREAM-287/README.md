# Upstream #287

Source: https://github.com/denoland/celld/issues/287

Run `python3 run.py` with CELLD_BIN, WORKERD_BIN, CELLD_ESBUILD, CELLD_TEST_RUNTIME and a fresh CELLD_TEST_ARTIFACTS. #292 also requires CELLD_V051_BIN. State and binary hashes are retained. Only owned PIDs are signalled. Exit 0 proves the invariant; exit 1 retains the failing observation.

The published loader/facet WebSocket reproduction retains handler and waitUntil positive controls and the unkept async-loop trigger. All three must reply pong.
