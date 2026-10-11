R4-09: actual __makeNode unit test, with a dispatch counter. A saved
method must fail after root disposal; awaiting the underlying root remains
valid (workerd worker-rpc.c++:248–310,562–574). Repeated disposal is included.
CELLD_SOURCE selects a baseline or fixed harness; run `node run.mjs`.
