#!/usr/bin/env python3
"""Emit metadata for handwritten body/form traces. Never execute any JavaScript."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HARNESS = 'celld-os-project/celld/crates/celld/js/harness.js'
FETCH = 'https://fetch.spec.whatwg.org/'
FILE = 'https://w3c.github.io/FileAPI/'
FORM = 'https://xhr.spec.whatwg.org/#interface-formdata'
MULTIPART = 'https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#multipart-form-data'
ENTRY = 'https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#create-an-entry'

# Each row is a separate authored mechanism, not parameterized generated cases.
DESIGNS = [
  {
    'id':'Y201', 'title':'Snapshot mixed Blob parts with a visible DataView window',
    'mechanism':'Blob composition and immutable input-buffer ownership',
    'hypothesis':'Blob composition may copy the entire DataView backing buffer or retain caller-owned bytes after construction.',
    'relevance':'Workers compose binary upload payloads from strings, views, and nested Blob parts.',
    'trace':['Compose one Blob from UTF-8 text, offset DataView, nested binary Blob, and punctuation.', 'Mutate the backing Uint8Array after construction.', 'Assert fixed seven-byte value, byte length, and normalized type.'],
    'expected':'Exact bytes [195,169,65,66,0,255,33], size 7, type application/x-fixture.',
    'ranges':[(10596,10649)], 'contract':[FILE+'#constructorBlob'],
    'source_note':'Pinned Blob converts parts and then copies into owned storage. The mutation happens after construction, so no resizable-buffer/reentrancy behavior is claimed.',
    'distinctness':'C016 already covers Blob view bounds, copied input and MIME normalization, and S005/H010 cover offset transport. None of those primitives earn new credit here. The distinct mechanism is ordered heterogeneous composition of a UTF-8 scalar string, DataView window, nested Blob bytes and trailing scalar string into one exact byte sequence.'
  },
  {
    'id':'Y202', 'title':'Keep Blob read-result buffers independent from immutable storage',
    'mechanism':'Blob arrayBuffer and bytes result ownership with repeated reads',
    'hypothesis':'Blob read methods may expose storage aliases or consume an immutable value like a one-shot Body.',
    'relevance':'Workers inspect or modify locally returned byte arrays while reusing the source Blob.',
    'trace':['Read two ArrayBuffers from one four-byte Blob.', 'Mutate the first buffer and assert the second is unchanged.', 'Read and mutate bytes(), then read again and assert original bytes and size.'],
    'expected':'All independent unmodified views retain [1,2,3,4]; ArrayBuffer identities differ and Blob size remains four.',
    'ranges':[(10645,10652)], 'contract':[FILE+'#arraybuffer-method-algo',FILE+'#bytes-method-algo'],
    'source_note':'Pinned methods return slices of the underlying bytes; tests concern public values only.',
    'distinctness':'Output ownership after Blob reads, as opposed to constructor input ownership in Y201 or Body consumption in Y207.'
  },
  {
    'id':'Y203', 'title':'Apply byte-relative Blob slicing without inheriting MIME type',
    'mechanism':'Blob slice endpoint normalization and independent slice metadata',
    'hypothesis':'Negative, reversed, or clamped slice ranges may be handled as string positions or inherit the original type incorrectly.',
    'relevance':'Workers cut bounded file segments for previews or object-store parts.',
    'trace':['Slice a ten-byte ASCII Blob with negative start/end and a new type.', 'Assert selected bytes, length, and type.', 'Check reversed and clamped ranges, default slice type, and original value.'],
    'expected':'slice(-5,-1) is 5678, size four; reversed range is empty; clamped prefix is 012; omitted type is empty.',
    'ranges':[(10665,10674)], 'contract':[FILE+'#slice-method-algo'],
    'source_note':'Pinned slice normalizes endpoints and constructs a new Blob. Multiple range controls stay inside this single slicing design.',
    'distinctness':'Byte-range interpretation and slice metadata; no stream or transport slicing.'
  },
  {
    'id':'Y204', 'title':'Cancel one independently opened Blob stream while consuming another',
    'mechanism':'Independent Blob.stream reader lifecycles over one immutable value',
    'hypothesis':'Cancelling one stream returned by Blob.stream may poison shared Blob state or a separately opened stream.',
    'relevance':'Workers may abandon a preview stream while retaining a full-file consumer.',
    'trace':['Create two independent streams from one eleven-byte Blob.', 'Cancel the first stream without reading it.', 'Drain the other with a bounded reader; assert literal bytes, original text, and unchanged size.', 'Cancel/release tracked reader during fixture cleanup.'],
    'expected':'The retained stream and Blob text are independent; bytes spell independent and size is 11.',
    'ranges':[(10650,10660)], 'contract':[FILE+'#stream-method-algo'],
    'source_note':'Pinned stream eagerly copies bytes into a new closed stream for each call.',
    'distinctness':'This is not a tee or remote cancellation schedule: two independent Blob.stream calls allocate independent streams; S018/H007/X014 share a tee source.'
  },
  {
    'id':'Y205', 'title':'Convert Blob and File form entries while preserving file metadata',
    'mechanism':'FormData File identity and explicit filename conversion',
    'hypothesis':'Appending a File may gratuitously clone it or rename it in place; Blob conversion may omit the default filename or lose type/lastModified.',
    'relevance':'Workers assemble uploads with user files, renamed attachments, and generated Blobs.',
    'trace':['Append one File unchanged and once with a new filename.', 'Append an ordinary Blob without filename.', 'Assert File identity/renaming, bytes, fixed lastModified, type, original metadata, and default blob filename.'],
    'expected':'Unrenamed File is identical; renamed File is distinct upload.txt with unchanged bytes/type/123456789 lastModified; plain Blob is named blob.',
    'ranges':[(10677,10713),(10893,10914)], 'contract':[FORM,ENTRY,FILE+'#file-constructor'],
    'source_note':'Pinned form-value conversion returns a File directly without a filename override and creates a new File for overrides or Blobs. The lastModified assertion is specifically the source-supported same-file metadata carry-through at harness.js 10899-10906; HTML create-an-entry independently supports identity/rename/bytes but does not spell out lastModified. This supporting assertion earns no separate case credit.',
    'distinctness':'Entry-value type and metadata conversion, which URLSearchParams and remote-stream cases do not implement.'
  },
  {
    'id':'Y206', 'title':'Replace mixed duplicate form entries with one renamed binary File',
    'mechanism':'FormData ordered mixed-type replacement and File conversion',
    'hypothesis':'Replacing a repeated field by a Blob may leave duplicate entries, move its position, or lose the replacement filename or another File reference.',
    'relevance':'Workers replace draft attachment fields with final file bytes while preserving other form entries.',
    'trace':['Build interleaved duplicate asset fields containing a string and a File, plus another File and a tail string.', 'Set asset to a two-byte Blob with explicit filename.', 'Assert exact key order, single replacement, File type/name/bytes, and unchanged sibling values.'],
    'expected':'Keys asset,other,tail; asset is pair.bin with bytes [7,8]; unrelated File identity and tail string stay unchanged.',
    'ranges':[(10893,10907),(10915,10932)], 'contract':[FORM,ENTRY],
    'source_note':'Pinned set combines entry conversion with first-position replacement and reverse duplicate removal.',
    'distinctness':'Mixed File/string entry conversion and preservation is specific to FormData; U211 has string-only URL parameters and URL synchronization.'
  },
  {
    'id':'Y207', 'title':'Convert a consumed binary Response into a reusable typed Blob',
    'mechanism':'Body.blob byte materialization and MIME-to-Blob conversion',
    'hypothesis':'Body.blob may text-decode binary input, lose its MIME type, or fail to mark the one-shot Body consumed while returning an independently readable value.',
    'relevance':'Workers materialize binary responses into reusable file-like values.',
    'trace':['Construct a four-byte response with uppercase octet-stream media type.', 'Consume it through blob().', 'Assert Blob class, normalized type, exact bytes/size, Response bodyUsed, and repeatable Blob read.'],
    'expected':'Blob contains [0,255,128,65] and type application/octet-stream; Response is consumed but Blob reads are repeatable.',
    'ranges':[(330,359),(10596,10652)], 'contract':[FETCH+'#dom-body-blob',FILE],
    'source_note':'Pinned blob() uses arrayBuffer(), then Blob construction, without text decoding.',
    'distinctness':'One-shot Body to reusable Blob conversion, independent of Y202 Blob-to-buffer result ownership.'
  },
  {
    'id':'Y208', 'title':'Extract a coherent multipart request snapshot before later form edits',
    'mechanism':'FormData BodyInit serialization and boundary/body consistency',
    'hypothesis':'A request body may consult a later-mutated FormData or advertise a boundary different from the bytes it actually contains.',
    'relevance':'Workers prepare an upload request then reuse a form builder for later work.',
    'trace':['Construct a POST Request from two text form fields and clone it.', 'Modify the original FormData after Request construction.', 'Consume clone text and independently parse only its generated framing with the advertised boundary.', 'Assert fixed pre-edit pairs, original request unused, then parse the original request and exclude the late field.'],
    'expected':'Both request branches contain name=before,count=2 and no extra field; boundary from Content-Type matches framing.',
    'ranges':[(20,30),(50,84),(402,426),(511,535)], 'contract':[FETCH+'#concept-bodyinit-extract',MULTIPART],
    'source_note':'Pinned typed extraction eagerly serializes multipart bytes and sets its generated media type. The independent oracle accepts optional final CRLF and header-name casing rather than pinning incidental formatting.',
    'distinctness':'Construction-time multipart extraction plus independent framing oracle. No duplicate count for the clone used as an observation tool.'
  },
  {
    'id':'Y209', 'title':'Parse binary multipart file parts without UTF-8 replacement',
    'mechanism':'Multipart byte scanner separates text headers from binary file payloads',
    'hypothesis':'Decoding the entire multipart body as text before splitting parts may corrupt legal binary file bytes.',
    'relevance':'Workers accept small binary uploads alongside Unicode captions.',
    'trace':['Construct one valid fixed-boundary multipart body from text framing and six raw file bytes plus a Unicode caption.', 'Consume Response.formData().', 'Assert ordered keys, File metadata and exact raw bytes, then independent caption decoding.'],
    'expected':'File bytes [0,255,128,13,10,65] are unchanged; caption is café, filename bytes.bin, type application/octet-stream.',
    'ranges':[(345,351),(10715,10738),(10758,10891)], 'contract':[FETCH+'#dom-body-formdata','https://www.rfc-editor.org/rfc/rfc7578#section-4'],
    'source_note':'Pinned form parser scans raw bytes and decodes only headers and string fields. Arbitrary file bytes are valid upload content, not malformed encoding inputs.',
    'distinctness':'Binary multipart part ownership and separate text decoding, absent from H-series host-body byte forwarding.'
  },
  {
    'id':'Y210', 'title':'Preserve mid-line multipart boundary lookalikes in file content',
    'mechanism':'Multipart delimiter line-position recognition',
    'hypothesis':'A naive delimiter substring split may truncate valid file text that contains the boundary string in the middle of a line.',
    'relevance':'Workers parse textual attachments containing arbitrary marker-like strings.',
    'trace':['Construct one valid text-file multipart body with a mid-line --MarkerLine substring.', 'Parse once as FormData.', 'Assert one field, exact file text including the marker and CRLF, and filename.'],
    'expected':'One notes.txt file contains prefix--MarkerLine-suffix followed by CRLF and second line.',
    'ranges':[(10719,10738),(10785,10821)], 'contract':[FETCH+'#dom-body-formdata','https://www.rfc-editor.org/rfc/rfc2046#section-5.1.1'],
    'source_note':'Pinned delimiter scan requires beginning-of-line placement. The body never places a conflicting delimiter prefix at line start.',
    'distinctness':'Framing-position recognition, not binary decoding or malformed-boundary rejection.'
  },
  {
    'id':'Y211', 'title':'Read multipart field names when filename parameter comes first',
    'mechanism':'Content-Disposition parameter token boundaries and valid quoted boundary',
    'hypothesis':'A loose name= search may find the substring in filename= and assign a legal part to the wrong FormData field.',
    'relevance':'Workers receive ordinary uploads produced by clients with differing parameter order.',
    'trace':['Parse one well-formed multipart part whose disposition lists filename before name and whose media type quotes its boundary.', 'Assert logical field key upload, absence of a report.txt key, filename, and file text.'],
    'expected':'Field is upload and File name is report.txt, containing report.',
    'ranges':[(10740,10749),(10779,10789),(10847,10889)], 'contract':[FETCH+'#dom-body-formdata','https://www.rfc-editor.org/rfc/rfc7578#section-4.2'],
    'source_note':'Pinned parameter regexes are anchored to semicolon/start boundaries rather than substring searching.',
    'distinctness':'Valid parameter-order tokenization; no auth, header injection, forbidden filename, or malformed MIME.'
  },
  {
    'id':'Y212', 'title':'Normalize multiline form values on the multipart wire',
    'mechanism':'Multipart text-field line-ending normalization',
    'hypothesis':'Serializing form strings verbatim may leave bare CR and LF on the generated multipart wire.',
    'relevance':'Workers upload ordinary multi-line notes originating on different platforms.',
    'trace':['Append one text value with LF, CR, and CRLF line breaks.', 'Construct and consume one multipart Request.', 'Use an independent framing oracle to assert CRLF-normalized field text and assert original FormData value unchanged.'],
    'expected':'Serialized field is first\\r\\nsecond\\r\\nthird\\r\\nfourth; builder retains its original line-break sequence.',
    'ranges':[(34,44),(50,84)], 'contract':[MULTIPART],
    'source_note':'Pinned serializer encodes non-Blob values directly without normalizing line endings. Static discrepancy hypothesis only.',
    'distinctness':'Text-field wire normalization, not parser tolerance or URL form percent-decoding.', 'gap':True
  },
  {
    'id':'Y213', 'title':'Dispatch a URLSearchParams BodyInit through its inferred form media type',
    'mechanism':'Typed BodyInit extraction, media-type inference, and Body.formData dispatch',
    'hypothesis':'A typed query object may be stringified without its media type, consulted after mutation, or routed to the wrong body parser.',
    'relevance':'Workers construct URL-encoded event submissions from a reusable parameter object.',
    'trace':['Construct a POST Request from two simple params, clone it, then change the original params.', 'Assert inferred media type and exact construction-time clone text.', 'Consume original through formData and assert output class, pairs, and bodyUsed.'],
    'expected':'Media type application/x-www-form-urlencoded;charset=UTF-8; body event=launch&count=2; parsed FormData has those two fields.',
    'ranges':[(20,30),(451,456),(511,521),(10758,10772)], 'contract':[FETCH+'#concept-bodyinit-extract',FETCH+'#dom-body-formdata'],
    'source_note':'Pinned __typedBody has a distinct URLSearchParams branch and formData has a media-type dispatch path.',
    'distinctness':'U209/U210 test parameter algorithms directly; this has deliberately plain values and tests the Request/Body integration seam and snapshot.'
  },
  {
    'id':'Y214', 'title':'Transfer inherited Request bodies while leaving overridden sources unused',
    'mechanism':'Request constructor body ownership transfer versus explicit replacement',
    'hypothesis':'The buffered prior-Request path may silently copy bytes instead of transferring body ownership like the streaming path.',
    'relevance':'Workers wrap an incoming request or deliberately replace its payload before forwarding.',
    'trace':['Construct a POST Request with buffered body and construct another Request from it without replacement.', 'Assert original becomes bodyUsed, destination starts unused, and inherited text survives.', 'Construct a second source and explicit-body replacement; assert source stays unused and each distinct payload is readable.'],
    'expected':'Inherited body transfers and marks source used; explicit replacement does not disturb its separate source.',
    'ranges':[(402,426),(456,466),(501,521)], 'contract':[FETCH+'#dom-request', 'https://streams.spec.whatwg.org/#readablestream-create-a-proxy'],
    'source_note':'Pinned constructor marks prior used only when prior._bodyBytes is null; buffered input instead uses slice(). Static discrepancy hypothesis only.',
    'distinctness':'Request ownership transfer, absent from H008 clone-to-independent-upload and V215 cache clone consumption.', 'gap':True
  },
  {
    'id':'Y215', 'title':'Preserve cloned Response metadata while isolating mutable consumer results',
    'mechanism':'Buffered Response clone metadata and result-buffer ownership',
    'hypothesis':'A clone may share its header list, omit status metadata, or expose mutable consumed buffers that alter the original body.',
    'relevance':'Workers branch a buffered response for independent middleware annotations and byte inspection.',
    'trace':['Clone a three-byte response carrying explicit status, statusText, and an ordinary custom header.', 'Modify clone headers and assert original header plus clone status metadata.', 'Consume clone bytes and mutate them; assert original is unused and its later bytes remain exact.'],
    'expected':'Header lists are independent; status 201/Created survives; original bytes stay [9,8,7] after clone-result mutation.',
    'ranges':[(5,12),(285,296),(353,374)], 'contract':[FETCH+'#dom-response-clone',FETCH+'#concept-response-clone'],
    'source_note':'Pinned clone rebuilds a Response from copied bytes and copied init metadata. Its ordinary no-cache ownership assertions are the primary test.',
    'distinctness':'V215 checks Cache.put consumes only the supplied clone; its clone-read subcheck is not new credit here. New mechanisms are clone metadata/header-list independence and byte-result mutation ownership, with no Cache API.'
  },
  {
    'id':'Y216', 'title':'Snapshot JSON response data while retaining response initialization',
    'mechanism':'Response.json eager serialization and response initialization composition',
    'hypothesis':'Response.json may retain a mutable object instead of serialized bytes or discard supplied status/headers.',
    'relevance':'Workers return queued-job acknowledgments and then continue mutating the original application object.',
    'trace':['Construct a JSON response from an object with nested array and explicit status/header.', 'Mutate both source object and nested array.', 'Assert response init values, media type, fixed JSON bytes, and consumed body state.'],
    'expected':'Status 202 and x-job queued; body exactly {"order":7,"tags":["ready"]}; application/json media type.',
    'ranges':[(299,304),(340,344)], 'contract':[FETCH+'#dom-response-json'],
    'source_note':'Pinned static json serializes immediately and supplies JSON type unless present.',
    'distinctness':'Structured JSON serialization snapshot, not generic string extraction or Blob composition.'
  },
  {
    'id':'Y217', 'title':'Keep absent bodies distinct from empty streams and never disturbed',
    'mechanism':'Null Body representation and bodyUsed semantics',
    'hypothesis':'Body consumers may set a boolean used flag even with no stream, or a bodyless POST may be represented as an empty stream.',
    'relevance':'Workers return 204 acknowledgments and construct bodyless POST operations.',
    'trace':['Construct null-body 204 response, read empty text and empty ArrayBuffer, and assert body stays null and bodyUsed false.', 'Construct POST without BodyInit and assert null body and false bodyUsed.'],
    'expected':'Absent bodies have no stream and cannot become disturbed; conversions yield empty values.',
    'ranges':[(280,296),(330,355),(422,466)], 'contract':[FETCH+'#dom-body-bodyused',FETCH+'#concept-body-consume-body',FETCH+'#dom-request'],
    'source_note':'Pinned consumers assign bodyUsed=true unconditionally; Request creates a CelldBodyStream for POST even without body. Static discrepancy hypothesis only.',
    'distinctness':'Presence/absence representation, not a nonempty body replay or malformed use.', 'gap':True
  },
  {
    'id':'Y218', 'title':'Reflect direct body-reader disturbance in Response.bodyUsed',
    'mechanism':'Body state derived from ReadableStream disturbance',
    'hypothesis':'A stored bodyUsed flag may remain false when the body is read through its public stream instead of a convenience consumer.',
    'relevance':'Workers incrementally inspect a body through getReader and use bodyUsed to decide later routing.',
    'trace':['Construct a three-byte response and acquire a tracked reader.', 'Assert acquiring alone leaves bodyUsed false.', 'Read once, assert nonempty data and bodyUsed true, then bounded-drain and verify bytes and persistent disturbed state.', 'Cancel/release tracked reader on every exit.'],
    'expected':'bodyUsed is false before read and true after read/EOF; full bytes [21,22,23].',
    'ranges':[(160,209),(280,296),(340,355)], 'contract':[FETCH+'#dom-body-bodyused'],
    'source_note':'Pinned bodyUsed is assigned by convenience methods but CelldBodyStream does not update its owner when a reader disturbs it. Static discrepancy hypothesis only.',
    'distinctness':'Stream-to-Body state coupling, not H011 text consumption or S-series remote stream behavior.', 'gap':True
  },
  {
    'id':'Y219', 'title':'Infer text BodyInit media types while preserving an explicit override',
    'mechanism':'String BodyInit default content-type and caller override precedence',
    'hypothesis':'The string extraction fast path may omit the standard text media type or overwrite an explicitly supplied type.',
    'relevance':'Workers construct ordinary text requests and responses that downstream clients interpret by their media type.',
    'trace':['Construct one implicit-type string Response, an explicit-type control Response, and one string POST Request.', 'Assert inferred text media types and preserved explicit type.', 'Consume all three and assert fixed text without transcoding.'],
    'expected':'Implicit string bodies infer text/plain;charset=UTF-8; explicit text/x-fixture remains; all bytes spell hello.',
    'ranges':[(5,30),(249,289),(402,456)], 'contract':[FETCH+'#concept-bodyinit-extract'],
    'source_note':'Pinned MIME inference is only triggered for __typedBody object kinds; the string fast path does not assign a content type. Static discrepancy hypothesis only.',
    'distinctness':'Scalar-string extraction and MIME inference, separate from URLSearchParams typed-form dispatch and JSON static helper.', 'gap':True
  },
  {
    'id':'Y220', 'title':'Clone a valid finite streaming Response and settle both bodies',
    'mechanism':'Response.clone support for unused non-buffered Body streams',
    'hypothesis':'Response.clone may reject an unused valid stream solely because the body has not been buffered.',
    'relevance':'Workers clone a streaming response for two ordinary consumers within one active request.',
    'trace':['Create a finite stream that eagerly enqueues two two-byte chunks and closes.', 'Construct a Response and clone it before any read.', 'Assert both bodies are unused, then join both consumers with allSettled.', 'Assert successful terminal outcomes, exact four-byte arrays, and clone metadata.'],
    'expected':'Clone succeeds; both consumers settle fulfilled with [10,20,30,40]; status 203 and x-origin local-stream preserved.',
    'ranges':[(139,158),(249,284),(353,374)], 'contract':[FETCH+'#dom-response-clone',FETCH+'#concept-body-clone'],
    'source_note':'Pinned Response.clone explicitly throws when _bodyBytes is null, despite the source being unused. Static discrepancy hypothesis only.',
    'distinctness':'Response.clone unsupported-source path, unlike H008 Request.clone followed by two committed host uploads, S017 remote tee, or buffered Cache.put ownership.', 'gap':True
  },
]

source = (HERE/'cases.js').read_text()
for design in DESIGNS:
    case_id=design['id']
    match=re.search(r'^  async '+case_id+r'\(t\) \{\n(.*?)^  \},',source,re.M|re.S)
    assert match
    assertions=[line.strip() for line in match.group(1).splitlines() if re.search(r't\.(equal|deep)\(',line)]
    design['fixed_runtime_assertions']=assertions
    design['assertion_count']=len(assertions)
    design['implementation']={'file':'cases.js','symbol':case_id,'start_line':source[:match.start()].count('\n')+1,'end_line':source[:match.end()].count('\n')+1}
    design['runtime_source_refs']=[{'path':HARNESS,'line_start':start,'line_end':end} for start,end in design.pop('ranges')]
    design['primary_contract_refs']=design.pop('contract')
    design['application_relevance']=design.pop('relevance')
    design['desired_behavior']=design.pop('expected')
    design['source_observation']=design.pop('source_note')
    design['static_prediction']='EXPECTED_FAILURE_CANDIDATE' if design.pop('gap',False) else 'NO_FAILURE_PREDICTION'
    design['prediction_is_runtime_evidence']=False
    design['entrypoint']={'method':'GET','path':'/case/'+case_id,'request_body':None}
    design['layer']='direct-celld-worker-fetch-global-body-form-api'
    design['preconditions']=['Reviewed exact direct-celld source/build/deployment pins and fresh isolated local store.', 'Native celld Blob, File, FormData, Request, Response, and ReadableStream globals; no mocks or implementation extraction.', 'External five-second case deadline plus independent 300-second suite deadline and owned cleanup are active.']
    design['schedule']={'kind':'one finite in-request trace','ordinal':int(case_id[1:])-200,'request':'GET /case/'+case_id,'depends_on':[],'parallelism':'two local body consumers joined with allSettled only in Y220; otherwise sequential'}
    design['limits']={'requests':1,'repetitions':1,'incoming_body_bytes':0,'outer_case_seconds':5,'fixture_logical_byte_cap':16384,'response_bytes':65536,'max_explicit_reader_reads':16,'max_form_entries':8,'timers':0,'outbound_fetches':0,'durable_writes':0}
    design['cleanup']='Every case is awaited before cleanup. Track explicit readers and body streams; cancel/release readers, initiate all unlocked-stream cancellations before joining them, and retain no request-local objects. Buffered body producers may be lazy; explicit JS stream producers are finite and close synchronously. Cleanup records runtime-retained locks with awaited consumer/descendant proof, and any unverified lock blocks acceptance. No open producer gates, external handles or timers are used. Await both Y220 consumers with allSettled. If a body method or cleanup does not settle within the external deadline, supervisor terminates only the owned process group and records failure/unknown plus incomplete cleanup. It never reports a pass.'
    design.update(authored=True,independently_reviewed=False,review_status='UNREVIEWED',status='NOT_RUN',runtime_status='UNRUN',actual_runtime_executions=0,runtime_pass_claimed=False)

manifest={'schema_version':1,'profile':'direct-celld-body-form-semantics-v1','source_snapshot':'celld-direct-source-v0.6.2-8d27-guard-20261009','authored_case_count':20,'reviewed_case_count':0,'runtime_executions':0,'runtime_status':'UNRUN','qualification':'Handwritten assertion-bearing candidates. Author/source/static evidence only; no SUT or reference-runtime execution. Independent review required for primary census credit.','oracle_policy':'Fixed literal values are authored independently from API contracts. Source-gap notes never replace desired behavior. Generated multipart boundary randomness is normalized only through a bounded independent framing parser, which accepts standard optional final CRLF and header casing. No case is generated by a parameter sweep.','ordinary_input_scope':'Tiny valid Blob/File/FormData/Request/Response inputs. All multipart examples are complete legal framing; arbitrary binary File bytes are allowed. No repeated use of consumed nonnull bodies, malformed input, auth, forgery, replay, transport fault, retained capability, guarded core path, outbound fetch, or host upload. Upload workflows are exercised as local Request bodies inside the direct Worker.','contract_sources_consulted_utc':'2026-10-09','cases':DESIGNS}
(HERE/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
