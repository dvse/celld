#!/usr/bin/env python3
"""Read source/hashes, parse JSON/Python, and ask Node for JS syntax only. Never import JS/TS."""
import ast, hashlib, json, pathlib, re, subprocess
H = pathlib.Path(__file__).resolve().parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
pins = json.loads((H/'source-pins.json').read_text())
manifest = json.loads((H/'manifest.json').read_text())
provenance = json.loads((H/'provenance.json').read_text())
roots = {'runtime': pathlib.Path(pins['source_root']), 'os': pathlib.Path(pins['os_root']), 'overlap': pathlib.Path(pins['overlap_root'])}
checked = 0
for path, digest in pins['files'].items():
 assert sha(roots['runtime']/path) == digest, path
 checked += 1
for field, root in [('os_files',roots['os']),('overlap_files',roots['overlap']),('vendor_files',H)]:
 for item in pins[field]:
  p=root/item['path']; assert sha(p)==item['sha256'] and p.stat().st_size==item['bytes'],item['path']; checked+=1
module = H/'vendor/cloudflare-os/packages/typed-storage/src/index.ts'
assert sha(module)==provenance['source_sha256']=='561111a1a0787d5158ddfa9df5c1910285b156906d874f5f58719a901e004c12'
assert module.read_bytes()==(roots['os']/'raw/packages/typed-storage/src/index.ts').read_bytes()
assert not re.search(r'^\s*import\s',module.read_text(),re.M), 'Production module unexpectedly imports runtime dependencies'
assert provenance['source_modified'] is False and provenance['downloaded_code_executed'] is False
s=(H/'cases.js').read_text(); f=(H/'fixture.js').read_text()
functions=re.findall(r'^export function (C\d+)\(s, t\)',s,re.M)
ids=[c['id'] for c in manifest['cases']]
assert functions==ids==['C201','C202','C203','C204','C205','C206','C207']
assert re.findall(r"^import .* from '([^']+)';",s,re.M)==['./vendor/cloudflare-os/packages/typed-storage/src/index.ts']
assert re.findall(r"^import .* from '([^']+)';",f,re.M)==['./cases.js']
assert 'CASES[id](storage, t)' in f and 'storage = this.state.storage' in f
assert 'export const CASES = { '+', '.join(ids)+' };' in s
assert 'i <= 64' in f and "if (step.done) return result" in f
assert 'if (traceSettled)' in f and 'await storage.deleteAll();' in f
assert "if (typeof iterator.return === 'function') iterator.return();" in f
assert not re.search(r'\b(?:eval|new Function|fetch|setInterval)\s*\(',s)
assert not re.search(r'\b(?:function|class)\s+(?:createTypedStorage|createCollection|KvPrefixedView)\b',s+f)
assert manifest['authored']==7 and manifest['independently_reviewed']==manifest['accepted_primary_static']==0
assert manifest['runtime_executions']==manifest['runtime_passes']==0
for i,c in enumerate(manifest['cases']):
 end=s.index('export function '+ids[i+1]+'(') if i+1<len(ids) else s.index('export const CASES')
 body=s[s.index('export function '+c['id']+'('):end]
 assert len(re.findall(r'\bt\.(?:eq|same|ok)\(',body))==c['literal_assertion_call_sites']>=3
 assert c['runtime_status']=='NOT_RUN' and c['actual_runs']==c['runtime_passes']==0 and c['independently_reviewed'] is False
 assert c['limits']['max_native_storage_entries']==32 and c['limits']['max_outbound_public_network_requests']==0
 assert c['limits']['max_owned_domain_processes']==32 and c['limits']['max_owned_writable_bytes']==134217728
 assert 'across PGIDs' in c['limits']['descendant_supervision']
 for ref in c['source_refs']+c['application_callsite_refs']:
  path=roots[ref['root']]/ref['path']; assert path.is_file()
  assert any(x['path']==ref['path'] for x in pins['os_files'])
  assert 1<=ref['line_start']<=ref['line_end']<=len(path.read_text().splitlines())
for file in ('author_manifest.py','validate_static.py'): ast.parse((H/file).read_text(),filename=file)
for file in ('cases.js','fixture.js'):
 subprocess.run(['node','--input-type=module','--check'],input=(H/file).read_bytes(),check=True,capture_output=True,timeout=10)
config=json.loads((H/'wrangler.jsonc').read_text())
assert config['main']=='fixture.js' and config['durable_objects']['bindings']==[{'name':'CASE','class_name':'TypedStorageCase'}]
assert config['migrations']==[{'tag':'v1','new_sqlite_classes':['TypedStorageCase']}]
if (H/'SHA256SUMS').exists():
 for line in (H/'SHA256SUMS').read_text().splitlines():
  digest, path=line.split('  ',1); assert sha(H/path)==digest, path
report={'kind':'STATIC_ONLY','source_and_overlap_pins_verified':checked,'vendored_production_module_byte_exact':True,'module_sha256':sha(module),'case_functions':len(ids),'literal_assertion_call_sites':sum(x['literal_assertion_call_sites'] for x in manifest['cases']),'javascript_syntax_files':2,'python_source_parses':2,'downloaded_source_executed':False,'downloaded_source_compiled':False,'dependency_installs':0,'sut_launches':0,'runtime_executions':0,'runtime_passes':0,'independent_review':'pending','scope':'Actual pinned OS typed-storage component source; no full-OS, distributed, restart, security, durability or performance claim.'}
print(json.dumps(report,indent=2))
