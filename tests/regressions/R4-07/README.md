R4-07: source-owned disposal (workerd worker-rpc.c++:1565–1576).
The actual __disposeStub function runs against a context-entry adapter that
tracks the active owner and refuses dead-context re-entry. Checks the source
owner, unchanged holder, once-only cleanup, and no resurrection after abort.
The baseline executes twice in the holder context and never attempts re-entry.
Run `node run.mjs`; CELLD_SOURCE can select the def239b harness.
