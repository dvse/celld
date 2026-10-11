#!/usr/bin/env python3
"""Write source-only metadata from inspected pins and literal case descriptions; never run JS."""
import hashlib, json, pathlib, re
H = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
CAMPAIGN = H.parent
OS = CAMPAIGN / 'os-source-inventory/historical-4358072'
MODULE = 'packages/typed-storage/src/index.ts'
MODULE_SHA = '561111a1a0787d5158ddfa9df5c1910285b156906d874f5f58719a901e004c12'
LICENSE_SHA = '0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
def save(name, value): (H/name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
def records(root, names): return [{'path': p, 'sha256': sha(root/p), 'bytes': (root/p).stat().st_size} for p in names]
assert sha(OS/'raw'/MODULE) == MODULE_SHA == sha(H/'vendor/cloudflare-os'/MODULE)
assert sha(OS/'raw/LICENSE') == LICENSE_SHA == sha(H/'vendor/cloudflare-os/LICENSE')
source_pins = {
 'schema': 1, 'source_snapshot': BASE.name, 'binary_sha256': None,
 'runtime_status': 'NOT_RUN', 'source_root': str(BASE),
 'files': {x['path']: x['sha256'] for x in records(BASE, [
  'celld-os-project/celld/crates/celld/js/harness.js',
  'celld-os-project/celld/crates/celld/js/storage_ops.rs',
  'celld-os-project/celld/crates/celld/storage.rs',
  'celld-os-stress/waves/sqlite-concurrency/cell-cases.js',
  'celld-os-stress/waves/sqlite-concurrency/cases.js',
  'celld-os-stress/waves/sqlite-concurrency/manifest.json',
  'celld-os-stress/waves/sqlite-concurrency/source-pins.json',
 ])},
 'os_root': str(OS), 'os_commit': '4358072f8cb1bc9ddfb6ee11122e194c76cd71e0',
 'os_files': records(OS, ['raw/'+MODULE, 'raw/LICENSE',
  'raw/packages/workshop-backend/src/storage-schema/overseer-storage.ts',
  'raw/packages/workshop-backend/src/storage-schema/overseer-migrations.ts',
  'raw/packages/workshop-backend/src/overseer.ts',
  'SOURCE-MANIFEST.json', 'SOURCE-SHA256SUMS', 'INITIAL-FIVE-SOURCES.json', 'VERIFICATION.json']),
 'vendor_files': records(H, ['vendor/cloudflare-os/'+MODULE, 'vendor/cloudflare-os/LICENSE']),
 'overlap_root': str(CAMPAIGN), 'overlap_files': records(CAMPAIGN, [
  'storage-sql-semantics/cases.js', 'storage-sql-semantics/manifest.json',
  'atomic-accounting-semantics/cases.js', 'atomic-accounting-semantics/manifest.json',
  'facet-root-semantics/cases.js', 'facet-root-semantics/manifest.json',
  'kv-semantics/worker.js', 'kv-semantics/manifest.json']),
 'qualification': 'Exact OS module imported as production code over native direct-celld storage; actual application call sites establish relevance only, not whole-OS execution.'
}
save('source-pins.json', source_pins)
save('provenance.json', {
 'repository': 'https://github.com/cloudflare/cloudflare-os', 'commit': source_pins['os_commit'],
 'source_url': 'https://github.com/cloudflare/cloudflare-os/blob/'+source_pins['os_commit']+'/'+MODULE,
 'source_sha256': MODULE_SHA, 'local_original': 'os-source-inventory/historical-4358072/raw/'+MODULE,
 'vendor_path': 'vendor/cloudflare-os/'+MODULE, 'source_modified': False,
 'license': {'type':'Apache-2.0', 'path':'vendor/cloudflare-os/LICENSE', 'sha256': LICENSE_SHA,
  'source_url':'https://github.com/cloudflare/cloudflare-os/blob/'+source_pins['os_commit']+'/LICENSE'},
 'retrieval': 'Inventory worker inspected official pinned GitHub blob and used Download raw file. Author copied existing exact local bytes without transformations or new downloads.',
 'notice_scope': 'Pinned repository root listing has no NOTICE entry. No repo-wide statement about per-package notices is made.',
 'runtime_dependencies': [], 'build_inputs_missing': ['Separately authorized trusted esbuild capable of TypeScript syntax erasure', 'Exact guarded direct-celld executable and owned deployment supervisor'],
 'downloaded_code_executed': False, 'downloaded_code_compiled': False, 'runtime_executions': 0,
})

def ref(start, end): return {'root':'os', 'path':'raw/'+MODULE, 'line_start':start, 'line_end':end}
def caller(path, start, end): return {'root':'os', 'path':'raw/packages/workshop-backend/src/'+path, 'line_start':start, 'line_end':end}
items = [
 ('C201', 'Traverse buffered nonunique index pages',
  'Failure to buffer the outer native index cursor could invalidate it when child-group iteration starts; applying a record limit to the outer list would truncate a complete index-key group.',
  ['Seed four records spanning blue, green and red with overlapping memberships.', 'Fully consume limit-one and continuation reads, then dedupe and reverse reads.', 'Read two bounded reverse primary-key pages within blue.'],
  'First blue page a,b; next green page a,c; first two keys deduped a,b,c. Reverse two keys d,c,c,a; deduped d,c,a. Blue get pages b then a. Full records are literal expectations.',
  [ref(10,56),ref(74,81),ref(654,684)],
  [caller('overseer.ts',10641,10660),caller('storage-schema/overseer-storage.ts',1246,1268)],
  ['T029','D207','D208','K215','K216'],
  'T029 characterizes raw native iterator invalidation; D207/D208/K215/K216 cover low-level listing. This case exercises the actual OS module nested index traversal and documented key-count versus record-count semantics, with option permutations combined into one case.'),
 ('C202', 'Roll back conflicting index subscriptions',
  'A conflict in the second unique subscriber could retain writes made by the first subscriber, damage the old registration, or poison a later successful indexed replacement.',
  ['Seed two valid indexed registrations.', 'Attempt one ordinary conflicting replacement and one conflicting insertion using another existing mail key.', 'Compare exact entire native keyspace to original literal state.', 'Perform a valid replacement and compare exact native rows/indexes and reconstructed group records.'],
  'Both legal conflicts identify existing b; a,b and original unique/nonunique keys survive unchanged. Valid a becomes slug gamma/mail c/team blue/revision3; old alpha/a-mail/red keys absent, team counter2 unchanged, blue group has a,b.',
  [ref(419,436),ref(480,558),ref(563,580),ref(627,649)],
  [caller('storage-schema/overseer-storage.ts',1217,1229)],
  ['T016','T008','D220','T206'],
  'T016 is native SQL conflict with a held reader; T008/D220 are generic rollback APIs; T206 is a SQL partial-index UPSERT. Here byte-exact OS subscribers execute several real sync-KV index changes inside their own transaction and a later subscriber rejects a valid business uniqueness conflict.'),
 ('C203', 'Transition nullable multikey memberships',
  'Scalar, array and null membership transitions could remove retained intersections, leak last-member group rows, retain nullable unique aliases, or reuse retired group IDs.',
  ['Seed two pending draft records, one with no unique alias.', 'Move a to scalar draft and check shared group retention.', 'Move a through scalar-to-array-to-null and b to scalar; check reclaimed groups.', 'Recreate a array and alias memberships; verify the literal complete native keyspace.'],
  'Draft group1 is retained. First pending group0 and final group2 are reclaimed; counter remains3. Recreated a memberships allocate pending3/final4, counter5; b remains draft1 and beta; a regains alpha.',
  [ref(487,553),ref(563,580),ref(627,649)],
  [caller('storage-schema/overseer-storage.ts',1196,1205),caller('storage-schema/overseer-storage.ts',1217,1229),caller('storage-schema/overseer-storage.ts',1256,1268)],
  ['T203','T206','T215'],
  'Those cases maintain SQL triggers, partial SQL indexes or FTS postings. This case executes the actual OS addIndexSubscriber array/scalar/null delta algorithm and nonunique child reclamation; actual action history schema returns both scalar and array index keys.'),
 ('C204', 'Rebuild newly declared storage indexes',
  'A late index migration could omit old records, leave stale child rows on repeated rebuild, reset the persistent allocation counter, or make the next indexed edit inconsistent.',
  ['Persist two records under an unindexed schema; stop using that schema.', 'Declare unique slug and nonunique tags and observe empty new indexes before writes.', 'Invoke both production rebuild methods and version stamp inside one typed transaction.', 'Rebuild again, checking counter and fresh child IDs.', 'Perform a post-migration indexed edit and compare literal complete storage.'],
  'First rebuild returns migration-v2 with version2/counter2 and blue a,b/red b. Second rebuild has counter4 and groups blue2/red3, no old children. Edit b yields slug second-v2/tags green4, counter5; a stays blue2 and version2 persists.',
  [ref(65,71),ref(85,90),ref(373,385),ref(606,615),ref(705,714),ref(740,743)],
  [caller('storage-schema/overseer-migrations.ts',231,246)],
  ['T208','T008','D211'],
  'T208 explicitly rebuilds a synthetic SQL ancestry relation; D211 clears raw storage; T008 nests raw transactions. This is the production module migration API, including its physical child sweep and intentionally retained allocation counter.'),
 ('C205', 'Delete buffered indexed groups safely',
  'Deleting a nonunique group while index subscribers and application callbacks open native list cursors could invalidate the unbuffered member traversal, skip selected records, or leave secondary postings.',
  ['Seed four records, red a,b,c and overlapping shared a,c,d; d is blue.', 'Subscribe an application remove callback that fully reads the shared index and stores an audit row.', 'Invoke production tags.delete(red); unsubscribe in finally.', 'Compare deletion receipts, surviving full record, full audit rows and complete secondary native keyspace.'],
  'Delete receipts3 then0; only d/four/[blue,shared] survives; audits a/one,b/two,c/three. Only slug four and blue2/shared1 child d remain; group counter3 persists.',
  [ref(442,456),ref(638,649),ref(687,703)],
  [caller('overseer.ts',5173,5179)],
  ['T029','T027','D210','T207'],
  'T029 triggers raw iterator invalidation, D210 is raw batch deletion, T027 restores a raw delete and T207 extracts a synthetic partition. This executes production nonunique delete buffering across real index-subscriber native list calls plus an ordinary read-and-audit callback. No callback timing oracle is asserted.'),
 ('C206', 'Delete records through computed keys',
  'deleteRecord could derive the wrong computed key or remove indexes using stale caller fields instead of the actual stored old record.',
  ['Persist two revisions keyed by document/revision with unique label and nonunique document indexes.', 'Delete revision1 using a caller record with the same key fields but obsolete label/bytes.', 'Repeat deletion and compare complete surviving record and native main/index keyspace.'],
  'Receipts true,false; only memo/2 label final bytes7 survives. Draft posting and memo/1 child absent; document group0/counter1 and final posting remain exactly.',
  [ref(128,135),ref(403,409),ref(442,460)],
  [caller('overseer.ts',2341,2355),caller('storage-schema/overseer-storage.ts',1350,1362)],
  ['D210','C205'],
  'D210 takes raw keys; C205 deletes every member of an index group. This documented helper must read only computed primary-key fields from a caller record while removing actual stored index data, including when non-key fields are stale.'),
 ('C207', 'Preserve storage across schema renames',
  'Renaming schema properties could accidentally create new physical main/index/singleton keys or fail to discover original persisted locations despite explicit storage aliases.',
  ['Persist items:a, its slug index and revision singleton under original neutral names.', 'Stop using original schema, then declare documents with storageName items and generation with storageKey revision.', 'Read original records, update through renamed code in a typed transaction, and compare exact physical keys.', 'Recreate the renamed schema object and re-read committed values.'],
  'Renamed read sees saved record and revision4. Update leaves only items.slug:two=a, items:a with edited record and revision5; no documents/generation shadow keys. Fresh schema instance sees edited record and5.',
  [ref(197,216),ref(236,239),ref(758,801)],
  [caller('storage-schema/overseer-storage.ts',1148,1148)],
  ['Z206','Z208','D204'],
  'Z206/Z208 test distinct facet scopes and D204 sync/async API coherence. This tests explicit same-storage migration aliases on one native DO with sequential schemas only. The actual singleton alias call site establishes relevance; storageName uses the documented module contract, with no concrete application caller claimed.'),
]
source = (H/'cases.js').read_text()
limits = {'max_external_case_http_requests':1,'max_frontend_do_fetches':1,'max_created_do_roots':1,'max_outbound_public_network_requests':0,'max_native_storage_entries':32,'max_rows_per_fully_consumed_iterator':64,'max_native_list_calls':64,'max_record_payload_bytes':1024,'max_total_logical_payload_bytes':8192,'max_schema_instances':3,'max_sync_transaction_depth':3,'max_application_remove_callbacks':3,'precondition_deadline_ms':1000,'trace_deadline_ms':5000,'cleanup_deadline_ms':2000,'outer_http_deadline_seconds':10,'outer_case_process_deadline_seconds':15,'outer_wave_deadline_seconds':120,'outer_rss_bytes':1073741824,'max_owned_domain_processes':32,'max_owned_writable_bytes':134217728,'descendant_supervision':'All proven-owned dev, trusted bundler and runtime descendants across PGIDs; prefer one enforceable cgroup/ownership domain; no single-process-group cleanup assumption','writable_quota_scope':'All generated bundles, staging config, logs, temporary files and private store; externally supplied read-only binaries/source are not copied into the writable domain'}
cases=[]; overlap=[]
for idx,(cid,title,hypothesis,trace,oracle,refs,callers,nearest,distinctness) in enumerate(items):
 end = source.index('export function '+items[idx+1][0]+'(') if idx+1<len(items) else source.index('export const CASES')
 body = source[source.index('export function '+cid+'('):end]
 count=len(re.findall(r'\bt\.(?:eq|same|ok)\(',body))
 cases.append({'id':cid,'title':title,'failure_hypothesis':hypothesis,'trace':trace,'oracle':oracle,
  'implementation':'cases.js:'+cid,'source_refs':refs,'application_callsite_refs':callers,'closest_existing_cases':nearest,'distinctness':distinctness,
  'literal_assertion_call_sites':count,'preconditions':['Exact reviewed OS source, Apache-2.0 license and guarded direct-celld source/build/bundle pins.','Fresh disposable SQLite-backed DO with native kv and transactionSync; no user data.','Externally enforceable resource and ownership domain includes the complete proven-owned dev/bundler/runtime descendant tree across PGIDs and all generated writable artifacts.','Trusted future bundler must preserve imported production semantics; no mocked storage or runtime fallback.'],
  'schedule':'One exact GET /case/'+cid+'; one fresh named DO and one ordinary same-deployment DO.fetch; all operations synchronous in written dependency order inside that active request.',
  'limits':limits,'cleanup':['Application subscriptions removed in finally where present.','Trace must settle before cleanup; unsettled trace requires external owned-process teardown only.','Open and fully exhaust one public sync-KV list to replace any abandoned native list for this scope; never next() after done.','DeleteAll only this fresh owned DO; assert native KV empty. External supervisor must verify termination of the complete proven-owned dev/bundler/runtime descendant tree across PGIDs, then remove only its owned staging/bundle/log/temp/store files; a single process-group cleanup is insufficient.'],
  'expected_exception_scope':'Only ordinary valid uniqueness conflicts in C202; no malformed inputs, corruption, authentication, forgery, replay, capability lifetime or injected faults.',
  'coverage_class':'actual-pinned-os-module-over-direct-celld-native-storage','classification':'functional-regression-candidate','promotion_candidate':True,
  'authored':True,'independently_reviewed':False,'runtime_status':'NOT_RUN','actual_runs':0,'runtime_passes':0})
 overlap.append({'id':cid,'closest_cases':nearest,'decision':'RETAIN_PENDING_INDEPENDENT_BODY_REVIEW','mechanism_delta':distinctness})
save('manifest.json', {'schema':1,'wave':'os-typed-storage-semantics','authored':7,'independently_reviewed':0,'accepted_primary_static':0,'runtime_executions':0,'runtime_passes':0,'cases':cases})
save('overlap-audit.json', {'schema':1,'baseline_read':['T001–T032 native storage transaction/cursor wave','D201–D220 ordinary native storage/SQL wave','T201–T215 synthetic atomic-accounting wave','Z201–Z219 accepted facet cases','K201–K220 env-KV cases'],'proposed_then_retired':[{'id':'C208','reason':'Undocumented observer timing characterization; no primary credit and no body authored.'}],'reserved_unused_ids':['C209','C210','C211','C212','C213','C214','C215','C216','C217','C218','C219'],'cases':overlap,'counting_rule':'Seven independently authored mechanism-level candidates; options, retries, raw receipts and multiple assertions add no separate case credit. Independent review remains external.'})
print('Wrote source-only metadata for seven candidates; imported JavaScript/TypeScript execution: zero.')
