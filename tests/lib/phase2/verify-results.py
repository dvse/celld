#!/usr/bin/env python3
"""Verify final coverage, resource receipts and every exported raw-file hash."""
import collections,gzip,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];T=ROOT/'tests'
sys.path.insert(0,str(T/'lib'))
from phase2.campaign import profile as campaign_profile
def read(path):
    data=gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()
    return json.loads(data)
report=read(T/'RESULTS.json');manifest=read(T/'MANIFEST.json');cases={c['id']:c for c in manifest['cases']}
export=ROOT/report['matrix'];audit={};tools=read(export/'TOOLS.json')
exporter=read(export/'EXPORTER.json');assert hashlib.sha256((export/exporter['artifact']).read_bytes()).hexdigest()==exporter['sha256']
assert tools['esbuild']['receipt']['source_commit']==report['source_pins']['esbuild']['source_commit']
assert tools['esbuild']['receipt']['go_version']=='go'+report['source_pins']['go']
for label,column in report['columns'].items():
    assert len(column['results'])==len(cases)*2
    assert column['source_commit']==report['source_pins']['source_columns'][label]
    source=read(export/label/'SOURCE-RECEIPT.json')
    assert source['build']['commit']==column['source_commit']
    assert source['source_tree']==report['source_pins']['source_trees'][label]
    assert source['source_tree']==read(export/'MATRIX.json')['columns'][label]['source_tree']
    assert source['build']['toolchain']==report['source_pins']['rust']
    assert source['build']['sha256']==read(export/'MATRIX.json')['columns'][label]['binary_sha256']
    guarded=0;guards=set();campaign_domains=set()
    raw_files=read(export/label/'ARTIFACTS.json')['files'];raw_by_path={x['remote_path']:x for x in raw_files}
    for row in column['results']:
        case=cases[row['id']]
        if row['runtime']=='celld' and case.get('reviewed'):assert row['status']!='not-applicable',row['id']
        if not (case.get('campaign') or case.get('adapter') in ['topology','recovery','deployment']):continue
        if row['status']=='not-applicable':continue
        receipts=[ROOT/p for p in row['artifacts'] if Path(p).name in ['resource-guard.json','resource-guard.json.gz']]
        assert receipts,('no independent resource receipt',label,row['id'],row['runtime'])
        for item in row['artifacts']:
            path=ROOT/item
            if path.name in ['fleet.json','fleet.json.gz'] and row['runtime']=='celld':
                fleet=read(path);assert fleet['binary']['sha256']==source['build']['sha256']
                assert all(n['exe_sha256']==source['build']['sha256'] for n in fleet['nodes'].values())
                assert fleet['store']['sha256']==tools['seaweedfs']['sha256']
        if row['runtime']=='workerd' and case.get('corpus_wave') in ['sqlite-concurrency','native-transform-stress','bounded-resource']:
            routing=[ROOT/p for p in row['artifacts'] if Path(p).name in ['oracle-routing.json','oracle-routing.json.gz']]
            assert len(routing)==1,('oracle callback routing evidence absent',label,row['id'])
            graph=read(routing[0])['bindings'];assert graph
            assert all(b['target_worker']==('caller' if b['binding']=='ROOT' else 'owner') for b in graph)
        guarded+=1
        for path in receipts:
            g=read(path);guards.add(str(path));assert g['samples']>0 and g['processes']
            if case.get('campaign'):
                assert g['profile']==campaign_profile(case['corpus_wave']),('source envelope mismatch',path)
                if row['runtime']=='workerd':
                    routing=[ROOT/p for p in row['artifacts'] if Path(p).name in ['oracle-routing.json','oracle-routing.json.gz']]
                    assert len(routing)==1 and read(routing[0])['v8_flags']==['--max-heap-size=128'],('stock campaign V8 bound absent',path)
                domain=g['kernel_domain'];assert domain and domain['filesystem']['maximum_bytes']<=g['profile']['disk_bytes'];campaign_domains.add(domain['path'])
                assert not domain['remaining_pids'],path
                retained=Path(domain['filesystem']['retained'])
                for relative,digest in domain['filesystem']['retained_files_sha256'].items():
                    assert raw_by_path[str(retained/relative)]['sha256']==digest,('retained state differs',path,relative)
                if row['status']=='pass':
                    assert int(domain['final']['memory.peak'])<=g['profile']['rss_bytes']
                    assert domain['peak_aggregate_rss_bytes']<=g['profile']['rss_bytes']
                    assert domain['peak_processes']<=g['profile']['pids']
                    assert domain['peak_owned_writable_bytes']<=g['profile']['disk_bytes']
                    assert int(domain['final']['pids.current'])==1,('unreaped tasks besides quota keeper',path)
                    assert g['elapsed_seconds']<=g['profile']['wave_seconds']
            if row['status']=='pass':
                assert not g['violations']
                assert all(p['reaped'] and p['samples']>0 and p['peak_rss_bytes']<=p['rss_limit_bytes'] and p['peak_log_bytes']<=p['log_limit_bytes'] for p in g['processes'].values()),path
    binaries=0
    for record in raw_files:
        if not record.get('export') or Path(record['remote_path']).name!='runtime.json':continue
        value=read(export/record['export'])
        if value.get('runtime') not in ['celld','workerd'] or not value.get('binary_sha256'):continue
        expected=source['build']['sha256'] if value['runtime']=='celld' else tools['workerd']['sha256']
        assert value['binary_sha256']==expected,(label,record['remote_path'],'executed binary differs');binaries+=1
    hashed=0;raw_files=read(export/label/'ARTIFACTS.json')['files']
    for record in raw_files:
        if 'export' not in record:continue
        path=export/record['export'];data=gzip.decompress(path.read_bytes()) if path.suffix=='.gz' else path.read_bytes()
        assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256'],path
        hashed+=1
    na=[r for r in column['results'] if r['layer']=='conformance' and r['runtime']=='celld' and r['status']=='not-applicable']
    assert len(na)==6 and all(not cases[r['id']]['runnable'] for r in na)
    audit[label]={'results':len(column['results']),'guarded_case_runtime_rows':guarded,'resource_receipts':len(guards),'kernel_campaign_domains':len(campaign_domains),'runtime_binary_receipts_verified':binaries,'exported_file_hashes_verified':hashed,'raw_files_indexed':len(raw_files),'candidate_conformance_exclusions':len(na)}
