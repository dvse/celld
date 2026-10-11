#!/usr/bin/env python3
"""Serialize 26 explicitly authored HTTP schedules. No parameter grid or runtime work."""
import hashlib, json, pathlib
HERE=pathlib.Path(__file__).resolve().parent
PROJECT=pathlib.Path('/workspace/shared/celld-os-project')
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
# Each tuple is an independently specified state transition, never a generated size/seed variant.
# ID, intent, failure hypothesis, specific precondition, ordered trace, stress, oracle, distinction.
ROWS=[
('H001','Advance a small upload beside host-body relay','A host-backed HTTP upload is collected before local DO dispatch or monopolizes unrelated ingress','Source emits 4096 logical bytes then holds; sink has identical expected 32768-byte document',
 ['Start HTTP source-to-sink relay','Observe at least4096 sink bytes while source tail remains held','Complete small upload and prove sink effect0','Release source tail; await exact sink receipt and effect1'],
 'One open download and its forwarded upload overlap an independently completed upload',
 'Sink receives bytes before source EOF, small effect1 precedes tail release, sink effect0 before release and exact32768-byte SHA256/effect1 afterward',
 'HTTP registry transfer -> direct network -> local DO.fetch ingress; S/B stream arguments use RPC stream capabilities instead'),
('H002','Complete upload while response body held','Retaining a partially consumed HTTP response blocks a fresh opposite-direction upload','Download has8192-byte application prefix and held tail; independent upload configured',
 ['Read at least8192 response bytes','Complete independent upload and exact effect','Release response tail','Drain original response with exact bytes and stable EOF'],
 'One response reader stays live across independent complete upload',
 'Upload receipt/effect1 before response release; response equals32768 expected bytes followed by repeated done',
 'HTTP request/response direction coupling with reader-owned response; H001 instead transfers ownership into a new request'),
('H003','Release held response heads out of order','Pending HTTP response heads exchange metadata/body identity or head-of-line block a third request','First and second have separate header gates and distinct MIME types; third is buffered',
 ['Dispatch first and second without awaiting headers','Observe both recipient entries','Finish third response','Release second then first, validating each response metadata and bytes'],
 'Two unresolved response-head promises and a completed third request',
 'Third completes before either release; each held result has correct name/root/run/isolate, MIME type and exact body',
 'Pre-header HTTP metadata association; B009 gates post-RPC stream prefixes, not HTTP heads'),
('H004','Drain small response around a retained reader','An open response reader prevents another response from reaching terminal state','Slow body has4096-byte prefix and held tail; independent313-byte body is buffered',
 ['Read slow logical prefix and retain reader','Drain independent body','Snapshot proves independent EOF while slow remains active with4096 produced bytes','Release and drain slow response'],
 'Concurrent response-body ownership without a second request-body producer',
 'Independent exact313 bytes and server EOF while slow active; slow exact65536 bytes after release',
 'Explicit same-direction HTTP body completion behind held tail; H002 tests opposite-direction request body'),
('H005','Resume recipient-held relay after source release','A locally held DO request reader loses bytes or blocks independent traffic when source resumes','Source4096-byte prefix; recipient pauses after first4096 logical bytes on its own gate',
 ['Relay source into recipient','Observe recipient prefix','Release source tail while keeping recipient consume gate closed','Complete independent probe; assert sink effect0','Release recipient; require exact receipt/effect1'],
 'Two independently controlled producer/consumer gates with small intervening HTTP response',
 'Probe exact111 bytes while sink effect0; released sink has exact complete archive and one effect; no write-ack or buffer-capacity timing asserted',
 'Receiver DO.fetch input-reader gate differs from H001 producer-only gate'),
('H006','Duplicate host HTTP body into delayed consumer','Native HTTP tee corrupts one branch while unrelated upload progresses','Single49153-byte network response; two host HTTP tee branches',
 ['Tee response and begin left drain','Complete probe upload while right unread','Start right drain','Compare both complete branch bodies and probe effect'],
 'Two native HTTP registry branches, one initially delayed, overlap upload',
 'Both exact49153-byte bodies reach stable EOF; probe effect1; no branch chunk shape or promised fast-branch completion before right starts',
 'Native HTTP registry tee rather than S017/B016 RPC readable tee'),
('H007','Cancel one host tee consumer before tail','Canceling a native HTTP tee branch destroys the surviving branch or unrelated request','4096-byte source prefix plus gated tail; tee uses host registry',
 ['Tee response and cancel right branch','Read left logical prefix','Complete independent upload','Release source tail and drain left','Await canceled-branch settlement'],
 'One canceled HTTP tee branch beside surviving gated branch and upload',
 'Left exact32768 bytes/stable EOF, cancellation settles, probe receipt/effect1',
 'HTTP tee cancellation and body registry are distinct from S018 RPC stream cancel'),
('H008','Clone streaming request into separately committed uploads','Request.clone host-body tee aliases destination effects or loses one copy','Source12289 bytes; left upload commit held, right upload unheld',
 ['Wrap HTTP response body in Request then clone','Send original and clone bodies to distinct configured operations','Await right receipt and effect1 while left effect0','Release left commit; await left exact receipt/effect1'],
 'Two HTTP upload owners from one Request.clone with asymmetric commit gates',
 'Both recipients receive complete identical12289 bytes exactly once; right can commit while left cannot',
 'Request.clone invokes host tee then transfers both branches into request-body owners, unlike response consumers H006'),
('H009','Forward response-rewrapped host body incrementally','Wrapping a host body in a new Response loses native stream identity and causes fallback buffering','Source4096-byte prefix and gated tail; Response wrapper has replaced MIME metadata',
 ['Create Response(source.body)','Upload rewrapped body to sink','Observe sink prefix before source tail release','Drain unrelated probe','Release tail and verify sink receipt/effect'],
 'Response wrapper adoption plus live host-body transfer and independent probe',
 'Sink consumes at least4096 bytes before tail release; sink exact32768-byte receipt/effect1; probe exact79 bytes',
 'Explicit response-constructor host-body adoption seam, unlike H001 direct body transfer'),
('H010','Send offset view beside held application commit','Buffered HTTP request transfer sends sentinel bytes outside an ArrayBufferView','8193-byte visible subarray embedded at offset7 in251-filled backing array; sink commit held',
 ['Post only backing.subarray(7,8200)','Observe complete recipient input before commit','Complete peer upload','Release slice commit and verify both effects'],
 'Buffered typed-view request conversion overlaps independent write',
 'Sink exact8193 visible bytes/hash, no outer sentinels; both effects1 and peer completes before slice commit',
 'HTTP byte fallback ArrayBufferView seam differs from S005 RPC subarray codec'),
('H011','Decode held HTTP text beside binary control','Network-body text consumption decodes binary payload incorrectly or associates wrong response','Text MIME request headers held; binary control has identical invalid-UTF8 byte pattern',
 ['Dispatch text response and observe entry','Drain binary control before text headers released','Release text headers','Consume Response.text and inspect bodyUsed'],
 'Held text response head and binary control use different body consumers',
 'Binary exact16391 bytes; text equals TextDecoder replacement decoding of same bytes; bodyUsed true',
 'HTTP Response.text body drain/decoding path, not RPC string codec'),
('H012','Match buffered arrayBuffer with gated streamed body','Buffered and streaming HTTP response representations disagree after partial consumption','Both responses contain24577 identical bytes; streamed form has4096 prefix and tail gate',
 ['Read streamed prefix','Consume buffered response via arrayBuffer while tail held','Compare buffered result with expected bytes','Release tail and compare complete streamed bytes with captured arrayBuffer'],
 'Buffered body consumer and retained streaming reader overlap',
 'Buffered exact24577 bytes and complete streamed bytes identical, stable streamed EOF',
 'Representation conversion parity and Response.arrayBuffer seam rather than same-consumer relay'),
('H013','Preserve declared length through streamed response','Content-Length metadata is lost or declared-body framing truncates gated response','Known32771-byte streamed body with explicit length; independent16387-byte unknown-length body',
 ['Open known-length response and verify header','Read known prefix','Drain unknown-length sibling','Release known tail and drain exact body'],
 'HTTP framing with known length versus sibling unknown length',
 'Content-Length32771 survives; each response has its own exact bytes and stable EOF; no connection-reuse claim',
 'HTTP declared response-body length is absent from RPC stream tests'),
('H014','Suppress HEAD payload beside active GET','HEAD accidentally produces body bytes or its no-body handling interferes with active GET','HEAD/GET refer to same49157-byte logical document; GET tail held',
 ['Read GET prefix','Send HEAD and check length/status','Verify empty client HEAD body and server outputBytes0/head terminal','Release and drain GET'],
 'Bodyless HEAD boundary overlaps a live GET stream',
 'HEAD200 with length49157 and zero payload; GET exact49157 bytes/stable EOF',
 'HTTP method-specific payload suppression not covered by stream terminal-only cases'),
('H015','Acknowledge upload through no-content response','204 response handling leaves uploaded bytes uncommitted or fabricates a body','Receiptless upload16384 bytes completes input before commit gate; independent document response',
 ['Start upload','Observe input EOF with commit held','Drain independent document and prove effect0','Release commit; consume204 and inspect exact input effect'],
 'Request body completes before bodyless response, interleaved with response traffic',
 '204 has empty body; recipient input EOF/hash exact and effect1; independent599-byte document exact',
 'No-content HTTP response after full input, unlike HEAD request suppression H014'),
('H016','Reject incomplete upload beside healthy writer','An ordinary409 early response becomes a success effect or poisons an unrelated upload','Host source tail held after4096 bytes; recipient rejects without consuming request body',
 ['Forward source to rejecting endpoint','Observe reject handler entry before releasing source tail','Complete healthy upload','Release source tail and require409 body','Assert rejected effect0 and healthy effect1'],
 'Recipient request cancellation plus non2xx response overlaps valid upload',
 '409 with exact31-byte rejection body; reject effect0; healthy exact receipt/effect1; no disconnect rollback claim',
 'HTTP early non2xx response semantics instead of RPC consumer exception B014'),
('H017','Abort before HTTP dispatch with live sibling','Already-aborted signal still dispatches request bytes or cancels unrelated response','Undispatched upload configured; independent download prefix retained',
 ['Read sibling prefix','Abort controller before calling upload','Require upload rejection','Inspect never.entered0/effect0','Release and drain sibling'],
 'Pre-dispatch abort beside a live response stream',
 'Aborted operation never enters recipient; sibling exact bytes/stable EOF',
 'Fetch pre-dispatch signal branch distinct from remote body cancellation'),
('H018','Abort accepted request before response head','Cancellable fetch waiting for headers fails to reject or interferes with another upload','Recipient header gate prevents input consumption and response release',
 ['Start signaled upload','Observe accepted recipient entry','Abort and require rejection','Explicitly stop held application operation','Complete independent upload and inspect effects'],
 'Abort races held HTTP response head; application stop separately prevents effect',
 'Caller rejection, stopped operation effect0, independent exact receipt/effect1; abort alone is not claimed to roll back writes',
 'Native request cancellation window after entry but before response head, unlike H017 pre-dispatch'),
('H019','Cancel one response reader and resume sibling','Consumer cancellation of one HTTP body ends the other body or fails to terminate its own reader','Two response prefixes observed with independent held tails',
 ['Read both logical prefixes','Cancel abandoned reader and verify repeated read done','Stop abandoned application producer','Release live tail and drain survivor'],
 'Selective body cancellation after response head among two active streams',
 'Canceled reader terminal done, observed prefix retained, survivor exact full bytes/stable EOF',
 'Registered HTTP body cancellation differs from pre-head AbortSignal and B012 RPC stream cancellation'),
('H020','Fail source body before forwarded upload data','A zero-byte HTTP source failure becomes normal EOF or a sink effect','Source errorBefore gate and target upload configured; independent healthy writer',
 ['Start source relay','Observe source entry','Complete healthy upload','Release source error gate','Require relay rejection and inspect source/sink witnesses'],
 'No-data response-body failure during attempted host-body request transfer',
 'Source outputTerminal error/outputBytes0, sink effect0, healthy effect1; sink entry is not required because response/network error may precede it',
 'HTTP response-to-request error propagation at zero-byte boundary; S006 reads RPC stream directly'),
('H021','Fail relayed source after sink observes prefix','HTTP source error after accepted upload bytes becomes complete request or commits partial payload','Source4096-byte prefix and fail gate; sink expects32768 bytes',
 ['Start relay','Observe sink at least4096 bytes before fault','Complete healthy writer','Release source failure','Require relay rejection and inspect sink/source'],
 'Already-received request prefix followed by upstream HTTP body error',
 'Source error, sink inputBytes below32768/effect0, healthy effect1; no exact network error text asserted',
 'HTTP failure after DO request input exposure, unlike zero-data H020 and direct RPC readable S007'),
('H022','Fail local stream fallback before dispatch','Ordinary JS stream fallback dispatches its prefix before full body conversion succeeds','Local stream emits4096 bytes then waits on local error gate; sibling response tail held',
 ['Start upload with ordinary JS stream','Read independent HTTP response prefix','Release local producer error gate','Require upload rejection and never.entered0/effect0','Release and drain sibling'],
 'Local byte-fallback collection failure beside retained network response',
 'No partial request dispatch/effect; live HTTP response exact bytes; error comes from deliberate local producer',
 'Frozen source explicitly buffers unbranded JS streams, unlike incremental host response H001'),
('H023','Refuse locked host body while writer recovers','Transferring a host body with a held reader double-consumes or dispatches it','Host response has data; caller acquires and retains reader before attempted upload',
 ['Read source once while keeping reader lock','Attempt upload with same locked source body','Require rejection','Complete healthy upload','Inspect never.entered0/effect0 then cancel/release original reader'],
 'Competing reader/transfer ownership at fetch request construction',
 'Locked-body upload rejected before recipient entry, healthy receipt/effect1, source reader explicitly cleaned',
 'Host HTTP transfer lock gate, unlike ordinary RPC reader lock tests'),
('H024','Retain prefix when HTTP response later errors','Partial response error is converted into clean EOF or erases bytes already delivered','Broken response produces4096 bytes before error gate; healthy response buffered',
 ['Read broken prefix and validate exact bytes','Drain healthy response','Release error gate','Require remaining read rejection and source error witness'],
 'One direct consumer sees body error after successful sibling response',
 'Exact4096-byte prefix, subsequent rejection rather than EOF, server error terminal, healthy exact1025 bytes',
 'Direct HTTP response read failure instead of H021 subsequent request transfer and S007 RPC source'),
('H025','Share abort controller across accepted requests','One signal cancels only one registered HTTP request or leaks into an unrelated request','Two separately gated response-head requests share controller; third upload does not',
 ['Start left/right requests under one controller','Observe both recipient entries','Abort controller; require two rejections','Stop both application producers','Complete unrelated upload'],
 'One-to-many AbortSignal listener fanout over two host dispatch IDs',
 'Both pending requests reject, unrelated exact receipt/effect1, both owned producers stopped',
 'Signal fanout association differs from one-request cancellation H018'),
('H026','Preserve committed effect after response abandonment','Aborting caller after effect but before response silently undoes or repeats the application mutation','Upload exact6143-byte input committed; reply gate holds response head',
 ['Start signaled upload','Observe effect1 and exact completed input while reply held','Abort caller and require rejection','Complete peer upload; inspect original effect1','Release reply and wait handler inactive; recheck effect1'],
 'Ambiguous caller outcome after known application effect, alongside successful peer',
 'Original input EOF/hash exact and effect remains1 before/after reply release; peer effect1; no durable storage or crash-recovery claim',
 'Volatile HTTP request outcome ambiguity without D015 durable replay/restart scenario')
]
COMMON_PRE=[
 'Independent review of exact wave/source/profile hashes and explicit parent exclusive run slot',
 'Already-running owned disposable bounded fleet, at most2 runtimes; actual PID/boot/executable and enforced memory/PID/CPU/wall bounds witnessed',
 'Fresh caller/recipient DO names on independently witnessed runtime processes and distinct root/isolate IDs',
 'Recipient DO placed locally to fixed private HTTP ingress192.168.77.1:18080; no cross-node incremental request premise',
 'Native fetch/ReadableStream/AbortController/crypto APIs, matching profile/identity and empty recipient operation journal; missing prerequisite is typed BLOCKED before traceEntered'
]
CLEANUP=[
 'Keep every coordinator case within active DO fetch; release all local gates, abort owned outstanding requests and cancel/release owned readers and branches',
 'Recipient cleanup marks all operations stopped before releasing gates; cancel inputs, error unfinished outputs, join entered operations and require zero active/readers/controllers',
 'Join caller task outcomes and verify no live request/reader/pending task; terminal receipt correlates run/root/isolate',
 'Every run requires separate supervisor evidence for bounded destruction/reaping of only owned fleet, sockets and fresh case storage; semantic PASS alone remains BLOCKED until teardown receipt'
]
rows=[]
for ident,intent,hypothesis,pre,trace,stress,oracle,distinction in ROWS:
 rows.append({'id':ident,'title':intent,'intent':intent,'failure_hypothesis':hypothesis,'preconditions':[pre,*COMMON_PRE],'trace':trace,'stress':{'schedule':stress,'bounded':True,'logical_payload_bytes_max':4194304,'coordinator_http_max':6,'fixture_operations_max':24,'read_operations_per_body_max':262144,'wall_seconds_max':30},'oracle':oracle,'cleanup':CLEANUP,'distinctness':distinction,'implementation':'cases.js:'+ident,'test_function':ident,'layer':'real-process-RPC','transport':'ordinary HTTP direct-network and local DO.fetch body seams','layer_limits':'Requires two observed native processes but does not claim cross-VM isolation, OS workflow, Git correctness, throughput, durability or tenant security','classification':'bounded-http-concurrent-failure','profile':'profile.json','authored':True,'reviewed':False,'executable_source_implementation':True,'run':False,'passed':False,'status':'NOT_RUN'})
