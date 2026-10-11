# bindings

72 cases; 68 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [container](container.case.json) | yes | N/A; see header |
| [cron](cron.case.json) | yes | example |
| [Keep rebound prepared statements independent](d1-e201.case.json) | no | http |
| [Address repeated numbered placeholders](d1-e202.case.json) | no | http |
| [Round-trip application scalar settings](d1-e203.case.json) | no | http |
| [Copy and encode binary bind sources](d1-e204.case.json) | no | http |
| [Keep all and run result semantics aligned](d1-e205.case.json) | no | http |
| [Distinguish first row scalar and absence](d1-e206.case.json) | no | http |
| [Preserve export headings and column order](d1-e207.case.json) | no | http |
| [Preserve own properties for special column labels](d1-e208.case.json) | no | http |
| [Retain duplicate columns in raw projections](d1-e209.case.json) | no | http |
| [Run successful schema and data dependencies in batch](d1-e210.case.json) | no | http |
| [Snapshot mutation metadata per batch statement](d1-e211.case.json) | no | http |
| [Parse exec statements without splitting SQL text](d1-e212.case.json) | no | http |
| [Drain row-producing exec statements before return](d1-e213.case.json) | no | http |
| [Reset readonly metadata after an acknowledged write](d1-e214.case.json) | no | http |
| [Distinguish schema changes from no-op writes](d1-e215.case.json) | no | http |
| [Complete mutations behind first RETURNING](d1-e216.case.json) | no | http |
| [Advance and resume independent query sessions](d1-e217.case.json) | no | http |
| [Advance a session after successful batch commit](d1-e218.case.json) | no | http |
| [Share configured database aliases and isolate identities](d1-e219.case.json) | no | http |
| [Resolve omitted IDs through database names](d1-e220.case.json) | no | http |
| [d1](d1.case.json) | no | example |
| [Keep empty values distinct from missing keys](kv-k201.case.json) | no | http |
| [Materialize independent JSON configuration reads](kv-k202.case.json) | no | http |
| [Snapshot a sliced binary input before reuse](kv-k203.case.json) | no | http |
| [Keep returned binary buffers detached from storage](kv-k204.case.json) | no | http |
| [Assemble a finite chunked upload before decoding](kv-k205.case.json) | no | http |
| [Preserve an active-request download snapshot](kv-k206.case.json) | no | http |
| [Snapshot structured metadata on write and read](kv-k207.case.json) | no | http |
| [Replace and clear record annotations](kv-k208.case.json) | no | http |
| [Preserve null and falsy metadata presence](kv-k209.case.json) | no | http |
| [Pair special key names in a bulk Map](kv-k210.case.json) | no | http |
| [Pair bulk JSON values with their annotations](kv-k211.case.json) | no | http |
| [Delete only the selected bulk subset](kv-k212.case.json) | no | http |
| [Order an international catalog by UTF-8 bytes](kv-k213.case.json) | no | http |
| [Match literal case-sensitive catalog prefixes](kv-k214.case.json) | no | http |
| [Terminate an exactly full final page](kv-k215.case.json) | no | http |
| [Resume keyset pagination after ordinary edits](kv-k216.case.json) | no | http |
| [Paginate a supplementary-character prefix](kv-k217.case.json) | no | http |
| [Isolate equal key names across namespaces](kv-k218.case.json) | no | http |
| [Clear prior expiration on permanent replacement](kv-k219.case.json) | no | http |
| [Join disjoint application result writes](kv-k220.case.json) | no | http |
| [kv](kv.case.json) | no | example |
| [opencode](opencode.case.json) | yes | N/A; see header |
| [pi](pi.case.json) | yes | N/A; see header |
| [queues](queues.case.json) | yes | example |
| [Round-trip a Unicode object with consistent head metadata](r2-i201.case.json) | no | http |
| [Respect binary body view boundaries during R2 conversion](r2-i202.case.json) | no | http |
| [Finish a finite streamed put across an empty chunk](r2-i203.case.json) | no | http |
| [Round-trip metadata and write only its HTTP fields](r2-i204.case.json) | no | http |
| [Replace body and metadata as one object revision](r2-i205.case.json) | no | http |
| [Cancel one R2 reader without disturbing other readers](r2-i206.case.json) | no | http |
| [Distinguish a conditional metadata-only read from a miss](r2-i207.case.json) | no | http |
| [Preserve successful compare-and-set state after stale refusal](r2-i208.case.json) | no | http |
| [Honor create-only writes across condition representations](r2-i209.case.json) | no | http |
| [Translate structured and header byte ranges correctly](r2-i210.case.json) | no | http |
| [Enumerate a finite R2 prefix through opaque cursors](r2-i211.case.json) | no | http |
| [Roll up child directories without exposing their objects](r2-i212.case.json) | no | http |
| [Project only requested listing metadata](r2-i213.case.json) | no | http |
| [Keep identical logical keys isolated between buckets](r2-i214.case.json) | no | http |
| [Delete an owned subset idempotently](r2-i215.case.json) | no | http |
| [Preserve empty and Unicode path segments in object keys](r2-i216.case.json) | no | http |
| [Retain verified checksum bytes and named JSON digests](r2-i217.case.json) | no | http |
| [Publish a completed single-final-part multipart object](r2-i218.case.json) | no | http |
| [Abort uncommitted replacement while keeping the prior object](r2-i219.case.json) | no | http |
| [Resume an owned multipart upload within one live request](r2-i220.case.json) | no | http |
| [r2](r2.case.json) | no | example |
| [sandbox](sandbox.case.json) | yes | N/A; see header |
| [static assets](static-assets.case.json) | yes | example |
| [vectordb](vectordb.case.json) | no | example |
| [workflow](workflow.case.json) | yes | example |
