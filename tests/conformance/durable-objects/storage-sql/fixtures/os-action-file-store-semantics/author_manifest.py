#!/usr/bin/env python3
"""Generate this wave's source-only metadata before independent freeze. No JS import/run."""
import hashlib, json, pathlib, re
H = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
CAMPAIGN = H.parent
OS = CAMPAIGN/'os-source-inventory/historical-4358072'
COMMIT = '4358072f8cb1bc9ddfb6ee11122e194c76cd71e0'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def save(name, value): (H/name).write_text(json.dumps(value, indent=2)+'\n')
def pin(root, name):
 p=root/name
 return {'path':name,'sha256':sha(p),'bytes':p.stat().st_size}
def ref(root,path,lo,hi): return {'root':root,'path':path,'line_start':lo,'line_end':hi}
af='vendor/cloudflare-os/packages/gatekeeper-kit/src/action-files.ts'
afr=lambda lo,hi:ref('wave',af,lo,hi)
gs='raw/packages/gatekeeper-google/src/gmail-state.ts'
gm='raw/packages/gatekeeper-google/src/gmail.ts'
limits={
 'max_external_case_http_requests':1,'max_frontend_do_fetches':1,'max_created_do_roots':1,
 'max_outbound_public_network_requests':0,'max_native_storage_entries':16,'actual_max_native_entries':10,
 'max_total_retained_payload_bytes':2097169,'visible_js_byte_buffer_estimate_bytes':16777216,'byte_buffer_estimate_scope':'Conservative visible-JS payload-view estimate only, not a total memory cap. Native serialization, WebCrypto transient copies, runtime heaps and allocator retention remain covered by the independently enforced aggregate RSS ceiling.',
 'max_rows_per_fully_consumed_iterator':64,'max_native_list_calls':64,'max_native_kv_point_operations':256,
 'max_native_transactions':16,'max_public_module_calls':12,'max_webcrypto_digest_calls':8,'max_streams':0,
 'max_clock_waits':32,'clock_wait_interval_ms':5,'max_external_receipt_bytes':32768,
 'precondition_deadline_ms':1000,'trace_deadline_ms':5000,'cleanup_deadline_ms':2000,
 'outer_http_deadline_seconds':10,'outer_case_process_deadline_seconds':15,'outer_wave_deadline_seconds':120,
 'outer_rss_bytes':1073741824,'max_owned_domain_processes':32,'max_owned_writable_bytes':134217728,
 'descendant_supervision':'Entire proven-owned dev, trusted-bundler and runtime descendant tree across PGIDs; prefer one enforceable cgroup and ownership domain. A single PGID or parent PID is insufficient.',
 'writable_quota_scope':'All generated bundles, staging config, logs, temporary files and private store. Do not copy externally supplied read-only source/binaries into the writable domain.'}
preconditions=[
 'Exact unmodified module, closed helper import graph, Apache license and guarded direct-celld source/build/bundle identities.',
 'Fresh disposable migrated SQLite-backed DO with genuine storage.kv, transactionSync and WebCrypto; only synthetic data.',
 'External supervisor witnesses complete process ownership, loopback ingress, bounded resource domain and whole-descendant teardown across PGIDs.',
 'Trusted future bundler with TypeScript erasure only; missing build/runtime prerequisites are BLOCKED, not substituted.']
cleanup=[
 'Await every capture/read and its digest before marking original trace settled; no streams exist.',
 'If original trace remains unsettled, do not race in-object teardown; external supervisor reaps the entire owned domain.',
 'After settlement open and completely drain one public native sync-KV iterator to replace any abandoned cursor; never call next after done.',
 'DeleteAll only this fresh owned DO and verify KV empty; cleanup failures are typed blockers.',
 'Independently terminate and verify every proven-owned dev/bundler/runtime descendant across PGIDs and remove only owned staging/bundles/logs/temp/private store, regardless of fixture outcome.']
