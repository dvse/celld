#!/usr/bin/env python3
"""Read-only static/hash/format checks. Node --check only; no JS/TS execution."""
import ast,hashlib,json,pathlib,re,struct,subprocess,zlib
H=pathlib.Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda name:json.loads((H/name).read_text())
pins=read('source-pins.json'); m=read('manifest.json'); dep=read('dependency-lock.json'); p=read('provenance.json'); v=read('golden-inputs.json'); sched=read('schedule.json')
roots={'runtime':pathlib.Path(pins['source_root']),'os':pathlib.Path(pins['os_root']),'overlap':pathlib.Path(pins['overlap_root']),'vendor':H}
checked=0
for field,key in [('runtime_files','runtime'),('baseline_files','runtime'),('os_files','os'),('overlap_files','overlap'),('vendor_files','vendor')]:
 for item in pins[field]:
  path=roots[key]/item['path'];assert sha(path)==item['sha256'] and path.stat().st_size==item['bytes'],path;checked+=1
lock=pathlib.Path(pins['lockfile']['path']);assert sha(lock)==pins['lockfile']['sha256']==dep['historical_lockfile_sha256'];checked+=1
module=H/p['vendor_path'];assert module.read_bytes()==pathlib.Path(p['local_original']).read_bytes()
assert sha(module)==p['source_sha256']=='56814f3f0608c88e6e83ba08e43f5af87ed4fabf972554e696c390809e9e1538'
assert p['source_modified'] is False and p['downloaded_code_executed'] is False
imports=re.findall(r'^import (?!type\b).*? from "([^"]+)";',module.read_text(),re.M)
assert imports==['node:zlib','pako']
assert dep['direct_dependency']['version']=='3.0.2' and dep['direct_dependency']['integrity'] in lock.read_text()
importer=lock.read_text().split('  packages/workshop-backend:\n',1)[1].split('\n  packages/',1)[0]
assert '      pako:\n        specifier: ^3.0.2\n        version: 3.0.2\n' in importer
assert dep['installed_package_verified'] is False and dep['dependency_installs']==0
runtime=roots['runtime']/'celld-os-project/celld/crates/celld/js'
assert '"zlib" | "node:zlib" => "__zlibModule"' in (runtime/'modules.rs').read_text()
harness=(runtime/'harness.js').read_text();native=harness.split('__celld.__zlibModule = {',1)[1].split('\n};',1)[0]
assert 'deflateSync: (data, _options)' in native and 'inflateSync: (data, _options)' in native
assert 'Z_BEST_SPEED' not in native
assert read('package.json')['dependencies']=={'pako':'3.0.2'}
assert read('wrangler.jsonc')['compatibility_flags']==['nodejs_compat']

def objoid(o):
 b=bytes.fromhex(o['payload_hex']);return hashlib.sha1(o['type'].encode()+b' '+str(len(b)).encode()+b'\0'+b).hexdigest()
def stored(b):
 return b'\x78\x01\x01'+struct.pack('<HH',len(b),len(b)^65535)+b+struct.pack('>I',zlib.adler32(b))
objs=[v['loose']['object'],v['tree']['object'],v['commit']['object']]+v['pack']['objects']+v['chain']['objects']+v['referents']
for o in objs:assert objoid(o)==o['oid']
assert v['loose']['object']['oid']=='bd9dbf5aae1a3862dd1526723246b20206e5fc37'
loose=bytes.fromhex(v['loose']['whole_hex']);assert loose==b'blob 16\0what is up, doc?'
assert bytes.fromhex(v['loose']['zlib_hex'])==stored(loose) and zlib.decompress(bytes.fromhex(v['loose']['zlib_hex']))==loose
# Fixed-format verification, not a reference implementation of the production decoder.
assert [e['name'] for e in v['tree']['entries']]==['a.b','a','a0','link','sub']
assert [e['mode'] for e in v['tree']['entries']]==['100644','40000','100755','120000','160000']
assert v['tree']['object']['payload_hex']==b''.join((e['mode']+' '+e['name']).encode()+b'\0'+bytes.fromhex(e['oid']) for e in v['tree']['entries']).hex()
base=bytes(range(256))*256;target=b'HEAD|'+base+bytes(range(1,17))+b'|END'
assert bytes.fromhex(v['delta']['base_hex'])==base and bytes.fromhex(v['delta']['expected_hex'])==target
assert len(target)==v['delta']['target_bytes']==65561
assert v['delta']['instructions_hex']=='80800499800405484541447c8093010110047c454e44'
assert hashlib.sha256(target).hexdigest()==v['delta']['target_sha256']
entries=[]
for o,code in zip(v['pack']['objects'],[3,2,1,4]):
 b=bytes.fromhex(o['payload_hex']);header=bytes.fromhex(o['pack_header_hex'])
 assert header==bytes([(code<<4)|128|(len(b)&15),len(b)>>4])
 z=stored(b);assert zlib.decompress(z)==b;entries.append(header+z)
