R4-11: workerd http.c++:2135–2138/server.c++:796–800 prohibits
serializing a direct facet stub. A private WeakSet retains this policy even
when a facet shares the generic raw-RPC representation. Parameter and return
transfers must fail; an ordinary RpcTarget is the positive control.
