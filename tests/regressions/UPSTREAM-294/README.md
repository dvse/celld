# Upstream #294

Source: https://github.com/denoland/celld/issues/294

Run `python3 run.py` with CELLD_BIN, WORKERD_BIN, CELLD_ESBUILD, CELLD_TEST_RUNTIME and a fresh CELLD_TEST_ARTIFACTS. #292 also requires CELLD_V051_BIN. State and binary hashes are retained. Only owned PIDs are signalled. Exit 0 proves the invariant; exit 1 retains the failing observation.

Independent object names cover timer, fetch, and waitUntil, with and without a first request cancelled after 50 ms. The local origin responds after 500 ms; later requests have a 2 s deadline. Every row must settle.