specs=[
 ('F201','Snapshot capture input before awaiting digest',
  'The production digest and chunk copies might observe different versions of a caller-mutated offset view.',
  ['Capture the five-byte view of an eight-byte backing buffer.','Mutate the backing synchronously before awaiting capture.','Check returned digest, stored chunk, public read, exact keys and charge against original literal bytes.'],
  'Original view [10,20,30,40,50], caller now all99; SHA6ef53a64…; one chunk; counter5 and exactly four native keys.',
  [afr(83,123),afr(131,160),afr(249,251)],['D201','D205','T019','X023','I202'],
  'D201/D205 snapshot serialized values; T019 snapshots a SQL BLOB during coercion; X023 copies an imported HMAC key; I202 converts R2 input. None exercises the actual ActionFileStore synchronous dual digest/chunk snapshot before its first await and the stored integrity-checked publication.',1,1,0,0,4,5),
 ('F202','Publish and reassemble real chunk boundaries',
  'Production 1 MiB split, key numbering, native typed-value persistence or reassembly could lose, reorder or mischarge boundary bytes.',
  ['Capture exactly2097169 synthetic bytes with three literal regions.','Check actual native chunks0000/0001/0002 with lengths1048576/1048576/17 and every byte.','Read via the real module, compare every reconstructed byte, exact digest, metadata, complete keys and aggregate charge.'],
  'Regions17×1048576 then34×1048576 then bytes0..16; SHA669a63cb…; chunks3; bytes2097169; exactly six native entries.',
  [afr(88,123),afr(126,160),afr(188,202)],['T210','T213','D202','I203'],
  'T210 uses authored four-byte SQL chunks and overwrite logic; T213 uses authored two-byte SQL completeness/charge transfer. D202 is structured-clone brand conversion; I203 is R2 streaming concatenation. This case uses actual OS chunk production and digest-validating reassembly across its real 1 MiB boundaries. It claims complete post-resolution publication, not concurrent isolation.',1,1,0,0,6,2097169),
 ('F203','Retain empty allocation without chunks',
  'A zero-iteration capture or read could omit the genuine allocation/manifest, fabricate a placeholder chunk, or fail to remove the zero-charge allocation.',
  ['Capture an empty genuine Uint8Array with positive configured limits.','Check manifest and allocation, zero native chunks, empty digest/read and literal counter0.','Delete through the real module and require only the zero counter remains.'],
  'SHAe3b0c442…; size0; chunks0; three initial keys then only alloc/totalBytes=0.',
  [afr(88,123),afr(131,160),afr(204,219)],['D210','D211','T213'],
  'D210/D211 concern primitive deletion receipts and deleteAll reset; T213 presupposes nonempty synthetic SQL chunks. The actual module zero-iteration branch must retain and later remove its allocation even though no payload or positive aggregate charge exists. No size-grid variants are counted.',1,1,1,0,3,0),
 ('F204','Release genuine allocation only once',
  'The repeated-valid-delete path might subtract a size without a remaining allocation or damage another capture sharing the store.',
  ['Capture genuine four-byte and three-byte files at cap7.','Delete the four-byte file and verify complete removal with total3.','Delete its same genuine reference again; verify unchanged peer metadata, exact readable peer bytes and complete remaining keys.'],
  'Totals7→3→3; removed allocation/chunks/manifest absent; peer[8,9,10] and original allocation/manifest remain; four remaining keys.',
  [afr(163,169),afr(204,219)],['D210','T202','T204','C206','I215'],
  'Primitive absent-delete idempotence D210/I215 and typed-record key deletion C206 do not establish actual allocation-based once-only aggregate release. T202 retains deduplicated reference counts and T204 uses SQL FK cascade. Capacity reuse was removed here to avoid duplicating F206.',2,1,2,0,7,7),
 ('F205','Prune only eligible unreferenced captures',
  'Production allocation scanning or later per-file deletion might ignore one eligibility predicate, miss the inclusive boundary, invalidate its outer cursor or reclaim protected bytes.',
  ['Capture old protected2-byte and old orphan3-byte files; obtain genuine bracketed allocation times.','Use at most32 waits of5ms to cross the orphan time, capture young4-byte file, and require actual young.createdAt > cutoff before pruning.','Prune with old reference protected at exact orphan timestamp; require only the three-byte orphan removed.','Release the old reference at same cutoff, then advance cutoff to young timestamp; verify exact survivor bytes, keys and totals after each step.'],
  'Genuine protectedAt<=cutoff<youngAt; orphan.createdAt=cutoff. Totals9→6→4→0; first survivors protected[11,12],young[31,32,33,34]; second only young; final only zero counter.',
  [afr(171,185),afr(204,219),afr(241,246)],['T207','T209','C201','C205','I211','I215'],
  'T207 transfers KV partitions into SQL and T209 ranks SQL revisions; I211/I215 list/delete R2 objects; C201/C205 buffer typed index groups. Here the actual ActionFileStore first buffers allocation handles then opens deletion lists, enforcing conjunctive live-reference and inclusive-age eligibility with genuine runtime timestamps. Missing witness is BLOCKED, not altered timestamps.',3,3,0,3,10,9),
 ('F206','Preserve captures through aggregate refusal',
  'An ordinary aggregate refusal could publish orphan rows or perturb earlier captures/accounting, or prevent a later valid exact-capacity capture.',
  ['Capture four and three bytes under per-file8 and aggregate8 limits.','Attempt a valid five-byte third capture and require the exact aggregate-limit Error.','Compare complete preexisting native key/value snapshot, independently established metadata/keys, and both original literal public reads.','Delete the first capture and repeat the valid five-byte payload; require exact surviving three-plus-five bytes and complete keys at counter8.'],
  'Before refusal total7; normal five-byte refusal leaves all seven native keys/values unchanged. After deleting four bytes and admitting five, exact total8 with two genuine complete captures.',
  [afr(88,123),afr(204,219)],['T201','T213','C202','I208'],
  'T201 refuses a conditional SQL reservation, T213 reduces synthetic chunk completeness, C202 rolls back typed-index uniqueness changes, and I208 refuses an R2 revision condition. Actual ActionFileStore must refuse a valid payload after hashing but before publishing allocation/chunks and remain usable. No malformed limit or corruption path is tested.',4,4,1,0,7,8),
]
source=(H/'cases.js').read_text()
cases=[]
for i,(id,title,hyp,trace,oracle,refs,nearest,distinct,captures,reads,deletes,prunes,entries,payload) in enumerate(specs):
 start=source.index('export async function '+id+'(')
 end=source.index('export async function '+specs[i+1][0]+'(') if i+1<len(specs) else source.index('export const CASES')
 body=source[start:end]
 calls=len(re.findall(r'\bt\.(?:eq|same|ok)\(',body))
 cases.append({'id':id,'title':title,'failure_hypothesis':hyp,'trace':trace,'oracle':oracle,
 'implementation':'cases.js:'+id,'body_line_start':source[:start].count('\n')+1,'body_line_end':source[:end].count('\n'),
 'source_refs':refs,'application_callsite_refs':[ref('os',gs,19,33),ref('os',gm,278,293),ref('os',gm,752,766)],
 'closest_existing_cases':nearest,'distinctness':distinct,'literal_assertion_call_sites':calls,
 'shared_assertion_helpers':['retained','smallBytes','absent'],'preconditions':preconditions,
 'schedule':'One exact GET /case/'+id+'; one fresh migrated DO and one ordinary same-deployment DO.fetch; all operations remain in that live request in written order.',
 'operation_counts':{'capture_attempts':captures,'reads':reads,'explicit_deletes':deletes,'prune_calls':prunes,'maximum_retained_native_entries':entries,'maximum_retained_payload_bytes':payload},
 'limits':limits,'cleanup':cleanup,'expected_exception_scope':'Only F206 ordinary valid aggregate-limit refusal. F205 missing genuine time separation is BLOCKED_WITNESS.',
 'coverage_class':'actual-pinned-os-module-over-direct-celld-native-storage-and-webcrypto',
 'classification':'functional-regression-candidate','promotion_candidate':True,'authored':True,'independently_reviewed':False,
 'runtime_status':'NOT_RUN','actual_runs':0,'runtime_passes':0})
