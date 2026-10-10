R9-03 / R8-03: class props are reusable channel graphs, not one-use RPC packets.
Reference: workerd api/export-loopback.c++:32–41, api/worker-loader.c++:51–73,
server/server.c++:4097–4105. Both parameter-ownership modes run the same assertions.
Static and loaded classes initialize two facets, then abort/reopen. Static class
handles are stored twice and forwarded twice. Caller wrapper remains usable;
transient RpcTarget/readable/writable props reject at specialization.
The live packet reuse failure was introduced by f52475a; baseline also controls
its older transient-props acceptance and wrapper move behavior.
