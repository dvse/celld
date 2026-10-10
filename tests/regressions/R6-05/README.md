# R6-05 — persistent call admission

Workerd acquires a live/promised client before returning an RPC promise (worker-rpc.c++:359–374,683–699). Live, stored lazy, and already-pending restore calls must survive immediate last-wrapper disposal. New calls must reject. Covers child pipelining, failed calls and duplicate handles. Run through case.json using the regression contract.

The target creation/disposal totals must balance after calls settle. The Fetcher body control runs on both engines; workerd's Fetcher has no Symbol.dispose, so immediate HTTP disposal and later-call rejection are exercised only where that operation is exposed (celld). This does not claim workerd exposes disposable Fetchers.
