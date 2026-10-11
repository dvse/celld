#!/usr/bin/env python3
"""Read-only source/hash/vector checks and Node --check on authored JS only. Never execute JS/TS."""
import ast, hashlib, json, pathlib, re, subprocess
H=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda n:json.loads((H/n).read_text())
pins=read('source-pins.json'); manifest=read('manifest.json'); provenance=read('provenance.json'); schedule=read('schedule.json'); audit=read('overlap-audit.json')
roots={'wave':H,'runtime':pathlib.Path(pins['source_root']),'os':pathlib.Path(pins['os_root']),'overlap':pathlib.Path(pins['overlap_root'])}
count=0
for path,digest in pins['files'].items():
 assert sha(roots['runtime']/path)==digest,path
 count+=1
for field,root in [('os_files',roots['os']),('overlap_files',roots['overlap']),('vendor_files',H)]:
 for item in pins[field]:
  p=root/item['path']; assert p.stat().st_size==item['bytes'] and sha(p)==item['sha256'],item['path']; count+=1
module=H/'vendor/cloudflare-os/packages/gatekeeper-kit/src/action-files.ts'
helper=module.with_name('positive-int.ts'); types=module.with_name('kv.ts')
assert sha(module)=='e735cdd41333be3297a6e8d7114553483772b33f310edfb0844296650c855da0'
assert module.read_bytes()==(roots['os']/'raw/packages/gatekeeper-kit/src/action-files.ts').read_bytes()
assert sha(helper)=='e9813ec2bd5121a0384dc6bd4af4467ea6aa27f169e11ddc27673a88879bded1'
assert sha(types)=='2dd68d8822cb4737d8563da0595e250894d0f7f0b2ed2dc4b1505336a1f4ef9d'
assert re.findall(r'^import (type )?.* from "([^\"]+)";',module.read_text(),re.M)==[('type ','./kv'),('','./positive-int')]
assert not re.search(r'^\s*import\b',helper.read_text()+types.read_text(),re.M)
assert (H/'vendor/cloudflare-os/LICENSE').read_bytes()==(roots['os']/'raw/LICENSE').read_bytes()
assert sha(H/'vendor/cloudflare-os/LICENSE')==provenance['license_sha256']
assert provenance['source_modified'] is provenance['downloaded_code_executed'] is provenance['downloaded_code_compiled'] is False
for item in provenance['files']:
 assert item['modified'] is False and sha(H/item['path'])==item['sha256']
 assert item['official_blob_url'].startswith('https://github.com/cloudflare/cloudflare-os/blob/'+pins['os_commit']+'/')
s=(H/'cases.js').read_text(); f=(H/'fixture.js').read_text()
ids=[c['id'] for c in manifest['cases']]
assert re.findall(r'^export async function (F\d+)\(storage, t\)',s,re.M)==ids==['F201','F202','F203','F204','F205','F206']
assert 'export const CASES = { '+', '.join(ids)+' };' in s
assert re.findall(r"^import .* from '([^']+)';",s,re.M)==['./vendor/cloudflare-os/packages/gatekeeper-kit/src/action-files.ts']
assert re.findall(r"^import .* from '([^']+)';",f,re.M)==['./cases.js']
assert 'new ActionFileStore(storage,' in s and 'CASES[id](storage, t)' in f and 'storage = this.state.storage' in f
assert not re.search(r'\b(?:eval|fetch|setInterval)\s*\(|new Function\b|\b(?:class|function)\s+ActionFileStore\b',s)
assert not re.search(r'storage\.(?:put|delete|transaction|transactionSync)\s*\(|storage\.kv\.(?:put|delete)\s*\(',s)
assert not re.search(r'Date\.now\s*=|crypto\.subtle\.[a-z]+\s*=',s+f)
assert 'if (traceSettled)' in f and 'await storage.deleteAll();' in f and 'if (step.done) return result;' in f
assert 'i <= 64' in f and 'waits < 32' in s and 'setTimeout(resolve, 5)' in s and 'youngAt > cutoff' in s
assert f.count('byteLength > 32768')==2 and 'BLOCKED_WITNESS' in f
assert manifest['authored']==6 and manifest['independently_reviewed']==manifest['accepted_primary_static']==0
assert manifest['runtime_executions']==manifest['runtime_passes']==0
assert manifest['reserved_unused_ids']==['F207','F208','F209','F210','F211','F212']
assert schedule['ids']==ids and [c['id'] for c in audit['cases']]==ids
for c in manifest['cases']:
 body='\n'.join(s.splitlines()[c['body_line_start']-1:c['body_line_end']])
 assert body.startswith('export async function '+c['id']+'(')
 assert len(re.findall(r'\bt\.(?:eq|same|ok)\(',body))==c['literal_assertion_call_sites']>=2
 assert c['runtime_status']=='NOT_RUN' and c['actual_runs']==c['runtime_passes']==0 and c['independently_reviewed'] is False
 assert c['limits']==schedule['limits']
 limits=c['limits']; op=c['operation_counts']
 assert limits['max_outbound_public_network_requests']==0 and limits['max_streams']==0
 assert limits['max_total_retained_payload_bytes']==2097169 and limits['max_external_receipt_bytes']==32768
 assert op['maximum_retained_native_entries']<=limits['max_native_storage_entries']==16
 assert op['capture_attempts']+op['reads']<=limits['max_webcrypto_digest_calls']==8
 assert op['capture_attempts']+op['reads']+op['explicit_deletes']+op['prune_calls']<=limits['max_public_module_calls']==12
 assert limits['max_owned_domain_processes']==32 and limits['max_owned_writable_bytes']==134217728 and limits['outer_rss_bytes']==1073741824
 assert 'across PGIDs' in limits['descendant_supervision'] and 'estimate only' in limits['byte_buffer_estimate_scope']
 for reference in c['source_refs']+c['application_callsite_refs']:
  p=roots[reference['root']]/reference['path']; assert p.is_file()
  assert 1<=reference['line_start']<=reference['line_end']<=len(p.read_text().splitlines())
  category='vendor_files' if reference['root']=='wave' else 'os_files'
  assert any(v['path']==reference['path'] for v in pins[category])
