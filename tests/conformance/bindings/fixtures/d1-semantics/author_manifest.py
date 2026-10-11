#!/usr/bin/env python3
"""Build source-only case metadata from handcrafted descriptions and static slices."""
import hashlib, json, pathlib, re
HERE=pathlib.Path(__file__).resolve().parent
ARCHIVE=pathlib.Path('/workspace/shared/celld-recovered/celld-direct-source-v0.6.2-8d27-guard-20261009')
CORE='celld-os-project/celld/'
H=CORE+'crates/celld/js/harness.js'
S=CORE+'crates/celld/storage.rs'
SOURCES={
 'api':(CORE+'docs/services/d1.md',[[1,87]]),
 'bind':(H,[[8283,8326]]),
 'prepared':(H,[[8328,8387]]),
 'shape':(H,[[8389,8401]]),
 'session':(H,[[8403,8446]]),
 'database':(H,[[8448,8491]]),
 'server':(H,[[8196,8279]]),
 'bind_engine':(S,[[2343,2385]]),
 'row_codec':(S,[[2395,2478]]),
 'drain':(S,[[2491,2576]]),
 'parser':(S,[[2625,2729]]),
 'metadata':(S,[[2731,2828]]),
 'batch_exec':(S,[[2990,3139]]),
 'authorizer':(S,[[477,486],[518,679]]),
 'deploy':(CORE+'crates/celld/deploy.rs',[[1199,1257],[1465,1513]]),
 'fleet':(CORE+'crates/celld/fleet.rs',[[846,861]]),
 'bootstrap':(CORE+'crates/celld/js/bootstrap.rs',[[659,664]]),
}
DATA=[
('E201','Keep rebound prepared statements independent','Reuse a parameterized lookup safely for several application records.',
 ['Seed three label rows.','Prepare one lookup; bind id 1, rebind that result to 2, and bind the original template to 3.','Execute blue, red, green, then red again and assert distinct binding objects and exact values.'],
 ['seed lookup','blue execution','red execution','green execution','red reuse'],
 ['bind','prepared','metadata'],'bind constructs a new D1PreparedStatement with independently mapped scalar params; each first() dispatch uses that statement params.',
 'Public D1 immutable bind object and repeated full-result calls; unlike T011 direct DO busy cached cursor parameters and cross-request overlap.'),
('E202','Address repeated numbered placeholders','Reuse one invoice quantity in several output fields without shifting later parameters.',
 ['Create one-row lookup.','Bind four arguments to a statement whose numbered placeholders appear in order ?2,?1,?2,?3,?4.','Require the exact quantity, SKU, repeated quantity and null discount.'],
 ['seed numbered lookup','numbered lookup'],['bind','metadata'],'SQLite parameter count is validated once; values bind to offset+1, so repeated ?2 uses parameter index 2 and not its occurrence count.',
 'Indexes and repeated placeholders exercise mapping independently of E201 statement-object immutability.'),
('E203','Round-trip application scalar settings','Persist booleans, optional nulls, Unicode text, empty text and finite numbers without silent coercion to NULL.',
 ['Create an affinity-free settings table.','Batch two fixed rows with true/false flags, null, Unicode/newline/empty text, and finite numbers.','Read values and SQL types in id order and compare exact rows.'],
 ['create settings','save settings','load settings'],['bind','bind_engine','row_codec','database'],'The public client converts booleans to 1/0, preserves finite numbers/text/null, and the engine maps those JSON values to corresponding SQLite values.',
 'One scalar codec case with discriminating types, not separate credit for each input value.'),
('E204','Copy and encode binary bind sources','Store binary attachments while callers reuse mutable typed buffers after binding.',
 ['Create a binary table.','Bind an ArrayBuffer, Uint16Array, Int8Array and fixed byte array to four inserts.','Mutate only the ArrayBuffer and typed-array inputs before dispatch.','Batch inserts; raw-read exact byte arrays and SQLite BLOB types.'],
 ['create binary store','save binary values','load binary values'],['bind','bind_engine','row_codec','database'],'ArrayBuffer is copied to bytes and typed views are copied through Uint8Array.from(element values) at bind time; result BLOBs serialize as byte arrays.',
 'Byte serialization and bind-time typed-buffer copying on the public D1 wire are distinct from direct DO T019 raw-window cursor binding. No snapshot promise is made for mutable plain byte arrays.'),
('E205','Keep all and run result semantics aligned','Let data-access helpers use either public execution method for reads and DML RETURNING.',
 ['Create an empty table.','Insert one row through run and one through all, each with RETURNING.','Assert success and exact returned rows.','Execute the same ordered SELECT with all and run and compare exact results.'],
 ['create method parity table','run returning insert','all returning insert','all selection','run selection'],['prepared','row_codec'],'run delegates to all, which maps engine columns/rows to the same successful object result shape.',
 'Method alias equivalence includes both write-returned rows and reads, not just another SELECT-value variant.'),
('E206','Distinguish first row scalar and absence','Handle nullable application fields and absent records using the first API.',
 ['Seed a null note followed by a later row.','Read ordered first row, its id scalar, and its null note scalar.','Execute a zero-row selection through first and first(id).'],
 ['seed first selection','first object','first scalar','first null column','empty first object','empty first scalar'],['prepared','shape','drain'],'first shapes one retained row, returns the selected existing column, and returns null immediately when the engine returned no rows.',
 'Public row/scalar/null contract; unlike T015 exhausted live SQL cursor reuse, no cursor or cross-request handle exists.'),
('E207','Preserve export headings and column order','Produce ordered positional exports including a headings-only empty export.',
 ['Seed two rows including a null label.','Read selected caption/record_id columns through raw and raw(columnNames).','Read an empty selection in both forms.'],
 ['seed export','raw data','raw headings','empty raw','empty raw headings'],['prepared','row_codec','metadata'],'raw returns positional rows unchanged, or prepends engine columns even when there are no rows.',
 'Static positional export and zero-row metadata contract, not T012/T013 live shared cursor iteration.'),
('E208','Preserve own properties for special column labels','Accept report column labels that coincide with JavaScript prototype members.',
 ['Create one source row.','Select literal __proto__, constructor and toString aliases.','Assert exact own enumerable keys and values, then select __proto__ through first(column).'],
 ['seed special labels','special object result','first special column'],['shape','prepared'],'Object.fromEntries defines an own property for every column label; first(column) reads that shaped own property.',
 'Own-property integrity differs from E209 duplicate-name information loss; no prototype manipulation or malformed input is attempted.'),
('E209','Retain duplicate columns in raw projections','Recognize when a join report needs positional data rather than object-key projection.',
 ['Create one source row.','Select two amount columns followed by other.','Compare all object projection, first(amount), and raw with headings.'],
 ['seed duplicate labels','duplicate object selection','duplicate scalar selection','duplicate positional selection'],['shape','prepared'],'Object.fromEntries collapses duplicate labels with the last value, while raw preserves original duplicate columns and values.',
 'One duplicate-label shaping case; all/first/raw views do not count as independent authored cases.'),
('E210','Run successful schema and data dependencies in batch','Bootstrap an application table and use its new data within one submitted batch.',
 ['Batch create table, parameterized insert, read, parameterized update and read in that exact order.','Require five successful results and exact intermediate/final rows.','Read after batch return to verify the committed final value.'],
 ['schema write read batch','committed batch read'],['database','server','batch_exec','metadata'],'The engine prepares and steps statements sequentially on one connection and commits the successful batch before returning one result per statement.',
 'Valid dependency and commit completeness only; this does not prove rollback or atomic visibility to a concurrent observer.'),
('E211','Snapshot mutation metadata per batch statement','Use write receipts to attribute affected rows and insert IDs to individual batched operations.',
 ['Create ledger table.','Batch two explicit-rowid inserts, one real update, one unmatched update and an ordered read.','Compare exact per-statement changes, rows_written, last_row_id, changed_db and final rows.'],
 ['create metadata ledger','snapshot metadata batch'],['database','batch_exec','metadata'],'Each d1_run_prepared snapshots total_changes/schema before its own execution and reads connection counters before the next batch item; reads explicitly reset changes and rowid.',
 'Per-item attribution cannot be established by E210 result ordering. Read counter reset is a celld source difference, not universal Cloudflare behavior.'),
('E212','Parse exec statements without splitting SQL text','Apply a small application schema script containing comments, quoted semicolons and multiline SQL.',
 ['Execute four complete statements with line/block comments, quoted semicolons, an escaped quote, and no final semicolon.','Assert count 4, exact public exec keys and well-formed duration.','Read exact committed text values.'],
 ['parse multi statement script','read parsed script effects'],['server','parser','batch_exec'],'SQLite sqlite3_prepare_v2 and tail walking determine statement boundaries; exec counts stepped statements, discards trivia, and accepts the final complete statement without semicolon.',
 'Valid tokenizer/statement-count contract differs from generic multi-write batch behavior; source count semantics intentionally differ from Cloudflare line counting.'),
('E213','Drain row-producing exec statements before return','Run initialization scripts that contain RETURNING without leaving some mutations incomplete.',
 ['Exec create table, a three-row INSERT RETURNING, a three-row UPDATE RETURNING and a SELECT.','Require count 4 and no public results field.','Read the exact three updated rows after exec returns.'],
 ['exec returning script','read exec completion'],['server','parser','drain','batch_exec'],'Worker exec requests rows:false, so keep=0 discards output but steps every row to SQLITE_DONE before commit.',
 'Zero-row retention for exec is distinct from E216 first retaining one row; neither test assumes RETURNING order.'),
('E214','Reset readonly metadata after an acknowledged write','Avoid showing a previous write receipt as if a later application read performed that write.',
 ['Create table and insert rowid 41 through run.','Assert exact write counters.','Read the row; assert zero read mutation counters, source-primary routing markers and nonexact duration/size types.'],
 ['create read metadata table','write before readonly','readonly after write'],['prepared','metadata'],'Readonly statements get (last_row_id,changes)=(0,0); metadata publishes served_by=celld, served_by_region=local and served_by_primary=true.',
 'Cross-call read metadata reset and service attribution; E211 covers within-batch snapshots. No exact elapsed time, page size or scan count is asserted.'),
('E215','Distinguish schema changes from no-op writes','Use changed_db to decide whether successful schema maintenance actually altered the database.',
 ['CREATE a table through a prepared run and inspect metadata.','UPDATE with a valid unmatched predicate and inspect metadata.','DROP the empty table through run and inspect metadata.'],
 ['schema mutation','no matching update','schema removal'],['metadata','authorizer'],'changed_db compares total row writes and schema cookie while a writable no-op with neither delta is false.',
 'Schema-cookie evidence is independent of E211 row DML counts. Does not rely on connection changes/last_row_id after DDL.'),
('E216','Complete mutations behind first RETURNING','Use a single returned row as a receipt without accidentally stopping a multi-row update.',
 ['Seed exactly three rows.','Execute UPDATE of all rows with RETURNING through first.','Require one valid id/value pair from the known set, without ordered-return assumptions.','Read all rows in explicit id order and require all updates.'],
 ['seed first returning','first mutation result','verify all returning effects'],['prepared','drain','metadata'],'first sets keep=1, but d1_step_to_done continues stepping to SQLITE_DONE and merely drops later returned rows.',
 'Successful write completion behind first is distinct from E206 SELECT cardinality and E213 exec keep=0.'),
('E217','Advance and resume independent query sessions','Carry a read-session bookmark between application components while independent sessions retain their own state.',
 ['Seed one row.','Create first-primary and default sessions; require null initial bookmarks.','Read through the first session, require celld:primary and unchanged other session.','Create a new session from the returned bookmark and read exact data again.'],
 ['seed session read','session read','resumed session read'],['session','database'],'Constraints begin with null bookmarks; each successful _query changes only that session bookmark to the constant celld:primary; supplied bookmark is retained initially.',
 'Session-local query-bookmark lifecycle and resume, explicitly celld source behavior with no replica/consistency-order claim.'),
('E218','Advance a session after successful batch commit','Use one session for a dependent write batch and its subsequent application read.',
 ['Create an empty table and a first-unconstrained session.','Batch insert, increment and read using statements prepared by that session.','Require exact batch results and bookmark advancement.','Read exact final data from both the base binding and the same session.'],
 ['create session batch table','session batch','base read after session batch','session read after batch'],['session','database','batch_exec'],'Session.batch calls the underlying database batch then advances its own bookmark; all session calls route to the same underlying database.',
 'The separate session.batch advancement path is not exercised by E217 queries or E210 base database batches.'),
('E219','Share configured database aliases and isolate identities','Let renamed bindings share one resource while another tenant database uses the same table and key safely.',
 ['Seed the same table/key with different labels in DB and OTHER identities.','Read through ALIAS configured with the DB id but another name.','Write through ALIAS, then read DB and OTHER separately.'],
 ['seed shared identity','seed separate identity','alias read','alias write','shared read after alias','isolated read'],['deploy','fleet','bootstrap','database'],'fleet chooses database_id as identity and bootstrap passes it into the public client; identical ids resolve one cell, different ids another.',
 'Public configuration identity aliasing/isolation; not a direct DO scope or provider-origin test. Cleanup owns one table per actual database identity.'),
('E220','Resolve omitted IDs through database names','Preserve a celld-only database identity when an application later introduces an explicit matching ID.',
 ['Seed FALLBACK, whose database_id is omitted.','Read through a second omitted-id binding with the same database_name.','Write through EXPLICIT_NAME whose database_id equals that fallback name.','Read both original omitted-id bindings.'],
 ['seed name identity','same name no-id read','explicit identity write','fallback after explicit write','fallback alias after explicit write'],['deploy','fleet','bootstrap','database'],'fleet uses database_name only when database_id is absent; the resulting identity string equals an explicit id with the same bytes.',
 'Fallback precedence and fallback-to-explicit identity convergence differ from E219 explicit-id aliasing. This is celld configuration behavior, not Cloudflare provisioning behavior.'),
]

