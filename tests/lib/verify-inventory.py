#!/usr/bin/env python3
"""Verify behaviour placement, unchanged imports, deduplication and result coverage."""
import collections,json,sys
from common import ROOT,TESTS,sha
m=json.loads((TESTS/'MANIFEST.json').read_text());cases=m['cases'];ids=[c['id'] for c in cases]
assert len(ids)==len(set(ids))
reviewed=[c for c in cases if c.get('reviewed')];assert len(reviewed)==671
census=json.loads((TESTS/'lib/provenance/COUNTS.json').read_text())
assert {(c['corpus_wave'],c['corpus_id']) for c in reviewed if not c.get('campaign')}=={(g['wave'],id) for g in census['groups'] for id in g['accepted_static_ids']}
assert len(m['excluded_designs'])==115
campaign=json.loads((TESTS/'lib/phase2/CAMPAIGN.json').read_text())
assert {(c['corpus_wave'],c['corpus_id']) for c in reviewed if c.get('campaign')}=={(c['wave'],c['id']) for c in campaign['designs'] if c['classification']=='primary'}
for f in campaign['files']:assert sha(ROOT/f['path'])==f['sha256'],f['path']
aliases=[a for c in cases for a in c.get('legacy_ids',[])];assert len(aliases)==len(set(aliases))
assert len([a for a in aliases if a.startswith('examples/')])==26
assert len([a for a in aliases if a.startswith('hyperbob/')])==25
assert len([a for a in aliases if a.startswith('logic/lease-continuity/')])==19
for p in (TESTS/'conformance').rglob('*'):
 if p.is_dir():assert not any(x in ['examples','hyperbob','corpus','waves','workerd-ported','wpt'] for x in p.relative_to(TESTS/'conformance').parts),p
for c in cases:
 assert (ROOT/c['source']).exists(),c['source']
 assert c['runnable'] or c['reason'],c['id']
 assert c['origins'] and c['title'],c['id']
 if c['source_sha256']:assert sha(ROOT/c['source'])==c['source_sha256'],c['id']
 if c['layer']!='regressions':
  assert c['id'].startswith(c['layer']+'/'+c['behaviour']+'/'),c['id']
  p=ROOT/c['header'];assert p.parent==TESTS/c['layer']/c['behaviour'],p
  assert json.loads(p.read_text())=={k:v for k,v in c.items() if k!='header'},c['id']
 if c.get('fixture'):assert (ROOT/c['fixture']).is_dir(),c['id']
# The execution selector and oracle define a case; shared helper source does not.
fingerprints={}
for c in cases:
 key=json.dumps({k:c.get(k) for k in ['layer','source_sha256','fixture','test_filter','requests','selector','mutation','runnable','reason']},sort_keys=True)
 if key in fingerprints:raise AssertionError(('duplicate execution contract',fingerprints[key],c['id']))
 fingerprints[key]=c['id']
sources=json.loads((TESTS/'lib/SOURCES.json').read_text())['files']
for f in sources:assert sha(ROOT/f['path'])==f['sha256'],f['path']
for f in json.loads((TESTS/'regressions/IMPORT.json').read_text())['files']:assert sha(ROOT/f['path'])==f['sha256'],f['path']
for e in m['excluded_designs']:assert not e['runnable'] and e['reason'] and (ROOT/e['header']).exists()
if '--results' in sys.argv:
 x=json.loads((TESTS/'RESULTS.json').read_text())
 columns=x['columns'].values() if x.get('kind')=='source-column-matrix' else [x]
 for column in columns:
  rows=column['results'];seen={(r['id'],r['runtime']) for r in rows};assert len(seen)==len(rows)
  assert all(r['status'] in ['pass','fail','expected-fail','not-applicable'] and r['reason'] and r['duration_ms']>=0 for r in rows)
  assert dict(collections.Counter(r['status'] for r in rows))==column['counts']
  if column['profile']=='full' and not column['arguments'].get('layer') and not column['arguments'].get('case'):
   runtimes=['celld','workerd'] if column['arguments']['runtime']=='both' else [column['arguments']['runtime']]
   assert seen=={(c['id'],r) for c in cases for r in runtimes if 'full' in c['profiles']}
  for row in rows:
   assert all((ROOT/p).exists() for p in row['artifacts']),row['id']
print(f'PASS: {len(cases)} behaviour cases; 671 reviewed identities; 115 characterization designs; {len(sources)} unchanged imported files; no duplicate execution contracts')
