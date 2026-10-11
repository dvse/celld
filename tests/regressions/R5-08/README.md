# R5-08 — disposer capture

Runs the actual entry construction and release functions with controlled context/route adapters. Requires one source-context lookup at export, original source-context callback after replacement, rejection of a throwing getter before insertion, and no retained entry after native revocation failure. Workerd `worker-rpc.c++:1565–1576,1622–1644` captures the disposer at export. This is a source unit regression, not a network test.
