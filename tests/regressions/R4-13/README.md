R4-13: concurrently active stateless sessions A and B share module state.
A retains a received target while B tries method, property and dup operations.
All must reject with workerd's cross-request ownership error, before execution
or reference acquisition. A's same-session call is the positive control.
Workerd worker-rpc.c++:683–731 and io-own.h:379–386.