save('manifest.json',{'schema':1,'wave':H.name,'authored':6,'independently_reviewed':0,'accepted_primary_static':0,'runtime_executions':0,'runtime_passes':0,'reserved_unused_ids':['F207','F208','F209','F210','F211','F212'],'cases':cases})
runtime_files=[
 'celld-os-project/celld/crates/celld/js/harness.js','celld-os-project/celld/crates/celld/js/storage_ops.rs','celld-os-project/celld/crates/celld/storage.rs','celld-os-project/celld/crates/celld/js/crypto.js','celld-os-project/celld/crates/celld/js/crypto.rs','celld-os-project/celld/crates/logic/lib.rs',
 'celld-os-stress/waves/sqlite-concurrency/cell-cases.js','celld-os-stress/waves/native-transform-stress/operations.js']
os_files=['raw/packages/gatekeeper-kit/src/action-files.ts','raw/LICENSE','raw/AGENTS.md',gs,gm,'SOURCE-MANIFEST.json','SNAPSHOT-SHA256SUMS','VERIFICATION.json']
overlap_files=['storage-sql-semantics/cases.js','atomic-accounting-semantics/cases.js','os-typed-storage-semantics/cases.js','r2-semantics/cases.js']
vendor_files=sorted(str(p.relative_to(H)) for p in (H/'vendor').rglob('*') if p.is_file())
save('source-pins.json',{'schema':1,'source_snapshot':BASE.name,'source_root':str(BASE),'os_root':str(OS),'overlap_root':str(CAMPAIGN),'os_commit':COMMIT,'binary_sha256':None,'runtime_status':'NOT_RUN','files':{name:sha(BASE/name) for name in runtime_files},'os_files':[pin(OS,n) for n in os_files],'overlap_files':[pin(CAMPAIGN,n) for n in overlap_files],'vendor_files':[pin(H,n) for n in vendor_files]})
downloads={
 'packages/gatekeeper-kit/src/positive-int.ts':'/opt/codex/downloads/aece9135-ca64-462d-a168-716ed7e4bc07/a7eaf546-0d1a-4255-91c0-c2b8a2ba16b3',
 'packages/gatekeeper-kit/src/kv.ts':'/opt/codex/downloads/aece9135-ca64-462d-a168-716ed7e4bc07/93f2865e-7a4c-428e-ade1-907b7f79d8bd',
 'packages/gatekeeper-kit/AGENTS.md':'/opt/codex/downloads/aece9135-ca64-462d-a168-716ed7e4bc07/98839c14-9d06-4870-9080-529a42945945'}
