R9-06. Reference: workerd api/worker-rpc.c++:262–305,359–429.
Pending/resolved result pipelines capture nested values and duplicate callbacks
before mutation/disposal. Returned stubs, plain objects/deeper paths and callable
results run the same program on both runtimes. A resolved target disposed after
admission cannot revoke its admitted call; disposing the root before admission
rejects. Parent failure rejects queued operations. Admission owns the native
argument packet and drops it on parent failure/context abort.