# These are independent literal synthetic vectors; no JS/TS code is imported or interpreted.
vectors=[(bytes([10,20,30,40,50]),'6ef53a6408ec4429791fa808e4fbe7843f936316950a20ba5fbbbdd01cd29899'),
(bytes([17])*1048576+bytes([34])*1048576+bytes(range(17)),'669a63cbe23fd19a58eea8d71ca68ce9d5a24a74ed34171d5cd17ebb262d2277'),
(b'','e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'),
(bytes([1,2,3,4]),'9f64a747e1b97f131fabb6b447296c9b6f0201e79fb3c5356e6c77e89b6a806a'),
(bytes([8,9,10]),'6e9fa019228fe1a9d342d4a0085ab80270c9726bd08cd5a35d7626a700b34e2f'),
(bytes([11,12]),'1b47e3acf9cd496936430df42e017269c3bb14f54dda91b41a90fd265960f124'),
(bytes([21,22,23]),'95cee872c44c906ec46f0fad618cd7c8c601651be78e6f9d7d2ffe745e910ef9'),
(bytes([31,32,33,34]),'06b0a21bf142b7dc9b1360ec9cef21dc20d8afe62d09448a7e0d7b09ca3c5789'),
(bytes([41,42,43,44,45]),'7bdeb14b9ae8423d9cfd11fe32235450cccff5ee3cdce8b58c79bb6099f1ecc5')]
for data,expected in vectors: assert hashlib.sha256(data).hexdigest()==expected and expected in s
for name in ('author_manifest.py','validate_static.py'):ast.parse((H/name).read_text(),filename=name)
for name in ('cases.js','fixture.js'):
 subprocess.run(['node','--input-type=module','--check'],input=(H/name).read_bytes(),capture_output=True,check=True,timeout=10)
config=read('wrangler.jsonc')
assert config['main']=='fixture.js'
assert config['durable_objects']['bindings']==[{'name':'CASE','class_name':'ActionFileCase'}]
assert config['migrations']==[{'tag':'v1','new_sqlite_classes':['ActionFileCase']}]
if (H/'SHA256SUMS').exists():
 listed=set()
 for line in (H/'SHA256SUMS').read_text().splitlines():
  digest,path=line.split('  ',1); assert path not in listed; listed.add(path); assert sha(H/path)==digest,path
 assert listed=={str(p.relative_to(H)) for p in H.rglob('*') if p.is_file() and p.name!='SHA256SUMS'}
report={'kind':'STATIC_ONLY','source_and_overlap_pins_verified':count,'vendored_production_and_license_byte_exact':True,'runtime_helper_hash_verified':True,'type_helper_hash_verified':True,'closed_import_graph':True,'module_sha256':sha(module),'case_functions':6,'literal_assertion_call_sites':sum(c['literal_assertion_call_sites'] for c in manifest['cases']),'independent_digest_vectors_verified':len(vectors),'javascript_syntax_files':2,'python_source_parses':2,'downloaded_source_executed':False,'downloaded_source_compiled':False,'dependency_installs':0,'sut_launches':0,'runtime_executions':0,'runtime_passes':0,'independent_review':'pending','scope':'Actual pinned OS component source over native DO storage and real WebCrypto. No full OS, durability, performance or security claim.'}
print(json.dumps(report,indent=2))
