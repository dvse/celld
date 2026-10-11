# workerd port provenance

Reference checkout: workerd `19b1657bd`. `upstream/` preserves original Apache-2.0
assertions and `.wd-test` configurations. Globals run original exported test
functions. Durable Object HTTP ports select stub identity, RPC receiver, KV
list/transaction and SQLite behavior from actor-stub-test and actor-kv-test;
HTTP transport and deterministic observations replace the workerd test service.
These selected cases do not claim the complete upstream contract suite.
