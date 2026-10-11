#!/usr/bin/env python3
"""Independent literal-format fixture authoring. No Git/JS/TS/runtime execution.
Only Python hashlib, struct and adler32; stored DEFLATE blocks are written directly.
This is a vector constructor, never an alternative production codec or runtime oracle.
"""
import hashlib, json, pathlib, struct, zlib
H = pathlib.Path(__file__).resolve().parent

def oid(kind, payload):
    return hashlib.sha1(kind.encode()+b' '+str(len(payload)).encode()+b'\0'+payload).hexdigest()

def stored(payload):
    assert len(payload) <= 65535
    # CMF/FLG 78 01, BFINAL=1/BTYPE=00, little-endian LEN/NLEN, Adler32 big-endian.
    return b'\x78\x01\x01'+struct.pack('<HH',len(payload),len(payload)^65535)+payload+struct.pack('>I',zlib.adler32(payload))

def obj(kind, payload, header=None):
    d={'type':kind,'payload_hex':payload.hex(),'oid':oid(kind,payload)}
    if header is not None: d['pack_header_hex']=header
    return d

def pack(entries):
    body=b'PACK\x00\x00\x00\x02'+struct.pack('>I',len(entries))+b''.join(entries)
    return {'hex':(body+hashlib.sha1(body).digest()).hex(),'body_bytes':len(body),'trailer_hex':hashlib.sha1(body).hexdigest()}

blob=b'what is up, doc?'
assert oid('blob',blob)=='bd9dbf5aae1a3862dd1526723246b20206e5fc37'
loose=b'blob 16\0'+blob
empty_tree=oid('tree',b'')
assert empty_tree=='4b825dc642cb6eb9a060e54bf8d69288fbee4904'
parent1=(f'tree {empty_tree}\nauthor Fixture Author <author@example.invalid> 1700000000 +0000\ncommitter Fixture Author <author@example.invalid> 1700000000 +0000\n\nRoot one\n').encode()
parent2=parent1.replace(b'Root one',b'Root two')
p1=oid('commit',parent1); p2=oid('commit',parent2)
link=b'a.b'
ordered=[{'mode':'100644','name':'a.b','oid':oid('blob',blob)}, {'mode':'40000','name':'a','oid':empty_tree}, {'mode':'100755','name':'a0','oid':oid('blob',blob)}, {'mode':'120000','name':'link','oid':oid('blob',link)}, {'mode':'160000','name':'sub','oid':p1}]
# Literal order a.b < a/ < a0 < link < sub, not a generic sorter.
tree=b''.join((e['mode']+' '+e['name']).encode()+b'\0'+bytes.fromhex(e['oid']) for e in ordered)
commit=(f'tree {oid("tree",tree)}\nparent {p2}\nparent {p1}\nauthor Fixture Author <author@example.invalid> 1700000000 +0530\ncommitter Fixture Committer <committer@example.invalid> 1700000001 -0330\nx-note alpha\nx-note beta\n\nMerge fixture\n\nDetails\n').encode()
continued=(f'tree {empty_tree}\nparent {p1}\nauthor Fixture Author <author@example.invalid> 1700000000 +0000\ncommitter Fixture Author <author@example.invalid> 1700000000 +0000\nx-note first\n  second\n \n fourth\nx-note last\n\nA normal message.\n').encode()
base=bytes(range(256))*256
expected=b'HEAD|'+base+bytes(range(1,17))+b'|END'
assert len(expected)==65561
# source size 65536=80 80 04, result65561=99 80 04;
# insert5, copy0/65536 (80), copy257/16 (93 01 01 10), insert4.
delta=bytes.fromhex('80800499800405484541447c8093010110047c454e44')
packtree=b'100644 note\0'+bytes.fromhex(oid('blob',blob))
packcommit=(f'tree {oid("tree",packtree)}\nauthor Fixture Author <author@example.invalid> 1700000000 +0000\ncommitter Fixture Author <author@example.invalid> 1700000000 +0000\n\nPack fixture\n').encode()
tag=(f'object {oid("commit",packcommit)}\ntype commit\ntag fixture-v1\ntagger Fixture Author <author@example.invalid> 1700000000 +0000\n\nFixture tag\n').encode()
# Per-entry type/size varint constants are calculated as explicit low4/high7 fields.
objects=[]; entries=[]
for kind,payload,code in [('blob',blob,3),('tree',packtree,2),('commit',packcommit,1),('tag',tag,4)]:
    assert 16<=len(payload)<2048
    header=bytes([(code<<4)|0x80|(len(payload)&15),len(payload)>>4])
    objects.append(obj(kind,payload,header.hex()));entries.append(header+stored(payload))
whole=pack(entries)
# One complete three-object delta pack. Base is uncompressed256 byte blob.
chainbase=bytes(range(256)); mid=bytes(range(17,25))+b'-middle'; end=mid+b'!'
d1=bytes.fromhex('80020f911108072d6d6964646c65')
d2=bytes.fromhex('0f10900f0121')
assert len(d1)==14 and len(d2)==6 and len(mid)==15 and len(end)==16
chain_entries=[bytes.fromhex('b010')+stored(chainbase), bytes.fromhex('6e810d')+stored(d1), bytes.fromhex('76')+bytes.fromhex(oid('blob',mid))+stored(d2)]
assert len(chain_entries[0])==269 # OFS distance269 = (1+1)*128+13 => 81 0d.
chain=pack(chain_entries)
V={'loose':{'object':obj('blob',blob),'whole_hex':loose.hex(),'zlib_hex':stored(loose).hex()},'tree':{'entries':ordered,'input_order':[4,2,1,3,0],'object':obj('tree',tree),'types':['blob','tree','blob','blob','commit']},'commit':{'object':obj('commit',commit),'tree':oid('tree',tree),'parents':[p2,p1],'continued_hex':continued.hex(),'continued_refs':{'tree':empty_tree,'parents':[p1]},'continued_values':['first\n second\n\nfourth','last']},'delta':{'base_hex':base.hex(),'instructions_hex':delta.hex(),'expected_hex':expected.hex(),'target_bytes':len(expected),'target_sha256':hashlib.sha256(expected).hexdigest()},'pack':{'objects':objects,**whole},'chain':{'objects':[obj('blob',chainbase),obj('blob',mid),obj('blob',end)],'lookup_oids':[oid('blob',chainbase),oid('blob',mid)],'entry_offsets':[12,281,309],**chain},'referents':[obj('tree',b''),obj('blob',link),obj('commit',parent1),obj('commit',parent2)]}
# Write JSON and a mechanically identical JS data module. Neither executes source.
(H/'golden-inputs.json').write_text(json.dumps(V,indent=2)+'\n')
(H/'vectors.js').write_text('// Independent literal-format vectors; see author_vectors.py and ORACLES.md.\nexport const V = '+json.dumps(V,indent=2)+';\n')
print(json.dumps({'vector_authoring':'STATIC_ONLY','golden_bytes':(H/'golden-inputs.json').stat().st_size,'pack_bytes':len(bytes.fromhex(whole['hex'])),'chain_bytes':len(bytes.fromhex(chain['hex'])),'production_execution':False}))
