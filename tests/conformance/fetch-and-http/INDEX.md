# fetch-and-http

144 cases; 144 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [A failed first write prevents subsequent remote writes](a-failed-first-write-prevents-subsequent-remote-writes.case.json) | no | topology |
| [A late error after an observed prefix is swallowed or poisons other pending streams and future transfers.](a-late-error-after-an-observed-prefix-is-swallowed-or-poisons-other-pending-streams-and-future-trans.case.json) | no | topology |
| [A returned WritableStream loses a remote failure at terminal close or conflates failure with three other saturated sinks.](a-returned-writable-stream-loses-a-remote-failure-at-terminal-close-or-conflates-failure-with-three.case.json) | no | topology |
| [Abort a buffered pack digest and reuse the digest path](abort-a-buffered-pack-digest-and-reuse-the-digest-path.case.json) | no | topology |
| [Abort a native transform when its source fails before any bytes](abort-a-native-transform-when-its-source-fails-before-any-bytes.case.json) | no | topology |
| [Abort accepted request before response head](abort-accepted-request-before-response-head.case.json) | no | topology |
| [Abort an unflushed raw exporter and immediately recover](abort-an-unflushed-raw-exporter-and-immediately-recover.case.json) | no | topology |
| [Abort before HTTP dispatch with live sibling](abort-before-http-dispatch-with-live-sibling.case.json) | no | topology |
| [Abort before writer acquisition reaches remote sink once](abort-before-writer-acquisition-reaches-remote-sink-once.case.json) | no | topology |
| [Abort while intermediate redirect head is held](abort-while-intermediate-redirect-head-is-held.case.json) | no | topology |
| [Accumulate JSON request bodies in object storage](accumulate-json-request-bodies-in-object-storage.case.json) | yes | http |
| [Acknowledge upload through no-content response](acknowledge-upload-through-no-content-response.case.json) | no | topology |
| [Advance a small upload beside host-body relay](advance-a-small-upload-beside-host-body-relay.case.json) | no | topology |
| [An abandoned upload leaves its source live or propagates receiver failure into five sibling uploads.](an-abandoned-upload-leaves-its-source-live-or-propagates-receiver-failure-into-five-sibling-uploads.case.json) | no | topology |
| [Blocked download result streams prevent independent upload argument streams from completing on the same owner connection.](blocked-download-result-streams-prevent-independent-upload-argument-streams-from-completing-on-the-s.case.json) | no | topology |
| [Snapshot mixed Blob parts with a visible DataView window](body-form-y201.case.json) | no | http |
| [Keep Blob read-result buffers independent from immutable storage](body-form-y202.case.json) | no | http |
| [Apply byte-relative Blob slicing without inheriting MIME type](body-form-y203.case.json) | no | http |
| [Cancel one independently opened Blob stream while consuming another](body-form-y204.case.json) | no | http |
| [Convert Blob and File form entries while preserving file metadata](body-form-y205.case.json) | no | http |
| [Replace mixed duplicate form entries with one renamed binary File](body-form-y206.case.json) | no | http |
| [Convert a consumed binary Response into a reusable typed Blob](body-form-y207.case.json) | no | http |
| [Extract a coherent multipart request snapshot before later form edits](body-form-y208.case.json) | no | http |
| [Parse binary multipart file parts without UTF-8 replacement](body-form-y209.case.json) | no | http |
| [Preserve mid-line multipart boundary lookalikes in file content](body-form-y210.case.json) | no | http |
| [Read multipart field names when filename parameter comes first](body-form-y211.case.json) | no | http |
| [Normalize multiline form values on the multipart wire](body-form-y212.case.json) | no | http |
| [Dispatch a URLSearchParams BodyInit through its inferred form media type](body-form-y213.case.json) | no | http |
| [Transfer inherited Request bodies while leaving overridden sources unused](body-form-y214.case.json) | no | http |
| [Preserve cloned Response metadata while isolating mutable consumer results](body-form-y215.case.json) | no | http |
| [Snapshot JSON response data while retaining response initialization](body-form-y216.case.json) | no | http |
| [Keep absent bodies distinct from empty streams and never disturbed](body-form-y217.case.json) | no | http |
| [Reflect direct body-reader disturbance in Response.bodyUsed](body-form-y218.case.json) | no | http |
| [Infer text BodyInit media types while preserving an explicit override](body-form-y219.case.json) | no | http |
| [Clone a valid finite streaming Response and settle both bodies](body-form-y220.case.json) | no | http |
| [BYOB transitions between short source chunks without byte loss](byob-transitions-between-short-source-chunks-without-byte-loss.case.json) | no | topology |
| [Cancel a gzip decoder after a decoded prefix is observed](cancel-a-gzip-decoder-after-a-decoded-prefix-is-observed.case.json) | no | topology |
| [Cancel manual body before explicit handoff](cancel-manual-body-before-explicit-handoff.case.json) | no | topology |
| [Cancel one host tee consumer before tail](cancel-one-host-tee-consumer-before-tail.case.json) | no | topology |
| [Cancel one response reader and resume sibling](cancel-one-response-reader-and-resume-sibling.case.json) | no | topology |
| [Cancel resolves a pending read as done and reaches source](cancel-resolves-a-pending-read-as-done-and-reaches-source.case.json) | no | topology |
| [Canceling one tee branch preserves remaining consumer](canceling-one-tee-branch-preserves-remaining-consumer.case.json) | no | topology |
| [Cancellation after EOF does not reopen or cancel completed source](cancellation-after-eof-does-not-reopen-or-cancel-completed-source.case.json) | no | topology |
| [Cancelling two pending readers leaks their producers, emits post-cancel frames, or cancels unrelated streams.](cancelling-two-pending-readers-leaks-their-producers-emits-post-cancel-frames-or-cancels-unrelated-s.case.json) | no | topology |
| [Carry303 method rewrite through later307](carry303-method-rewrite-through-later307.case.json) | no | topology |
| [Clone streaming request into separately committed uploads](clone-streaming-request-into-separately-committed-uploads.case.json) | no | topology |
| [Close a buffered digest after a peer decoder poisons and recovers](close-a-buffered-digest-after-a-peer-decoder-poisons-and-recovers.case.json) | no | topology |
| [Complete upload while response body held](complete-upload-while-response-body-held.case.json) | no | topology |
| [Decode held HTTP text beside binary control](decode-held-http-text-beside-binary-control.case.json) | no | topology |
| [Delay a valid gzip trailer while a pack digest finishes](delay-a-valid-gzip-trailer-while-a-pack-digest-finishes.case.json) | no | topology |
| [Dispose an unlocked buffered DigestStream while another digest closes](dispose-an-unlocked-buffered-digest-stream-while-another-digest-closes.case.json) | no | topology |
| [Drain decoded output only after an independent exporter finishes](drain-decoded-output-only-after-an-independent-exporter-finishes.case.json) | no | topology |
| [Drain small response around a retained reader](drain-small-response-around-a-retained-reader.case.json) | no | topology |
| [Duplicate host HTTP body into delayed consumer](duplicate-host-http-body-into-delayed-consumer.case.json) | no | topology |
| [Echo HTTP request URL](echo-http-request-url.case.json) | yes | http |
| [Empty BYOB stream returns terminal zero-length view](empty-byob-stream-returns-terminal-zero-length-view.case.json) | no | topology |
| [Empty remote readable terminates once and retains stable EOF](empty-remote-readable-terminates-once-and-retains-stable-eof.case.json) | no | topology |
| [End follow at302 without Location](end-follow-at302-without-location.case.json) | no | topology |
| [Fail relayed source after sink observes prefix](fail-relayed-source-after-sink-observes-prefix.case.json) | no | topology |
| [Fail source body before forwarded upload data](fail-source-body-before-forwarded-upload-data.case.json) | no | topology |
| [Finish distinct DigestStream payloads in reverse request order](finish-distinct-digest-stream-payloads-in-reverse-request-order.case.json) | no | topology |
| [Forward response-rewrapped host body incrementally](forward-response-rewrapped-host-body-incrementally.case.json) | no | topology |
| [Handoff a compressor writer lock without widening offset views](handoff-a-compressor-writer-lock-without-widening-offset-views.case.json) | no | topology |
| [Enumerate header records in observable order](headers-v201.case.json) | no | http |
| [Prefer custom iterable over header record fields](headers-v202.case.json) | no | http |
| [Honor overridden iterator on Headers input](headers-v203.case.json) | no | http |
| [Coerce ordinary header arguments in order](headers-v204.case.json) | no | http |
| [Compact duplicate header values after cached iteration](headers-v205.case.json) | no | http |
| [Delete repeated fields without losing empty survivors](headers-v206.case.json) | no | http |
| [Keep iterator views aligned across split cookie fields](headers-v207.case.json) | no | http |
| [Observe insertion after a live iterator cursor](headers-v208.case.json) | no | http |
| [Apply deletion shifts to a live iterator](headers-v209.case.json) | no | http |
| [Refresh an unvisited iterator value after mutations](headers-v210.case.json) | no | http |
| [Preserve callback receiver during finite live traversal](headers-v211.case.json) | no | http |
| [Detach returned iteration and cookie arrays](headers-v212.case.json) | no | http |
| [Snapshot a reused iterable tuple at each yield](headers-v213.case.json) | no | http |
| [Drain a finite response producer before cache put resolves](headers-v214.case.json) | no | http |
| [Consume a cache clone while preserving its original body](headers-v215.case.json) | no | http |
| [Preserve bodyless response state through cache put](headers-v217.case.json) | no | http |
| [Complete independent named and default cache consumers](headers-v218.case.json) | no | http |
| [Independently stalled download streams are cross-wired or coupled when completion order differs from creation order.](independently-stalled-download-streams-are-cross-wired-or-coupled-when-completion-order-differs-from.case.json) | no | topology |
| [Isolate deferred gzip checksum corruption from a healthy native peer](isolate-deferred-gzip-checksum-corruption-from-a-healthy-native-peer.case.json) | no | topology |
| [Keep a decoded tee branch complete after cancelling its sibling](keep-a-decoded-tee-branch-complete-after-cancelling-its-sibling.case.json) | no | topology |
| [Keep an imported public HMAC key independent of caller-buffer mutation](keep-an-imported-public-hmac-key-independent-of-caller-buffer-mutation.case.json) | no | topology |
| [Keep overlapping manual and follow choices independent](keep-overlapping-manual-and-follow-choices-independent.case.json) | no | topology |
| [Local pipeTo sink failure cancels remote source](local-pipe-to-sink-failure-cancels-remote-source.case.json) | no | topology |
| [Match buffered arrayBuffer with gated streamed body](match-buffered-array-buffer-with-gated-streamed-body.case.json) | no | topology |
| [Multiple pending reads resolve in FIFO order before EOF](multiple-pending-reads-resolve-in-fifo-order-before-eof.case.json) | no | topology |
| [One-byte BYOB reads preserve residual data from a larger chunk](one-byte-byob-reads-preserve-residual-data-from-a-larger-chunk.case.json) | no | topology |
| [Keep sink writable after pipe EOF](pipe-cleanup-s201.case.json) | no | http |
| [Reuse sink after source error](pipe-cleanup-s202.case.json) | no | http |
| [Drain source after sink error](pipe-cleanup-s203.case.json) | no | http |
| [Reuse both resources after signal shutdown](pipe-cleanup-s204.case.json) | no | http |
| [Join write and both signal cleanup actions](pipe-cleanup-s205.case.json) | no | http |
| [Hold pipe completion through sink close](pipe-cleanup-s206.case.json) | no | http |
| [Preserve zero pre-abort reason without transfer](pipe-cleanup-s207.case.json) | no | http |
| [Join pre-aborted asynchronous cleanup](pipe-cleanup-s208.case.json) | no | http |
| [Surface cancellation failure after signal abort](pipe-cleanup-s209.case.json) | no | http |
| [pipeTo drains a remote readable into a local writable](pipe-to-drains-a-remote-readable-into-a-local-writable.case.json) | no | topology |
| [Poison a decoder after independently observed prefix delivery](poison-a-decoder-after-independently-observed-prefix-delivery.case.json) | no | topology |
| [Poison one decoder while preserving a second live decoder in the same request](poison-one-decoder-while-preserving-a-second-live-decoder-in-the-same-request.case.json) | no | topology |
| [Preserve committed effect after response abandonment](preserve-committed-effect-after-response-abandonment.case.json) | no | topology |
| [Preserve declared length through streamed response](preserve-declared-length-through-streamed-response.case.json) | no | topology |
| [Preserve finite PUT body at moved endpoint](preserve-finite-put-body-at-moved-endpoint.case.json) | no | topology |
| [Preserve HEAD across303 without payload](preserve-head-across303-without-payload.case.json) | no | topology |
| [Propagate AbortSignal through an open source-to-native pipe](propagate-abort-signal-through-an-open-source-to-native-pipe.case.json) | no | topology |
| [Queued close cannot overtake delayed writes](queued-close-cannot-overtake-delayed-writes.case.json) | no | topology |
| [Reader lock release and reacquisition preserve remaining remote data](reader-lock-release-and-reacquisition-preserve-remaining-remote-data.case.json) | no | topology |
| [Recover from a non-byte chunk after a valid exporter prefix](recover-from-a-non-byte-chunk-after-a-valid-exporter-prefix.case.json) | no | topology |
| [Refuse locked host body while writer recovers](refuse-locked-host-body-while-writer-recovers.case.json) | no | topology |
| [Reject a pack digest after the accepted header source fails](reject-a-pack-digest-after-the-accepted-header-source-fails.case.json) | no | topology |
| [Reject a pending native compression read on consumer cancellation](reject-a-pending-native-compression-read-on-consumer-cancellation.case.json) | no | topology |
| [Reject incomplete upload beside healthy writer](reject-incomplete-upload-beside-healthy-writer.case.json) | no | topology |
| [Reject missing gzip size trailer and recover the decoder path](reject-missing-gzip-size-trailer-and-recover-the-decoder-path.case.json) | no | topology |
| [Reject trailing bytes after a complete gzip member before close](reject-trailing-bytes-after-a-complete-gzip-member-before-close.case.json) | no | topology |
| [Release held response heads out of order](release-held-response-heads-out-of-order.case.json) | no | topology |
| [Remote writable closes correctly without writes](remote-writable-closes-correctly-without-writes.case.json) | no | topology |
| [Report final URL and redirected metadata](report-final-url-and-redirected-metadata.case.json) | no | topology |
| [Resolve relative redirect chain by current URL](resolve-relative-redirect-chain-by-current-url.case.json) | no | topology |
| [Keep cloned raw body chunks independent after sibling mutation](response-clone-chunk-y301.case.json) | no | http |
| [Resume a partially written native gzip encoder after a separate raw exporter finishes](resume-a-partially-written-native-gzip-encoder-after-a-separate-raw-exporter-finishes.case.json) | no | topology |
| [Resume an encoder after separate crypto validation failures and recovery](resume-an-encoder-after-separate-crypto-validation-failures-and-recovery.case.json) | no | topology |
| [Resume recipient-held relay after source release](resume-recipient-held-relay-after-source-release.case.json) | no | topology |
| [Retain manual redirect body during sibling upload](retain-manual-redirect-body-during-sibling-upload.case.json) | no | topology |
| [Retain prefix when HTTP response later errors](retain-prefix-when-http-response-later-errors.case.json) | no | topology |
| [Rewrite buffered POST after302](rewrite-buffered-post-after302.case.json) | no | topology |
| [Send offset view beside held application commit](send-offset-view-beside-held-application-commit.case.json) | no | topology |
| [Separate discarded redirect bodies from final stream](separate-discarded-redirect-bodies-from-final-stream.case.json) | no | topology |
| [Share abort controller across accepted requests](share-abort-controller-across-accepted-requests.case.json) | no | topology |
| [Sink close failure rejects both close and writer.closed](sink-close-failure-rejects-both-close-and-writer-closed.case.json) | no | topology |
| [Six native stream arguments waiting in receivers starve unrelated metadata RPCs or corrupt their resumed bytes.](six-native-stream-arguments-waiting-in-receivers-starve-unrelated-metadata-rpcs-or-corrupt-their-res.case.json) | no | topology |
| [Source error preserves already delivered prefix without becoming EOF](source-error-preserves-already-delivered-prefix-without-becoming-eof.case.json) | no | topology |
| [Source exception before data remains an error on repeated reads](source-exception-before-data-remains-an-error-on-repeated-reads.case.json) | no | topology |
| [Renew weighted writer readiness epochs](stream-backpressure-s301.case.json) | no | http |
| [Admit queued writes after successful start](stream-backpressure-s302.case.json) | no | http |
| [Lift ready while close is queued](stream-backpressure-s303.case.json) | no | http |
| [Gate transforms on readable demand](stream-backpressure-s304.case.json) | no | http |
| [Own asynchronous flush tail through EOF](stream-backpressure-s305.case.json) | no | http |
| [Admit readable pulls by weighted capacity](stream-backpressure-s306.case.json) | no | http |
| [Subarray RPC transfer excludes backing-buffer sentinel bytes](subarray-rpc-transfer-excludes-backing-buffer-sentinel-bytes.case.json) | no | topology |
| [Suppress HEAD payload beside active GET](suppress-head-payload-beside-active-get.case.json) | no | topology |
| [Tee gives both concurrent consumers identical remote bytes](tee-gives-both-concurrent-consumers-identical-remote-bytes.case.json) | no | topology |
| [Three slow tee consumers prevent fast branches draining, or late branch cancellation incorrectly cancels already-completed sources.](three-slow-tee-consumers-prevent-fast-branches-draining-or-late-branch-cancellation-incorrectly-canc.case.json) | no | topology |
| [Writer reacquisition preserves remote sink order](writer-reacquisition-preserves-remote-sink-order.case.json) | no | topology |