(HERE/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
manifest_path=PROJECT/'deliverable/package/reports/final/runtime-manifest.json'
frozen=json.loads(manifest_path.read_text())
specs=[
 ('crates/celld/js/harness.js','139-173,214-243,331-371,500-537,586-712,5738-5805,12028-12150','HTTP host-body reader/tee, Request.clone, buffered vs streamed conversions, locked transfer, abort-before-dispatch, ordinary JS fallback, DO local stream forwarding and native response bridge'),
 ('crates/celld/js.rs','8840-8905,9100-9415,9478-9620,11646-11684,11800-11835','Native body claims, direct reqwest streaming/cancellable response-head window, tee/read/cancel, bounded queue response write acknowledgement is not downstream read acknowledgement'),
 ('crates/celld/http_streams.rs','1830-1965 and native tee implementation','Host source transfer/read terminal and cancellation; registry read/writer ownership and bounded branch queues'),
 ('crates/celld/main.rs','1768-1889','Ingress body declaration/threshold selects held bytes vs host stream; body-less and small known-length inputs collect; unknown-length relays remain incremental'),
 ('crates/celld/engine_api.rs','RequestBody and HttpResponse declarations','Native HTTP request/response representations; not RPC returned capability transport')
]
sources=[]
for rel,lines,contract in specs:
 path=PROJECT/'deliverable/patch-check-final'/rel;digest=sha(path);key='celld/'+rel
 assert digest==frozen['source_hashes'][key],f'Frozen source changed: {path}'
 sources.append({'path':str(path),'manifest_key':key,'sha256':digest,'lines':lines,'contract':contract})
candidate=PROJECT/'artifacts/do-visibility-candidate'
comparative=[{'path':str(candidate/name),'sha256':sha(candidate/name)} for name in ['source-manifest.json','build-manifest.json','from-648e17.patch']]
pins={'runtime_manifest':str(manifest_path),'runtime_manifest_sha256':sha(manifest_path),'binary_sha256':frozen['binary_sha256'],'celld_commit':frozen['base_commit'],'os_commit':frozen['os_commit'],'sources':sources,'candidate_context':{'files':comparative,'meaning':'Read-only comparison: candidate changes DO RPC method visibility; this HTTP-only wave remains pinned to frozen delivered binary and does not qualify candidate behavior.'}}
(HERE/'source-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
print(json.dumps({'authored':len(rows),'source_files_pinned':len(sources),'runtime_executed':False}))
