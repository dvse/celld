# R4-10 — disputed; reference controls

Stock workerd hides ctx.restore without allow_irrevocable_stub_storage:
actor-state.h:720–722 and global-scope.h:385–387. With the flag, plain token
parameters work and persist, but an RpcTarget parameter is rejected during
Frankenvalue creation ("Remote RPC references can only be serialized for RPC").

This control is expected to PASS on def239b, patched celld and workerd. It
refutes the proposed no-flag/live-transient regression, rather than inventing
a failing baseline for a behavior the reference does not support. Exact
property exposure/error wording without the flag remains different. Other
Frankenvalue host types have not been exhaustively compared.
