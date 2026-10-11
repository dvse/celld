#!/usr/bin/env python3
import argparse,collections,datetime,json,os,platform,signal,subprocess,sys,time,traceback
from pathlib import Path
from common import ROOT,TESTS,command,dump,result,reserve_ports,safe_id
from inventory import build
from native import Native
from cargo import Cargo
from conformance import run_group

def write_summary(out,rows,meta):
    totals=collections.Counter(r['status'] for r in rows)
    layer_order=['unit','logic','conformance','faults','regressions']
    selected_layers=[meta['arguments']['layer']] if meta['arguments'].get('layer') else layer_order
    selected_runtimes=['celld','workerd'] if meta['arguments']['runtime']=='both' else [meta['arguments']['runtime']]
    by={(layer,runtime):collections.Counter() for layer in selected_layers for runtime in selected_runtimes}
    for r in rows:by.setdefault((r['layer'],r['runtime']),collections.Counter())[r['status']]+=1
    behaviour_counts={}
    case_behaviours={c['id']:c['behaviour'] for c in json.loads((TESTS/'MANIFEST.json').read_text())['cases']}
    for row in rows:behaviour_counts.setdefault((row['layer'],case_behaviours[row['id']],row['runtime']),collections.Counter())[row['status']]+=1
    summary={**meta,'counts':dict(totals),'by_layer_runtime':[dict(layer=k[0],runtime=k[1],**{s:c[s] for s in ['pass','fail','expected-fail','not-applicable']}) for k,c in sorted(by.items(),key=lambda kv:(layer_order.index(kv[0][0]),kv[0][1]))],'results':rows}
    summary['by_behaviour_runtime']=[dict(layer=layer,behaviour=behaviour,runtime=runtime,**{status:counts[status] for status in ['pass','fail','expected-fail','not-applicable']}) for (layer,behaviour,runtime),counts in sorted(behaviour_counts.items())]
    summary['reviewed_corpus_counts']={runtime:dict(collections.Counter(r['status'] for r in rows if r['runtime']==runtime and r['id'] in meta['reviewed_case_ids'])) for runtime in selected_runtimes}
    summary['regression_import']=json.loads((TESTS/'regressions/IMPORT.json').read_text())
    dump(out/'results.json',summary)
    dump(TESTS/'RESULTS.json',summary)
    text=f"# Test results\n\nRun `{meta['run_id']}` — {meta['started_aest']}; profile `{meta['profile']}`, host `{meta['host']}`, source `{meta['source_commit']}`.\n\n"
    text+='Counts are case/runtime executions, not assertions or seeds. A paired differential mismatch marks both runtime executions as failed; each pair has one diff. Native logic runs only on celld; workerd entries explain non-applicability. Missing prerequisites never count as passes.\n\n'
    text+='| Layer | Runtime | Pass | Fail | Expected fail | Not applicable |\n|---|---|---:|---:|---:|---:|\n'
    for x in summary['by_layer_runtime']:text+='| '+' | '.join(str(x[k]) for k in ['layer','runtime','pass','fail','expected-fail','not-applicable'])+' |\n'
    text+='\nFeature-level counts are recorded in `RESULTS.json` under `by_behaviour_runtime`; browse case headers through `conformance/README.md`.\n'
    text+='\nReviewed corpus: **671 primary cases** in `MANIFEST.json`; selected runtime execution counts are distinct from that census. The 115 characterization/design entries earn no additional credit.\n\n'
    text+='Reviewed corpus outcomes in this run: `'+json.dumps(summary['reviewed_corpus_counts'],sort_keys=True)+'`.\n\n'
    imported=summary['regression_import'];text+=f"Fix-lane snapshot: `{imported['commit']}`; {len(imported['files'])} imported regression/vendor files. Zero rows means no committed regressions were available at that snapshot.\n\n"
    if meta.get('wall_duration_ms') is not None:text+=f"Execution wall time: {meta['wall_duration_ms']/1000:.1f} seconds; completed {meta['finished_aest']}.\n\n"
    text+=f"Run evidence: `{out.relative_to(ROOT)}`. Per-case JSON, stdout, source/binary hashes, staged fixtures, store journals and diffs are retained there. `RESULTS.json` contains every selected result and exact artifact paths.\n\n"
    failures=[r for r in rows if r['status'] in ('fail','expected-fail')]
    if failures:
        text+='## Failures and expected failures\n\n'
        for r in failures:text+=f"- `{r['id']}` ({r['runtime']}): {r['status']} — {r['reason']}\n"
    text+='\n## Scope limits\n\nThe supplied TLA+ specifications and full upstream WPT dependencies are absent. Original corpus VM/resource qualification requirements remain recorded per case. Local fleet faults use an append-only S3-compatible test store, not a commercial storage service. Local process stop does not claim provider-level host power loss.\n'
    (out/'RESULTS.md').write_text(text);(TESTS/'RESULTS.md').write_text(text)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--profile',choices=['quick','full'],required=True);p.add_argument('--layer',choices=['unit','logic','conformance','faults','regressions']);p.add_argument('--runtime',choices=['celld','workerd','both'],default='both');p.add_argument('--remote-worker',action='store_true');p.add_argument('--case',help='optional case substring for focused reproduction')
    p.add_argument('--resume-results',type=Path,help='preserved partial results');p.add_argument('--resume-compatible-source',action='store_true',help='allow suite-only revision changes after verifying identical crates/manifests/lock');p.add_argument('--rerun-wave',action='append',default=[],help='invalidate this corpus wave before resuming');p.add_argument('--rerun-case',action='append',default=[],help='invalidate this exact case before resuming');a=p.parse_args()
    if a.profile=='full' and not a.remote_worker:
        return subprocess.call([str(TESTS/'lib/full-remote.sh'),*sys.argv[1:]])
    for sig in [signal.SIGTERM,signal.SIGHUP]:signal.signal(sig,lambda signum,frame:sys.exit(128+signum))
    wall_start=time.monotonic();lock=reserve_ports();inv=build();runtimes=['celld','workerd'] if a.runtime=='both' else [a.runtime]
    cases=[c for c in inv['cases'] if a.profile in c['profiles'] and (not a.layer or c['layer']==a.layer) and (not a.case or any(a.case in x for x in [c['id'],*c.get('legacy_ids',[])]))]
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10)));runid=now.strftime('%Y%m%d-%H%M%S-AEST')+'-'+str(os.getpid());out=TESTS/'artifacts'/runid;out.mkdir(parents=True)
    commit=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,text=True,capture_output=True).stdout.strip() or os.environ.get('CELLD_TEST_SOURCE_COMMIT','exported-source')
    meta=dict(schema_version=1,run_id=runid,started_aest=now.isoformat(),profile=a.profile,host=platform.node(),source_commit=commit,arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(a).items()},reviewed_case_ids=[c['id'] for c in inv['cases'] if c.get('reviewed')],manifest_sha256=__import__('hashlib').sha256((TESTS/'MANIFEST.json').read_bytes()).hexdigest())
    retained=[];completed=set()
    if a.resume_results:
        prior=json.loads(a.resume_results.read_text());prior_meta=json.loads((a.resume_results.parent/'configuration.json').read_text());prior_manifest=json.loads((a.resume_results.parent/'manifest.json').read_text())
        assert isinstance(prior,list),'resume expects raw partial-results.json'
        same_revision=prior_meta['source_commit']==commit
        if not same_revision:
            assert a.resume_compatible_source,'resume source revision differs'
            check=subprocess.run(['git','diff','--name-only',prior_meta['source_commit'],commit,'--','crates','Cargo.toml','Cargo.lock'],cwd=ROOT,text=True,capture_output=True,check=True)
            assert not check.stdout.strip(),'resume compiled runtime source differs'
            meta['resume_runtime_compatibility']={'prior_commit':prior_meta['source_commit'],'current_commit':commit,'paths_verified':['crates/','Cargo.toml','Cargo.lock'],'git_diff':check.stdout,'scope':'runtime byte identity; changed case contracts rerun below'}
        prior_cases={c['id']:c for c in prior_manifest['cases']}
        selected={c['id']:c for c in cases};by={}
        for row in prior:by.setdefault(row['id'],[]).append(row)
        for id,existing in by.items():
            if id not in selected or selected[id]!=prior_cases.get(id) or id in a.rerun_case or selected[id].get('corpus_wave') in a.rerun_wave:continue
            if {r['runtime'] for r in existing}==set(runtimes):retained.extend(existing);completed.add(id)
        meta['resumption']={'prior_results':str(a.resume_results),'prior_run_id':prior_meta['run_id'],'retained_case_ids':sorted(completed),'invalidated_waves':a.rerun_wave,'invalidated_cases':a.rerun_case,'new_or_changed_case_ids':sorted(id for id,c in selected.items() if c!=prior_cases.get(id)),'source_revision_verified':same_revision,'runtime_source_verified':True,'case_contracts_verified':True,'policy':'retain every unchanged case contract outcome, including failures; execute every new, changed, incomplete or explicitly invalidated case/group'}
        meta['ancestor_raw_runs']=[str(a.resume_results.parent),*prior_meta.get('ancestor_raw_runs',[])]
        meta['resumption']['prior_started_aest']=prior_meta['started_aest']
        stop=a.resume_results.parent/'STOPPED.json'
        if stop.exists():meta['resumption']['prior_stop']=json.loads(stop.read_text())
        dump(out/'resumption.json',meta['resumption'])
    dump(out/'configuration.json',meta);dump(out/'manifest.json',inv)
    rows=[];native=Native(out);cargo=Cargo(out);groups={};fleet=[];topologies={};recoveries={};deployments={}
    def record(new):
        rows.extend(new)
        for r in new:
            d=out/'cases'/safe_id(r['id'])/(r['runtime']+'.json');dump(d,r)
            if r['status']!='not-applicable':print(r['status'],r['runtime'],r['id'],flush=True)
        dump(out/'partial-results.json',rows)
    if retained:record(retained)
    for c in cases:
        if c['id'] in completed:continue
        if not c['runnable']:record([result(c,r,'not-applicable',c['reason']) for r in runtimes]);continue
        if c['adapter']=='native':record([native.run(c,r,a.profile) for r in runtimes])
        elif c['adapter']=='cargo':record([cargo.run(c,r) for r in runtimes])
        elif c['adapter']=='http':groups.setdefault(c['fixture']+('/'+safe_id(c['id']) if c.get('isolated') else ''),[]).append(c)
        elif c['adapter']=='deployment':deployments.setdefault(c['corpus_wave'],[]).append(c)
        elif c['adapter']=='recovery':recoveries.setdefault(c['corpus_wave'],[]).append(c)
        elif c['adapter']=='topology':topologies.setdefault(c['corpus_wave'],[]).append(c)
        elif c['adapter']=='fleet':fleet.append(c)
        elif c['adapter']=='python':
            for r in runtimes:
                if r!='celld':record([result(c,r,'not-applicable','shared celld harness contract; no workerd implementation')]);continue
                art=out/'unit'/safe_id(c['id']);art.mkdir(parents=True)
                from common import clean_env
                env=clean_env();env['CELLD_TEST_ARTIFACTS']=str(art)
                code,ms=command(['python3',ROOT/c['source']],ROOT,art/'run.log',30,env)
                record([result(c,r,'pass' if code==0 else 'fail','store transport contract assertions passed' if code==0 else 'store transport contract failed',ms,[art/'run.log'])])
        elif c['adapter']=='example':
            from phase2.examples import run as run_example
            record(run_example(c,runtimes,out/'examples'/safe_id(c['id'])))
        elif c['adapter']=='hyperbob':
            from hyperbob import run as run_hyperbob
            record([run_hyperbob(c,r,out) for r in runtimes])
        elif c['adapter']=='regression':
            from regression import run
            record([run(c,r,a.profile,out) for r in runtimes])
    for fixture,group in groups.items():
        print('fixture',fixture,flush=True)
        try:record(run_group(group,runtimes,out/'conformance'/safe_id(fixture)))
        except Exception as e:
            log=out/(safe_id(fixture)+'.harness-error.log');log.write_text(traceback.format_exc());record([result(c,r,'fail','harness exception: '+str(e),artifacts=[log]) for c in group for r in runtimes])
    for wave,group in topologies.items():
        from phase2.topology import run_group as run_topology
        record(run_topology(group,runtimes,out/"topology"/wave))
    for wave,group in recoveries.items():
        from phase2.recovery import run_group as run_recovery
        record(run_recovery(group,runtimes,out/"recovery"/wave))
    for wave,group in deployments.items():
        from phase2.deployment import run_group as run_deployments
        record(run_deployments(group,runtimes,out/"deployment"/wave))
    if fleet:
        from fleet import run_fleet
        record(run_fleet(fleet,runtimes,out/'faults'))
    meta.update(finished_aest=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))).isoformat(),wall_duration_ms=round((time.monotonic()-wall_start)*1000))
    summary=write_summary(out,rows,meta);print(json.dumps({'run':runid,'counts':summary['counts']}),flush=True)
    return 1 if any(r['status']=='fail' for r in rows) else 0
if __name__=='__main__':raise SystemExit(main())
