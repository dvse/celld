# OR1-05 — client held before parameter serialization (Opus review 1, P2-5; structural change 1)

ported-2 `d6cf644` only *checked* the stub in `__invokeAdmitted` before
serializing parameters; a parameter getter that disposed the stub made
`__stubOp` reject the call. workerd acquires the one-call client first
(api/worker-rpc.c++:262-305, :364) and delivers it. Fixed by `acquire()`
taking a client reference that is released once the call holds its own.
The fixture also checks call-time capture through a pipelined RpcPromise and
that a stub disposed *before* the call still rejects. Differential with stock
workerd. Expected: passes on ported (old order) and workerd, fails on
`d6cf644` (`actorTarget`/`serviceTarget` reject), passes after the fix.
