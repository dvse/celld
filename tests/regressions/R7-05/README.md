# R7-05 — synchronous persistent-call parameters

Workerd worker-rpc.c++:359–429 serializes parameters and owns their capabilities
before a live or promised target can yield. The live/lazy/pending matrix mutates
nested input immediately and disposes both the callback and target after calling.
The result must retain value 1 and callback 42, with balanced callback disposal.
Encoding failure preserves the original callback; restore failure releases the
call-owned argument without waiting for GC. Runs through case.json on private
bounded-port MinIO or stock workerd. Baseline and reviewed outcomes are retained
in reviews/fix-7.md; this fixture does not claim transport-cancellation coverage.