CROSS_WAVE={
 'E203': {'neighbors':['D212'],'distinction':'D212 binds native SQL scalars and DataView and returns native ArrayBuffer; E203 exercises public D1 boolean normalization, JSON transport, SQL null and typed scalar persistence across batch/read dispatches.'},
 'E204': {'neighbors':['D212'],'distinction':'D212 observes a native DataView byte window and ArrayBuffer output. E204 tests the independently implemented D1 bind serializer: Uint16Array/Int8Array element truncation and typed-source copying at bind, then JSON byte-array output. Those are different encoding rules, not a new byte sample.'},
 'E205': {'neighbors':['D214'],'distinction':'D214 exhausts a native SQL RETURNING cursor and checks terminality. E205 compares public D1 run/all method aliases, success/result envelopes and RETURNING on both, with no exposed cursor.'},
 'E209': {'neighbors':['D213'],'distinction':'D213 has the same outward last-duplicate versus positional contract on native SqlStorageCursor paths. E209 independently targets D1 __d1Shape/Object.fromEntries and public raw/first/all across engine JSON rows. This is the closest cross-wave semantic overlap; independent review must decide whether separate public-surface implementation coverage merits distinct credit.'},
 'E212': {'neighbors':['D216','D217'],'distinction':'D216/D217 use sql.ingest with remainder/rowsWritten/statementCount. E212 targets the separate D1 SQLite tail walker, public count/duration-only envelope, comments and a complete final statement without semicolon, then post-return committed contents. It makes no ingest or streaming-suffix claim.'},
 'E213': {'neighbors':['D219'],'distinction':'D219 drains read SELECT rows in sql.ingest before later writes. E213 uses public D1 exec(rows:false) with both multirow INSERT RETURNING and UPDATE RETURNING and checks all effects after its successful transaction-completing response plus no public results field.'},
 'E216': {'neighbors':['D214'],'distinction':'D214 explicitly drains all native cursor receipts; E216 asks D1 first() to retain one receipt while the engine must still step the entire mutation. A native cursor completion test does not exercise that keep=1 boundary.'},
}

