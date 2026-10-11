#!/usr/bin/env python3
"""Aggregate behaviour case headers; origin is provenance, never discovery order."""
import collections,json
from pathlib import Path
from common import ROOT,TESTS,dump,sha
LAYERS=('unit','logic','conformance','faults','regressions')
def build():
    cases=[];excluded=[]
    for layer in LAYERS[:-1]:
        for path in sorted((TESTS/layer).rglob('*.case.json')):
            case=json.loads(path.read_text());case['header']=str(path.relative_to(ROOT))
            assert case['layer']==layer and case['id'].startswith(layer+'/'+case['behaviour']+'/'),path
            assert path.parent==TESTS/layer/case['behaviour'],path
            assert case['origins'] and case['title'] and (case['runnable'] or case['reason']),path
            cases.append(case)
        for path in sorted((TESTS/layer).rglob('*.design.json')):
            row=json.loads(path.read_text());row['header']=str(path.relative_to(ROOT));excluded.append(row)
    # Fix-lane files are owned by that lane and never rewritten by discovery.
    for path in sorted((TESTS/'regressions').iterdir()):
        if not path.is_dir() or path.name=='__pycache__' or path.name.startswith('.'):continue
        config=path/'case.json';cfg=json.loads(config.read_text()) if config.exists() else {}
        runner=next((p for p in [path/'run.py',path/'run.sh'] if p.exists()),None)
        source=config if config.exists() else runner or path
        cases.append(dict(id='regressions/'+cfg.get('id',path.name),layer='regressions',behaviour=cfg.get('behaviour',{'R4-05':'rpc/restored-http-channels','R4-03':'durable-objects/facet-mutation-order','R4-10':'durable-objects/persistent-stub-permissions','R4-01':'rpc/session-completion','R4-04':'durable-objects/alarm-timeout','R4-08':'web-platform/abort-attributes','R4-11':'rpc/facet-serialization','R4-02':'rpc/persistent-capability-failure','R4-06':'rpc/capability-identity','R4-07':'rpc/disposal-context','R4-09':'rpc/disposed-pipelines','R4-12':'rpc/receiver-lifetime','R4-13':'rpc/session-ownership','R4-14':'rpc/pipelining-and-cloning','R4-15':'rpc/property-observation','R4-16':'rpc/data-shape'}.get(path.name,'finding-specific')),title=cfg.get('title',cfg.get('description',path.name)),origins=[{'source':'fixes branch; see tests/regressions/IMPORT.json'}],legacy_ids=[],source=str(source.relative_to(ROOT)),source_sha256=sha(source) if source.is_file() else None,runnable=bool(config.exists() or runner),reason=None if config.exists() or runner else 'Fix-lane source has no case.json/run.py/run.sh; requires its documented Rust integration build.',profiles=cfg.get('profiles',['quick','full']),adapter='regression' if config.exists() or runner else 'none',regression=cfg,fixture=str(path.relative_to(ROOT))))
    # tests-hyperbob shape runners, asserted against tests/hyperbob-expected.json.
    from hyperbob import cases as hyperbob_cases
    cases.extend(hyperbob_cases())
    assert len({c['id'] for c in cases})==len(cases)
    assert len([c for c in cases if c.get('reviewed')])==671
    aliases=[x for c in cases for x in c.get('legacy_ids',[])];assert len(aliases)==len(set(aliases))
    sources=json.loads((TESTS/'lib/SOURCES.json').read_text())['files'];groups=collections.defaultdict(list)
    for f in sources:groups[f['sha256']].append(f['path'])
    inv=dict(schema_version=2,baseline='9c0fca5',organisation='layer / behaviour / case; origin and historical wave are metadata only',reviewed_corpus_count=671,design_census=dict(total=786,primary=671,characterization=115),phase2_provenance="lib/phase2/CAMPAIGN.json",cases=cases,excluded_designs=excluded,source_inventory='lib/SOURCES.json',archive_runner_inventory='lib/provenance/RUNNER-SOURCES.json',unpublished_runner_reasons='lib/provenance/RUNNERS.md',identical_file_groups=[{'sha256':k,'paths':sorted(set(v))} for k,v in groups.items() if len(set(v))>1],deduplication='One case per distinct trace and oracle; identical imported copies and accepted replacement revisions share case credit. See lib/provenance/DEDUPLICATION.md.')
    dump(TESTS/'MANIFEST.json',inv)
    print(f'Inventory: {len(cases)} behaviour cases, 671 reviewed corpus, {len(excluded)} non-promoting designs; {sum(c["runnable"] for c in cases)} runnable',flush=True)
    return inv
if __name__=='__main__':build()
