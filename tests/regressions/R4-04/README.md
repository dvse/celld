R4-04: native V8 ownership regression. The clock is advanced by changing the
entry's start Instant, not by shortening the production 900-second limit.
The test queues a ready native completion, times out an alarm and asserts
that the resolver cannot run, the old resource is revoked, pending operations
are dropped and a fresh incarnation receives a new identity.
Workerd global-scope.c++:626–654 aborts the IoContext and counts this retry.
Run `python3 run.py`; CELLD_REPO can select a separate baseline clone with
native.rs included in its js/ownership_tests.rs. No internal-test simulation
flag is needed. Source inspection of turn_finish_alarm additionally verifies
the timeout's counted-retry settlement; this is not a retry-ceiling fleet test.