provenance=[]
for v in vendor_files:
 n=v.removeprefix('vendor/cloudflare-os/')
 entry={**pin(H,v),'official_blob_url':'https://github.com/cloudflare/cloudflare-os/blob/'+COMMIT+'/'+n,'commit':COMMIT,'modified':False}
 if n in downloads: entry.update({'method':'Normal GitHub Download raw file control in dedicated dot cloud browser tab4; completed path copied without transformation.','completed_download_path':downloads[n],'retrieved_date_utc':'2026-10-09'})
 else: entry.update({'method':'Byte-exact local copy from sealed historical source inventory.','copied_from':str(OS/'raw'/n)})
 provenance.append(entry)
save('provenance.json',{'schema':1,'commit':COMMIT,'source_modified':False,'downloaded_code_executed':False,'downloaded_code_compiled':False,'files':provenance,
 'license':'Apache-2.0','license_path':'vendor/cloudflare-os/LICENSE','license_sha256':'0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594',
 'import_graph':{'action-files.ts':{'runtime':['./positive-int'],'type_only':['./kv']},'positive-int.ts':{'runtime':[],'type_only':[]},'kv.ts':{'runtime':[],'type_only':[]}},
 'notice_scope':'Original notices preserved. Inspected exact-commit package root displayed no NOTICE; sealed inventory records repository root. No repo-wide absence claim.',
 'deferred_build':'Trusted preexisting esbuild, TypeScript erasure, no install/package scripts/vendor edits; separately authorize, record output bundle/config and tool identity in new staging.',
 'full_os_claim':False})
audit_sources=[{'root':'runtime',**pin(BASE,n)} for n in runtime_files[-2:]]+[{'root':'overlap',**pin(CAMPAIGN,n)} for n in overlap_files]
save('overlap-audit.json',{'schema':1,'scope':'Exact closest case bodies inspected across D/T/X/C/I families; no wrapper, payload-grid, primitive-CRUD or generic-quota credit. Broader files pinned for reviewer reproducibility.','sources':audit_sources,'cases':[{'id':c['id'],'nearest_existing':c['closest_existing_cases'],'distinctness':c['distinctness']} for c in cases],
 'additional_nearest_body_details':{'X023':'Native HMAC import copies public key before caller mutation; no ActionFileStore digest-plus-chunk retention.','C206':'Computed-key delete with stale non-key fields and repeated delete; no aggregate file allocation unit.','F204_F206':'Shared capture/read machinery earns no separate credit. F204 owns once-only release; F206 owns aggregate refusal then recovery. Capacity reuse appears only in F206.'},
 'not_authored':['Payload-size or chunk-count grid','Repeated direct CRUD/quota names','Corrupt/missing chunks or forged references','Malformed limits or integrity metadata','Authentication, replay, excluded stateless lifetime and denied guarded-core paths'],
 'runtime_status':'NOT_RUN'})
save('schedule.json',{'schema':1,'wave':H.name,'runtime_status':'NOT_RUN','ids':[c['id'] for c in cases],'requests':[{'method':'GET','path':'/case/'+c['id'],'max_calls':1,'fresh_roots':1} for c in cases],'schedule':'Strictly sequential outer requests; one fresh migrated DO and one public DO.fetch per case; await every original module promise inside the active request.','F201':'Direct call capture(view); synchronously fill backing; await same original promise; no scheduler hook.','F205':'Genuine timestamps only; at most32 five-ms waits then explicit strict young>cutoff witness. Missing witness is BLOCKED_WITNESS. Never alter Date.now/storage.','limits':limits,'cleanup':cleanup,'runtime_qualification':['Exact guarded runtime binary/source/build and immutable vendor/helper/bundle/config witnessed independently','Fresh owned private store and actual object/process identity','Complete externally enforced descendant/resource domain across PGIDs','HTTP200 plus ASSERTIONS_SATISFIED plus nonempty all-true assertions plus traceSettled plus matching object labels plus cleanup COMPLETE','Independent all-descendant termination and owned writable artifact removal'],'forbidden_substitutes':['Node executing cases','workerd','mock or in-memory storage','rewritten ActionFileStore','private harness hooks','unreviewed larger budgets'],'full_os_claim':False})
print('Generated metadata for six authored NOT_RUN cases; independent review remains pending.')