vm=T/'evidence/phase2-vm';gates=read(vm/'GATES.json');assert len(gates)==12
by_run={g['run_id']:g for g in gates}
for gate in gates:
    receipt=vm/gate['receipt'];value=read(receipt)
    assert value['raw_receipt_sha256']==gate['receipt_sha256']
    assert value['raw_receipt']==gate['remote_receipt']
    raw=read(receipt.parent/'RAW-FILES.json')
    assert any(f['remote']==gate['remote_receipt'] and f['sha256']==gate['receipt_sha256'] for f in raw)
selected=read(vm/'SELECTED.json')
for label,checks in selected.items():
    for name,record in checks.items():
        path=ROOT/record['receipt'];gate=by_run[record['run_id']]
        assert hashlib.sha256(path.read_bytes()).hexdigest()==record['export_sha256']
        assert gate['receipt_sha256']==record['raw_sha256']
        expected=(report['source_pins']['historical_candidate002_binary_sha256'] if label=='historical-candidate002'
                  else read(export/'MATRIX.json')['columns'][label]['binary_sha256'])
        assert gate['binary_sha256']==expected
        if label!='historical-candidate002':assert gate['source_commit']==report['source_pins']['source_columns'][label]
        assert gate['status']==record['status']==('PASS' if name=='gate-v3' else 'FAIL')
        if name=='cold-restart-v1':
            assert gate['acknowledged_four']['status']=='PASS' and gate['released_owner']['status']=='PASS'
            assert gate['durability']['artifact']=='Snapshot' and not gate['generation2_entered']
            assert any(t['exit_code']==-9 and t['forced_kill'] and t['outer_term_grace_seconds']==45 and t['reaped'] for t in gate['terminal'])
prior=read(T/'NA-AUDIT.json');assert len(prior['dispositions'])==1894
output={'status':'PASS','columns':audit,'prior_na_dispositions':len(prior['dispositions']),'vm_attempts_verified':len(gates),'selected_vm_gates_verified':sum(map(len,selected.values())),'policy':'Campaign source envelopes, kernel descendant limits and all preserved working-file hashes verified. All primary designs executed; every corpus execution has independent resource evidence; no expected failure waiver; every exported raw-file hash verified.'}
(export/'VERIFICATION.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
