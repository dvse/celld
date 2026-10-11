R4-15: actual pipeline proxy unit, with observable GET and root-resolution
counters. Workerd worker-rpc.c++:542–574 distinguishes RpcProperty observations
from RpcPromise observations. Baseline returns [1,1,1,1]; fixed [1,2,3,4].
Run `node run.mjs` with optional CELLD_SOURCE.
