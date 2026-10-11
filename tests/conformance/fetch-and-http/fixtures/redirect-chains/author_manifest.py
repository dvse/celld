"""Serialize twelve individually specified traces. No case/body generation or SUT work."""
import json,pathlib
HERE=pathlib.Path(__file__).resolve().parent
# id, intent, hypothesis, specific precondition, ordered trace, stress, oracle, distinctness
ROWS=[
('F001','Retain manual redirect body during sibling upload','Manual mode consumes Location or loses ownership of the original3xx body','302 source owns4096-byte prefix and held12289-byte tail; target configured but unvisited',
 ['Read manual302 headers and exact logical4096-byte prefix','Complete independent257-byte upload and effect','Observe source still active and target entered0','Release tail; consume exact original body; reassert target entered0'],
 'One retained3xx response overlaps an independently entered/committed recipient upload',
 '302 and exact Location preserved; original body exact12289 bytes with stable EOF; target entry/effect0 before and after completion; sibling effect1',
 'H004 retains a200 response; this is the manual redirect policy/response ownership boundary, including forbidden automatic target dispatch'),
('F002','Resolve relative redirect chain by current URL','Successive relative Locations resolve against stale path/query or reorder endpoint identity','Acyclic origin/start?phase=start -> branch/middle?phase=middle -> branch/final?phase=done; original-base resolution instead reaches unconfigured origin/final; final head held',
 ['Start follow request at origin/start using ../branch/middle Location','Witness branch/final path/query behind the second relative final Location','Complete independent upload while final response head remains held','Release head and compare final payload; assert exact start,middle,final entry order and branch/final path'],
 'Two finite redirects before a held final head, with independently completed upload',
 'Each endpoint enters once with configured path/query and GET/zero input; order exact; final path is branch/final rather than stale-base origin/final; final headers/root/isolate/body identify final; sibling effect1',
 'M004/M016 resolve module referrers; this is native HTTP Location resolution, with recipient-observed path/query and no module work'),
('F003','Rewrite buffered POST after302','Native redirect resends submission method/body after a302 that should become GET','POST source fully consumes8193 synthetic document bytes; final expects empty GET and holds response head',
 ['Send finite buffered POST in follow mode','Observe result endpoint input EOF before releasing its head','Assert source POST8193 versus target GET0 with exact independent hashes','Complete sibling upload; release final head and drain response'],
 'Normal method rewrite while caller promise remains unresolved at a distinct recipient request',
 'Source receives exactly8193 bytes once, target GET has0 bytes, sibling commits first, final body exact619 bytes',
 'H uploads never redirect; this asserts method/body transition, not another status-code or byte-count variant'),
('F004','Carry303 method rewrite through later307','A later preserving redirect restores an earlier PUT/body that303 already discarded','PUT7169 ->303 ->GET ->307 ->GET; final response head held',
 ['Start buffered PUT followed through303','Witness final entry after later307','Check PUT input exact then both later requests GET/empty','Complete sibling upload before releasing final response'],
 'Two different ordinary redirect transitions compose within one fetch promise',
 'Initial PUT7169 exact; intermediate/final GET0 exact; no body resurrection; sibling effect1 and final701-byte body',
 'F003 covers POST302 branch; this separately reachable PUT303 transition plus preserving subsequent hop owns different state carryover failure'),
('F005','Preserve finite PUT body at moved endpoint','307 resubmission loses or duplicates ordinary finite request bytes or changes method','Both moved and stored endpoints expect same16387-byte buffered PUT; target commit held',
 ['Start PUT with307 follow and ordinary content type','Witness stored input EOF/effect0','Verify complete identical source/target input hashes, methods and preserved content type','Complete independent upload, release target commit, require effect1 and exact response'],
 'Finite source/target request bodies plus held target application effect',
 'Both endpoints entered exactly once with exact16387 bytes; method PUT and content type preserved; target effect0 before release and1 afterward; independent upload completes first',
 'Ordinary307 body resend, no authentication or protocol replay; H008 clones request branches, whereas native redirect owns this sequential transfer'),
('F006','Preserve HEAD across303 without payload','303 incorrectly becomes GET for HEAD or emits a body at either endpoint','HEAD303 source points to HEAD final with32771 logical length; final head held',
 ['Start followed HEAD','Witness final method HEAD before releasing response','Complete sibling upload','Release final head; verify length, empty client body and zero server output at both endpoints'],
 'Method-preserving HEAD exception to303 rewrite overlaps independent request',
 'Both methods HEAD/empty input; both outputBytes0 and head terminals; client body empty; final Content-Length32771; sibling effect1',
 'H014 checks direct HEAD suppression; this tests HEAD survival through native303 method-selection branch'),
('F007','End follow at302 without Location','Follow mode fabricates a further request or drops a valid locationless3xx body','302 has no Location; body has4096 prefix and10241 total bytes behind tail gate',
 ['Fetch locationless302 with follow','Read logical prefix and check status/header absence','Complete sibling upload while locationless body remains active','Release tail, consume exact body, inspect only configured operation entries'],
 'Redirect-status response without a redirect destination retains active body ownership',
 'Status302 and null Location returned; exact10241 bytes/stable EOF; source once; sibling effect1; no additional configured endpoint',
 'A distinct redirect termination predicate; F001 suppresses following explicitly while F007 requests follow but has no destination'),
('F008','Cancel manual body before explicit handoff','Closing a manual3xx reader corrupts the later explicitly issued target request','Manual decision endpoint has4096 prefix/held tail; explicit target head held',
 ['Read manual response Location and prefix; prove target unvisited','Cancel reader and require terminal read, then explicitly stop source application','Issue fresh explicit target GET and witness recipient entry','Complete independent upload, release target head and drain exact target response'],
 'Caller-controlled manual redirect decision, body cancellation, then a distinct ordinary request',
 'Target entry0 until cancellation; canceled reader done; explicit target once with correct997 bytes/root/isolate; independent upload effect1',
 'H019 cancels one body alongside an already-active sibling; this covers OS manual-redirect release-before-new-request flow and never claims cancellation rolls back application effects'),
('F009','Abort while intermediate redirect head is held','Cancellation fails after native fetch changes its internal current hop','First302 reaches middle; middle Location remains unavailable behind head gate; final never configured to run directly',
 ['Start follow with unique AbortController','Witness first complete and middle entered/EOF while head withheld','Abort with exact planned Error and require identical native fetch rejection; explicitly stop middle','Complete separate peer redirect graph; prove final entered0 and middle settled'],
 'Abort association after successful first-hop progression, beside independent healthy redirect graph',
 'Native fetch rejects with exact F009 planned intermediate abort reason object; first once, middle once/stopped, never0; peer graph exact; no rollback inference',
 'H018 aborts initial held request; this requires native multi-hop cancellation handle to continue owning the changed destination'),
('F010','Separate discarded redirect bodies from final stream','Unread intermediate network bodies contaminate or prematurely terminate the final response stream','First and second redirects own distinct6151/8193-byte bodies; second head held; final16389 bytes has4096 prefix/held tail',
 ['Follow first nonempty redirect until second entry','Complete independent upload before releasing second head','Read exact final-only prefix after both intermediate responses','Hold final tail, verify first/second journals, release tail and drain exact final body'],
 'Internal redirect-body consumption/disposal followed by separately owned incremental final body',
 'Client receives only final16389 bytes and stable EOF; both redirects entered once; final4096-byte produced barrier precedes tail release; sibling completes during intermediate hold',
 'F002 uses empty intermediate bodies for URL resolution; H body tests have no native redirect-internal body owner or discarded responses'),
('F011','Keep overlapping manual and follow choices independent','Cached same-origin client redirect policy bleeds between concurrent requests','Manual-start3xx body prefix held; independent follow-start points to separate final endpoint on same origin',
 ['Open and retain manual redirect prefix','Complete separate same-origin follow chain','Prove manual target unvisited and manual body still held','Release manual tail and retain original302 status; reassert target0'],
 'Two per-call redirect policies overlap in one coordinator invocation and same native origin pool',
 'Follow target body811 exact and source/final once; manual remains302 with exact9217 bytes; manual-target entered0 throughout',
 'F001 overlaps upload but not another redirect policy; this tests client-policy partitioning rather than generic reader scheduling'),
('F012','Report final URL and redirected metadata','Response metadata retains original request identity after a native redirect','One direct control plus one302 to query-bearing final; target head held to prove overlap',
 ['Start redirect and witness actual destination before response head','Complete direct control; assert its own URL and redirected false','Release destination head and consume exact final bytes with recipient identity','Assert followed URL equals final path/query and redirected true together'],
 'Direct control completes while a followed request is accepted at its final endpoint',
 'Direct response.url equals direct endpoint and redirected false; redirected response.url equals destination?document=final and redirected true; exact recipient journals and bytes',
 'No existing H/B/S/X/M case asserts Fetch final URL metadata; two properties are one case, not separate counting variants')
]
PRE=[
 'Fresh already-running owned disposable candidate8d27 fleet, parent exclusive slot, independent exact-hash source/oracle review',
 'External supervisor records actual process/boot/executable/DO/isolate identities and hard resource limits; no synthetic boolean substitutes for evidence',
 'Distinct coordinator/recipient roots and isolates; recipient local to fixed owned192.168.77.1:18080 ingress; controls and every hop are independent recipient requests',
 'Native public Fetch, ReadableStream, AbortController and SHA256 APIs; fresh recipient operation journal required before trace entry',
 'All synthetic bodies and valid ordinary redirects stay in earlier-configured owned fixture endpoints; graph depth at most3, each operation enters at most once'
]
CLEAN=[
 'Coordinator remains in active DO.fetch; close scope, abort pending owned fetches, cancel/release all owned readers and response bodies',
 'Recipient marks operations stopped before releasing gates; joins all entered handlers and producer pulls; any fault or unresolved work BLOCKS cleanup',
 'Join complete coordinator trace and every watched task; exact expected abort only; unobserved assertion failures cannot become successful cleanup',
 'Matched recipient journal and zero active/readers/controllers/pulls plus zero caller response/request/task resources required',
 'Independent supervisor must close/reap/destroy only owned sockets/processes/fresh storage and provide hash-matched teardown before runtime PASS'
]
rows=[]
for i,title,hyp,pre,trace,stress,oracle,distinct in ROWS:
 rows.append({'id':i,'title':title,'intent':title,'failure_hypothesis':hyp,'preconditions':[pre,*PRE],'trace':trace,'stress':{'schedule':stress,'bounded':True,'logical_payload_bytes_max':4194304,'operation_bytes_max':131072,'fixture_operations_max':24,'redirect_edges_per_graph_max':3,'coordinator_http_max':6,'coordinator_http_attempts_max':160,'wall_seconds_max':30,'active_fixture_ms_max':24000},'oracle':oracle,'cleanup':CLEAN,'distinctness':distinct,'implementation':'cases.js:'+i,'test_function':i,'layer':'real-process-HTTP','classification':'correctness-stress-candidate','promotion_candidate':True,'profile':'profile.json','os_call_sites':['provenance/os/web-fetch.ts:285-315','provenance/os/fetch.ts:164-214'],'request_scope':'one active coordinator DO.fetch; each control/hop/probe is an independent ordinary HTTP recipient request in a fresh recipient DO; no cross-invocation retained capability','layer_limits':'No OS workflow execution, cross-VM claim, authentication, security, fairness, throughput or durable effect guarantee','source_hypothesis':'Predicted final-URL/redirected mismatch from candidate source; no runtime defect established' if i=='F012' else 'Unexecuted contract candidate','authored':True,'reviewed':False,'executable_source_implementation':True,'run':False,'passed':False,'status':'NOT_RUN'})
(HERE/'manifest.json').write_text(json.dumps(rows,indent=2)+'\n')
