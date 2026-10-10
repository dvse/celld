# R5-06 — lazy persistent client ownership

Object A stores and reloads a token without resolving it. B attempts a method, getter, dup, storage serialization and RPC return; each must refuse foreign authority before restoration. Then A resolves the same handle in a later event and B repeats the checks. An explicit transfer from A is a positive control. Workerd `worker-rpc.c++:939–945`, `io-own.h:379–386` assigns ownership at deserialization, not at first use.
