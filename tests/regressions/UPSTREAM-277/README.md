# Upstream #277

Source: https://github.com/denoland/celld/issues/277

Run `python3 run.py` with CELLD_BIN, WORKERD_BIN, CELLD_ESBUILD, CELLD_TEST_RUNTIME and a fresh CELLD_TEST_ARTIFACTS. #292 also requires CELLD_V051_BIN. State and binary hashes are retained. Only owned PIDs are signalled. Exit 0 proves the invariant; exit 1 retains the failing observation.

The published constructor-continuation reproduction uses a local origin, independent objects for fetch+storage, storage-only, and blockConcurrencyWhile+storage. No request waitUntil keeps the retired constructor event alive.