def digest(data): return hashlib.sha256(data).hexdigest()
def write(name,value): (HERE/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
worker=(HERE/'worker.js').read_text()
lines=worker.splitlines()
starts=list(re.finditer(r'^  (E\d{3}): \{',worker,re.M))
cases=[]
for i, (cid,title,intent,trace,labels,refs,oracle,distinct) in enumerate(DATA):
    start=starts[i].start(); end=starts[i+1].start() if i+1<len(starts) else worker.index('\n};\n\nfunction context',start)
    first=worker[:start].count('\n')+1; last=worker[:end].count('\n')
    body='\n'.join(lines[first-1:last])+'\n'
    assertion_lines=[line.strip() for line in body.splitlines() if 'c.eq(' in line]
    assertions=[re.search(r', "([^"\n]+)"\);$',line).group(1) for line in assertion_lines]
    calls=len(re.findall(r'\bc\.(?:exec|batch|all|run|first|raw)\(',body))
    assert calls==len(labels),(cid,calls,len(labels))
    source_refs=[]
    for key in ['api']+refs:
        path,ranges=SOURCES[key]; source_lines=(ARCHIVE/path).read_text().splitlines()
        source_refs.append({'key':key,'path':path,'line_ranges':ranges,'slices_sha256':[digest(('\n'.join(source_lines[a-1:b])+'\n').encode()) for a,b in ranges]})
    owned=[{'binding':'DB','database_identity':'d1-next-id-a','table':f'd1_next_{cid.lower()}'}]
    if cid=='E219': owned.append({'binding':'OTHER','database_identity':'d1-next-id-b','table':f'd1_next_{cid.lower()}'})
    if cid=='E220': owned=[{'binding':'FALLBACK','database_identity':'d1-next-name','table':'d1_next_e220'}]
    cases.append({'id':cid,'title':title,'status':'NEWLY_AUTHORED_UNREVIEWED_NOT_RUN','family':'d1-semantics','artifact':'worker.js','entrypoint':'GET /case/'+cid,'fixture_line_range':[first,last],'fixture_slice_sha256':digest(body.encode()),'intent':intent,'application_relevance':intent,'sut':'direct celld only','surface':'public env D1 binding APIs only','source_refs':source_refs,'fixed_finite_trace':trace,'oracle':{'kind':'PINNED_DIRECT_CELLD_SOURCE_CONTRACT','claim':oracle,'assertions':assertions,'executable_assertion_source':assertion_lines,'successful_assertion_count':len(assertions),'qualification':'All expectations are against the exact pinned direct celld source. Metadata resets, primary service markers, stable bookmark, exec counts and database-name fallback are deliberately not universal Cloudflare claims. No runtime or workerd comparison was performed.'},'schedule':{'case_requests':1,'setup_binding_calls_exact_on_success':len(owned),'main_phase_binding_calls_exact_on_success':calls,'main_phase_dispatch_labels_in_order':labels,'cleanup_binding_calls_exact_on_success':2*len(owned),'maximum_in_flight_public_calls':1,'ordering':'Every public dispatch is awaited before the next; no overlapping requests, timers, retries or random schedules. prepare/bind/session constructors/bookmark access are synchronous local operations.','retries':0,'restarts':0,'faults':0},'limits':{'public_dispatches_per_phase_enforced':32,'maximum_rows_in_any_fixture_table':4,'maximum_application_tables':len(owned),'maximum_bound_parameters_per_statement':5,'maximum_batch_statements':5,'maximum_exec_statements':4,'maximum_SQL_UTF8_bytes_per_dispatch':1024,'maximum_bound_scalar_or_blob_bytes':64,'external_total_request_deadline_seconds':30,'external_response_capture_bytes':1048576,'no_internal_Promise_race_timeout':True},'owned_resources':owned,'cleanup':{'preflight':'For each declared physical identity/table, SELECT sqlite_schema by exact bound name and require absence before claiming ownership. Refuse pre-existing objects and never drop them. A fresh isolated store and serial runner remain mandatory.','finally':'For every claimed resource independently, DROP TABLE IF EXISTS and read sqlite_schema by exact name; require null and no cleanup errors. Deduplicate alias identities by owning only the canonical binding.','on_stall':'The separately reviewed adapter must enforce the total request deadline, stop only the owned invocation and, if request cancellation cannot be proved, the owned celld process group; preserve evidence then discard only its disposable store. No cleanup success may be inferred after timeout.','wave_end':'Stop the owned celld group and discard its disposable store even if every finally check succeeds.'},'distinctness':distinct+(' Cross-wave: '+CROSS_WAVE[cid]['distinction'] if cid in CROSS_WAVE else ''),'cross_wave_overlap':CROSS_WAVE.get(cid),'limits_of_evidence':['Source-backed assertion candidate only; zero execution, zero review acceptance.','No cross-node, restart, durability-loss, fault, rollback, malformed-input, authorization or guarded G/N/P/J122 claim.','Successful batch dependencies do not establish concurrent-observer atomicity.','Finite source traces do not substitute for an independently enforced outer deadline and owned teardown.'],'review_accepted':False,'runtime_execution_count':0})
write('manifest.json',{'schema_version':1,'family':'d1-semantics','status':'NEWLY_AUTHORED_UNREVIEWED_NOT_RUN','authored_case_count':len(cases),'review_accepted_cases':0,'runtime_executed_cases':0,'runtime_pass_cases':0,'source_archive':ARCHIVE.name,'source_contract':'PINNED_DIRECT_CELLD_SOURCE_CONTRACT','authoring_scope':'Added only d1-semantics artifacts; immutable source, historical corpus and sibling waves unchanged. Static-only checks never award runtime credit.','cases':cases})
pinpaths=sorted(set(path for path,ranges in SOURCES.values())|{'BUILD_AND_TEST.md',CORE+'docs/testing.md',CORE+'examples/d1/index.js',CORE+'examples/d1/wrangler.jsonc',CORE+'crates/celld/engine_api.rs','celld-os-stress/SOURCE-FILES.json','celld-os-stress/COUNTS.json','celld-os-stress/waves/sqlite-concurrency/cell-cases.js','celld-os-stress/waves/sqlite-concurrency/author_manifest.py','celld-os-stress/waves/sqlite-concurrency/manifest.json'})
write('source-pins.json',{'archive':str(ARCHIVE),'purpose':'Immutable source and actual overlap inputs; hashes establish byte identity, never execution.','pins':[{'path':path,'sha256':digest((ARCHIVE/path).read_bytes()),'bytes':(ARCHIVE/path).stat().st_size} for path in pinpaths]})
scanned=[]; matches=[]
pattern=re.compile(r'\bd1\b|d1_databases|withSession|getBookmark',re.I)
for root in [ARCHIVE/'celld-os-stress',ARCHIVE/'celld-os-project/tests']:
    for path in sorted(root.rglob('*')):
        if not path.is_file(): continue
        try: text=path.read_text()
        except UnicodeDecodeError: continue
        scanned.append(path.relative_to(ARCHIVE).as_posix())
        hits=[i for i,line in enumerate(text.splitlines(),1) if pattern.search(line)]
        if hits: matches.append({'path':path.relative_to(ARCHIVE).as_posix(),'line_numbers':hits})
write('overlap-audit.json',{'status':'SOURCE_AUDIT_ONLY_NOT_INDEPENDENT_REVIEW','scanned_roots':['celld-os-stress','celld-os-project/tests'],'scan_pattern':pattern.pattern,'text_files_scanned':len(scanned),'scanned_path_list_sha256':digest(('\n'.join(scanned)+'\n').encode()),'public_D1_text_matches':matches,'actual_case_bodies_read':['celld-os-stress/waves/sqlite-concurrency/cell-cases.js','celld-os-project/celld/examples/d1/index.js'],'nearest_existing_cases':[{'ids':['T011','T015','T018','T024'],'path':'celld-os-stress/waves/sqlite-concurrency/cell-cases.js','lines':[15,19,22,28],'relationship':'These are direct DO SQL prepared/cursor/transaction-view/schema-cache behaviors, not public D1 binding objects, wire row shapes, sessions or D1 metadata. Their substantive overlap is recorded per candidate; none are relabeled or recounted.'},{'ids':['T012','T013','T019','T020','T021'],'path':'celld-os-stress/waves/sqlite-concurrency/cell-cases.js','relationship':'Raw cursor iteration, typed SQL cursor BLOB binds, direct root scope isolation and connection-delta characterization are nearby concepts; new cases use materially different public D1 request/result contracts and do not claim cursor/concurrency coverage.'}],'source_example':'The source D1 guestbook uses ordinary exec/prepare/bind/run/first/all but has no assertion-bearing corpus case IDs. New cases are not copies of its GET/POST workflow.','limits':['Search only the restored available text corpus; private/omitted tests may exist.','No claim these are the first D1 tests globally; independent review must decide distinct accepted credit.','No restored corpus mutation or duplicate case credit.'],'new_candidate_ids':[c['id'] for c in cases],'accepted_new_case_credit':0,'current_sibling_wave_audited':{'family':'storage-sql-semantics','path':'../storage-sql-semantics/cases.js','sha256':digest((HERE.parent/'storage-sql-semantics/cases.js').read_bytes()),'cases_read':['D212','D213','D214','D216','D217','D219'],'source_lines':[[113,121],[124,128],[131,137],[149,152],[155,160],[173,177]],'case_comparisons':CROSS_WAVE,'credit_qualification':'Naming a separate public API is not by itself a distinctness proof; independent review decides accepted credit, especially E209/D213.'}})
print(f'Authored metadata for {len(cases)} cases, {len(scanned)} text files audited, {len(matches)} matching files. No SUT or Worker execution.')
