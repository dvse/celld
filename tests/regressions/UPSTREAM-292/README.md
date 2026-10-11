# Upstream #292

Source: https://github.com/denoland/celld/issues/292

Run `python3 run.py` with CELLD_BIN, WORKERD_BIN, CELLD_ESBUILD, CELLD_TEST_RUNTIME and a fresh CELLD_TEST_ARTIFACTS. #292 also requires CELLD_V051_BIN. State and binary hashes are retained. Only owned PIDs are signalled. Exit 0 proves the invariant; exit 1 retains the failing observation.

Writes and reads a1/a2 using official v0.5.1, gracefully stops it, then opens exactly the same fresh state with the candidate and checks both root and facet rows. Workerd has no celld disk-format migration.
