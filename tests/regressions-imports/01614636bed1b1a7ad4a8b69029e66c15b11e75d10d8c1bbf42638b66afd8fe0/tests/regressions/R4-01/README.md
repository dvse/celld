# R4-01 — session completion (partial finding)

A stateless Factory retains a duplicated argument and returns two independent
children. Releasing only one must retain the session; releasing both must end
it and release its held argument. Workerd's CompletionMembrane owns this
lifetime (worker-rpc.c++). The HTTP case uses real RPC on both runtimes.

This regression covers explicit local completion only. It does not establish
remote holder crash cleanup or serialization rollback. Those portions of
R4-01 remain open; no claim of full session/connection ownership is made.
