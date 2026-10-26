# H26-01 — Dynamic Worker loads refused past a live-count cap

Found 2026-10-26 running Hyperbob main on a five-node celld fleet (lane
CELLD-EVOL). After an Actuarial Desk application was created and saved, the
next open of the Island failed with:

    Failed to connect island to server: worker loader: too many loaded workers
    for script "hb-workshop" in generation 1 (limit 255)

The Workshop's isolated computations (cloudflare-os
`workshop-backend/src/isolated-module.ts`) call `LOADER.load()` once per
invocation and drop the stub without `dispose()`. celld kept every load in its
process registry until the JavaScript handle was collected and refused new
loads once 255 were live for one script generation (256 per process).

workerd has no such admission count. `WorkerLoader::load()`/`get()`
(`src/workerd/api/worker-loader.c++:76-123`, release 2026-10-19) hand the source
to `WorkerLoaderNamespace::load()` (`src/workerd/server/server/loader.rs:66-120`),
which never refuses because other loaded Workers are alive; an unnamed Worker is
owned by its JS handles alone (`loader.rs:50`).

The fixture loads 300 unnamed Workers one after another, each called once and
dropped: in a stateless request, then twice in the same Durable Object. Every
call must succeed. Before the fix celld failed the second Durable Object batch
after 250 loads; stock workerd 1.20261010.1 runs all of them.

Run `python3 run.py` with CELLD_BIN, WORKERD_BIN, CELLD_ESBUILD,
CELLD_TEST_RUNTIME and a fresh CELLD_TEST_ARTIFACTS. Exit 0 proves the
invariant; exit 1 retains the failing observation.
