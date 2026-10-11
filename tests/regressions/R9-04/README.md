R9-04 / R8-04. Workerd api/worker-rpc.c++:359–429 owns parameters at admission.
Cold/warm loader and facet calls, including a facet clone barrier, immediately
mutate data and dispose the callback. Each call must retain [1,42]. Failed startup
must reject. The shared admission helper cancels undelivered native packets on
failure/context abort and releases a losing late result. Ports 9700–9799.
