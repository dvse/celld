#!/usr/bin/env python3
"""Emit metadata for nine handwritten traces; never execute a runtime."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
STREAM = 'celld-os-project/celld/crates/celld/js/streams.js'
WRITE = 'celld-os-project/celld/crates/celld/js/writable_stream.js'
HARNESS = 'celld-os-project/celld/crates/celld/js/harness.js'
SPEC = 'https://streams.spec.whatwg.org/#readable-stream-pipe-to'
PROFILE = 'direct-celld-pipe-cleanup-semantics-v1'

DESIGNS = [
 ('S201', 'Keep sink writable after pipe EOF', 'prevent-close-and-writer-reuse',
  ['Pipe two fixed values with preventClose.', 'Witness fulfillment and lock release without sink close.', 'Acquire a new writer, write one value, close and release.'],
  'S015 drains with default close; S024 transfers writer ownership on a remote writable. This joins pipe EOF suppression with independently proven sink usability.', None),
 ('S202', 'Reuse sink after source error', 'prevent-abort-forward-error-isolation',
  ['Witness one sink callback.', 'Error the ordinary source controller with a specific Error.', 'Join rejected pipe, then independently write and close the preserved sink.'],
  'S006/S007 observe read errors and X006/X007/X020 propagate source failure into native transforms. This prevents forward abort and proves the surviving sink accepts new data.', None),
 ('S203', 'Drain source after sink error', 'prevent-cancel-backward-error-isolation',
  ['Offer one fixed value to an ordinary throwing sink.', 'Join pipe rejection with preventCancel.', 'Enqueue a new source value only after pipe termination, close source, then read it to EOF.'],
  'S016 requires default source cancellation. This suppresses cancellation and demonstrates new post-pipe data remains readable, without relying on implementation read-ahead.', None),
 ('S204', 'Reuse both resources after signal shutdown', 'prevent-both-inflight-write-shutdown',
  ['Hold a single sink write with an explicit gate.', 'Abort with preventAbort and preventCancel, and witness pending pipe.', 'Release write, join rejection, independently drain source and write/close sink.'],
  'X013 fans an active signal into native transform/source shutdown. This preserves both ordinary resources after abort and proves both remain usable; not a flag permutation credited without a new lifecycle.', None),
 ('S205', 'Join write and both signal cleanup actions', 'inflight-write-then-async-abort-cancel-join',
  ['Hold a single sink write and abort the active pipe.', 'Witness no cleanup entry before releasing that write.', 'Hold both abort and cancel callbacks, release abort first, and require pipe remain pending until cancel also finishes.'],
  'X013 has signal fanout but no independently held write, sink-abort acknowledgment and source-cancel acknowledgment. S020 covers queued writer close, not pipe shutdown fanout.', None),
 ('S206', 'Hold pipe completion through sink close', 'eof-async-close-join-and-lock-lifetime',
  ['Pipe one value and close source.', 'Hold underlying sink close and witness pending pipe with both locks.', 'Acknowledge sink close and join fulfilled pipe with released locks.'],
  'S015 covers transfer; S019/S020/S023 cover direct writers. No prior design holds ordinary pipeTo close acknowledgment and asserts the pipe promise and both lock lifetimes.', None),
 ('S207', 'Preserve zero pre-abort reason without transfer', 'pre-aborted-falsy-reason-identity',
  ['Abort the real controller with numeric zero.', 'Pipe one queued source value to an unwritten sink.', 'Require exact zero reason at pipe rejection and both cleanup callbacks, with zero writes.'],
  'H017 concerns pre-dispatch HTTP abort; X013 is an already-running native pipe. This exercises the ordinary pipe pre-abort reason branch with a valid falsy reason, not malformed input.',
  {'classification':'EXPECTED_FAILURE_CANDIDATE','source_evidence':'streams.js:568-573 substitutes DOMException via signal.reason || fallback; harness.js:10584-10588 accepts numeric zero.', 'intended_oracle':'Pipe rejection and cleanup reasons equal numeric zero exactly.'}),
 ('S208', 'Join pre-aborted asynchronous cleanup', 'pre-aborted-both-actions-join-before-release',
  ['Use a pre-aborted real signal and queue one value.', 'Hold both source cancel and sink abort callbacks.', 'Release cancel first; require pipe and locks remain pending until sink abort is released.'],
  'S207 covers zero identity, while this covers early-branch asynchronous join and ownership duration. S205 reaches shutdown after a held write; pre-abort is a different implementation branch.',
  {'classification':'EXPECTED_FAILURE_CANDIDATE','source_evidence':'streams.js:568-573 invokes cancellation and abort without joining their returned promises and returns an immediate rejection before acquiring pipe owners.', 'intended_oracle':'Pipe and locks remain live until both asynchronous shutdown callbacks complete; no data transfer.'}),
 ('S209', 'Surface cancellation failure after signal abort', 'shutdown-action-rejection-precedence',
  ['Accept one fixed value, then signal abort with preventAbort.', 'Hold source cancel callback and then reject it with a separate application Error.', 'Require the cancellation Error to replace the signal Error; independently write and close surviving sink.'],
  'Neither S016 nor X013 tests shutdown action failure precedence. preventAbort deliberately isolates one failing action, so no simultaneous-rejection ordering is assumed.',
  {'classification':'EXPECTED_FAILURE_CANDIDATE','source_evidence':'streams.js:617-619 catches and discards source cancellation rejection; 620-621 finishes with original signal reason.', 'intended_oracle':'The source cancel callback rejection replaces the initiating signal reason.'}),
]

def emit(name, obj):
    (HERE / name).write_text(json.dumps(obj, indent=2) + '\n')

def pin(root, path):
    data = (root / path).read_bytes()
    return {'path':path,'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}

body = (HERE / 'cases.js').read_text()
case_rows = []
for ident, intent, mechanism, trace, distinctness, gap in DESIGNS:
    match = re.search(r'^  async ' + ident + r'\(t\) \{\n(.*?)^  \},', body, re.M | re.S)
    assertions = [line.strip() for line in match.group(1).splitlines() if re.search(r't\.(equal|same|deep|before|locked|unlocked)\(',line)]
    case_rows.append({
      'id':ident,'intent':intent,'mechanism':mechanism,'implementation':'cases.js:' + ident,
      'entrypoint':{'method':'GET','path':'/case/' + ident,'request_body':None},
      'classification':'ordinary-functional-stream-lifecycle','primary_candidate':True,'independently_reviewed':False,
      'status':'NOT_RUN','runtime_status':'UNRUN','actual_runtime_executions':0,
      'preconditions':['Exact guarded source and actual direct-celld build/deployment identity verified.', 'One active Worker.fetch; real built-in ReadableStream/WritableStream/AbortController.', 'Independent supervisor enforces all schedule deadlines and limits; no reference runtime substitution.'],
      'trace':trace,'fixed_runtime_assertions':assertions,'assertion_count':len(assertions),
      'oracle':'All literal assertions execute and pass; no pending promise or public lock remains after joined cleanup.',
      'cleanup':'Open all finite gates even on assertion failure; signal-stop unfinished pipes; join original pipe and callback promises; release manual owners; prove readable/writable terminal states with closed promises; cancel/abort only still-open local resources; release probe owners. Owned supervisor teardown remains mandatory.',
      'runtime_source_refs':[{'path':STREAM,'line_start':539,'line_end':663},{'path':STREAM,'line_start':414,'line_end':454},{'path':WRITE,'line_start':291,'line_end':527},{'path':WRITE,'line_start':168,'line_end':197},{'path':HARNESS,'line_start':10532,'line_end':10589}],
      'primary_contract_refs':[SPEC],'distinctness':distinctness,'source_predicted_gap':gap,
      'os_relevance':'Core OS supporting stream/cancellation primitive; preserved native-transform OS provenance provides context only. This is not a claim that OS callers set these flags, nor a new product service.'
    })
emit('manifest.json',{'schema_version':1,'profile':PROFILE,'authored_case_count':len(case_rows),'runtime_status':'UNRUN','runtime_executions':0,'reviewed_credit':0,'review_receipt_required':True,'fixture':'fixture.js','config':'wrangler.json','cases':case_rows})

base_files = ['celld-os-stress/cases/streams.json','celld-os-stress/fixture/index.js','celld-os-stress/waves/native-transform-stress/manifest.json','celld-os-stress/waves/native-transform-stress/operations.js','celld-os-stress/waves/native-transform-stress/source-pins.json','celld-os-stress/waves/http-stream-stress/manifest.json','celld-os-stress/waves/http-stream-stress/cases.js','celld-os-stress/COUNTS.json','BUILD_AND_TEST.md']
prior = json.loads((ROOT / base_files[4]).read_text())
os_context = [entry for entry in prior['sources'] if '/os/' in entry['path']]
emit('source-pins.json',{'schema_version':1,'source_snapshot':ROOT.name,'source_root_at_authoring':str(ROOT),'upstream_commit':'90b43017241f81189453d326d05948f388b34652','binary_sha256':None,'binary_note':'No runtime built or run; historic unguarded binary hashes are not qualification evidence for these new guarded-source tests.','runtime_sources':[pin(ROOT,p) for p in [STREAM,WRITE,HARNESS]],'baseline_evidence':[pin(ROOT,p) for p in base_files], 'campaign_evidence':[pin(HERE.parent,'reviews/baseline-inventory-review.json'),pin(HERE.parent,'body-form-semantics/cases.js')], 'fixture_artifacts':[pin(HERE,p) for p in ['cases.js','fixture.js','wrangler.json']], 'primary_standard':{'url':SPEC,'retrieved_date':'2026-10-09','authority':'WHATWG Streams Standard normative pipe algorithm; implementation gaps do not weaken intended oracles.'},'os_provenance_context':{'status':'PRESERVED_METADATA_ONLY_OS_CHECKOUT_ABSENT','os_commit':prior['os_commit'],'source_manifest':base_files[4],'preserved_records':os_context,'qualification':'Historical OS archive/worksheet-export/digest stream-use evidence supports testing the shared stream primitive. OS source was not reread; no new live OS behavior or exact prevent* flag usage is asserted.'}})

extensions={'.js','.mjs','.json','.py','.rs'}
files=sorted(p for p in (ROOT/'celld-os-stress').rglob('*') if p.is_file() and p.suffix in extensions)
tokens=['preventClose','preventAbort','preventCancel']
search={token:[] for token in tokens}
for path in files:
    for lineno,line in enumerate(path.read_text().splitlines(),1):
        for token in tokens:
            if token in line: search[token].append({'path':str(path.relative_to(ROOT)),'line':lineno,'excerpt':line.strip()})
index=json.loads((HERE.parent/'reviews/baseline-inventory-review.json').read_text())
nearby=[item for item in index['design_index'] if re.search(r'stream|pipe|cancel|abort|close',item['intent'],re.I)]
emit('overlap-audit.json',{'schema_version':1,'evidence':'STATIC_SOURCE_INSPECTION_ONLY','baseline_designs_indexed':index['design_index_count'],'baseline_file_count':len(files),'prevent_option_search':search,'neighboring_baseline_designs':nearby,'human_review_focus':['S001-S024 source and executable baseline','X001-X024 manifest (X017 absent in preserved baseline); X013 exact executable signal trace','H001-H026 HTTP transport lifecycle manifests','All baseline intent-index stream/cancel/close neighbors','Concurrent body/form Y201-Y220 uses Blob/Body/Request ownership, not pipe shutdown; facet/root and atomic accounting author lanes have separate mechanisms.'],'per_case_distinctness':{row['id']:row['distinctness'] for row in case_rows},'not_added':['No repeated default pipe success or default sink-error cancellation case.','No general flag/value matrix; zero tests reason identity in the distinct pre-abort branch.','No compression/HTTP-body transport/capability-lifetime/lease/draining or malformed-input expansion.']})
emit('schedule.json',{'schema_version':1,'profile':PROFILE,'runtime_status':'UNRUN','suite_outer_deadline_seconds':180,'preflight_deadline_seconds':30,'startup_deadline_seconds':90,'cleanup_deadline_seconds':20,'concurrency':1,'retries':0,'request_count':len(case_rows),'resource_envelope':{'supervisor_enforced':True,'runtime_process_group_memory_max_bytes':536870912,'runtime_process_group_cpu_cores':1,'runtime_process_group_pid_max':128,'v8_heap_limit_mb':128,'request_response_max_bytes':65536,'owned_filesystem_max_bytes':268435456},'requests':[{'id':row['id'],'method':'GET','path':'/case/'+row['id'],'body':None,'outer_deadline_seconds':5,'repeat':1,'response_max_bytes':65536} for row in case_rows],'completion_contract':['Every declared assertion executes and passes.','All original pipe, write, close, abort, cancel and read promises are joined; every finite gate opened.','Source and sink terminal closed promises observed; public locks and timers both zero.','Independent owned process-group exit and disposable store deletion verified before acceptance.'],'stop_conditions':['Missing binary/provenance/deadline supervisor before trace entry => BLOCKED/NOT_RUN.','Entered-case deadline or resource breach => FAIL, not PASS; ambiguous entry/outcome => UNKNOWN.','Timeout termination is owned-process supervision, not a test stimulus; kill only owned process group.','Finish after one request per case and verified teardown; no retries or stress multiplication.']})
