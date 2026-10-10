R4-12: workerd creates a WorkerEntrypoint for each new top-level RPC session
(worker.c++:2435–2468). Props belong to the binding, not a cached receiver.
The baseline returns increasing counters for empty and nonempty props.
Run with the regression contract environment and `python3 ../http_case.py`.
State and runtime logs remain in CELLD_TEST_ARTIFACTS. Ports are supplied by
the caller; this lane uses 9700–9799.