body=b'PACK\0\0\0\x02\0\0\0\x04'+b''.join(entries)
assert bytes.fromhex(v['pack']['hex'])==body+hashlib.sha1(body).digest()
cb=bytes(range(256));mid=bytes(range(17,25))+b'-middle';end=mid+b'!'
assert [bytes.fromhex(o['payload_hex']) for o in v['chain']['objects']]==[cb,mid,end]
d1=bytes.fromhex('80020f911108072d6d6964646c65');d2=bytes.fromhex('0f10900f0121')
assert len(d1)==14 and len(d2)==6
# d1 manually means source256,target15,copy17/8,insert7. d2 means source15,target16,copy0/15,insert1.
ce=[b'\xb0\x10'+stored(cb),b'\x6e\x81\x0d'+stored(d1),b'\x76'+bytes.fromhex(v['chain']['objects'][1]['oid'])+stored(d2)]
assert len(ce[0])==269 and len(ce[1])==28 and v['chain']['entry_offsets']==[12,281,309]
assert (1+1)*128+13==269
chainbody=b'PACK\0\0\0\x02\0\0\0\x03'+b''.join(ce)
assert bytes.fromhex(v['chain']['hex'])==chainbody+hashlib.sha1(chainbody).digest()
assert v['chain']['lookup_oids']==[o['oid'] for o in v['chain']['objects'][:2]]
for key in ['pack','chain']:
 b=bytes.fromhex(v[key]['hex']);assert len(b)-20==v[key]['body_bytes']
 assert hashlib.sha1(b[:-20]).hexdigest()==v[key]['trailer_hex']==b[-20:].hex()
 ends=sched['source_chunks']['X205' if key=='pack' else 'X206'];assert sorted(set(ends))==ends and ends[-1]==len(b)
assert json.loads((H/'vectors.js').read_text().split('export const V = ',1)[1].rstrip(';\n'))==v
s=(H/'cases.js').read_text();f=(H/'fixture.js').read_text()
ids=[c['id'] for c in m['cases']]
assert re.findall(r'^export async function (X\d+)\(t\)',s,re.M)==ids==['X201','X202','X203','X204','X205','X206']
assert re.findall(r"^import .* from '([^']+)';",s,re.M)==['./vendor/cloudflare-os/packages/workshop-backend/src/git-codec.ts','node:zlib','./vectors.js']
assert 'await iterator.return();' in s and 'retained.set(step.value.oid, step.value);' in s
assert 'if (i === expected.length)' in s and "t.same(step.done, true" in s
assert 'builtLookups = await decode(built,' in s and 'lookups = await decode(bytes,' in s
assert 'chunks[1 + 2 * i]' not in s and 'chunks.length, 10' not in s
assert not re.search(r'\b(?:eval|new Function|fetch|setInterval)\s*\(',s)
assert 'CASES[match[1]](t)' in f and 'externalOwnedProcessReapRequired: true' in f
assert m['authored']==6 and m['independently_reviewed']==m['accepted_primary_static']==m['runtime_executions']==m['runtime_passes']==0
for i,c in enumerate(m['cases']):
 a=s.index('export async function '+c['id']+'(');b=s.index('export async function '+ids[i+1]+'(') if i+1<len(ids) else s.index('export const CASES')
 assert len(re.findall(r'\bt\.(?:eq|same|ok|bytes)\(',s[a:b]))==c['literal_assertion_call_sites']>=3
 assert c['runtime_status']=='NOT_RUN' and c['actual_runs']==c['runtime_passes']==0 and c['independently_reviewed'] is False
 assert c['limits']['max_readable_sources']==2 and c['limits']['max_generator_next_calls']==10
 for ref in c['source_refs']:
  lines=(roots['os']/ref['path']).read_text().splitlines();assert 1<=ref['line_start']<=ref['line_end']<=len(lines)
for file in ('author_vectors.py','author_manifest.py','validate_static.py'):ast.parse((H/file).read_text(),filename=file)
for file in ('cases.js','fixture.js','vectors.js'):
 subprocess.run(['node','--input-type=module','--check'],input=(H/file).read_bytes(),check=True,capture_output=True,timeout=10)
if (H/'SHA256SUMS').exists():
 for line in (H/'SHA256SUMS').read_text().splitlines():
  digest,path=line.split('  ',1);assert sha(H/path)==digest,path
report={'kind':'STATIC_ONLY','source_dependency_overlap_pins_verified':checked,'production_module_byte_exact':True,'module_sha256':sha(module),'case_functions':len(ids),'direct_literal_assertion_call_sites':sum(c['literal_assertion_call_sites'] for c in m['cases']),'shared_decoder_assertion_call_sites':6,'golden_object_oids_checked':len(objs),'golden_pack_bytes':[475,367],'manual_delta_target_bytes':65561,'javascript_syntax_only_files':3,'python_source_parses':3,'native_zlib_status':'source mapping/functions present; Z_BEST_SPEED/options compatibility caveat preserved; runtime unverified','pako_status':'exact historical3.0.2/integrity declared; package bytes/install unverified','downloaded_source_executed':False,'downloaded_source_compiled':False,'dependency_installs':0,'sut_launches':0,'runtime_executions':0,'runtime_passes':0,'independent_review':'pending','scope':'Actual immutable OS Git codec valid-format source fixtures only; no full OS/runtime pass, authorization, scheduler, capability, performance or durability claim.'}
print(json.dumps(report,indent=2))
