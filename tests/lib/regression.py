"""Execute fix-lane contracts without changing their owned source files."""
import difflib,json,time
from common import ROOT,clean_env,command,dump,result,safe_id,sha
from runtime import Runtime,Unavailable,executable,fetch

HTTP_MODES={'R4-08':['prototype','instance'],'R4-10':['disabled','enabled'],'R5-09':['prototype','instance']}

def http_fixture(case,runtime,source,art):
    """Execute an unchanged HTTP fixture and exact oracle on assigned ports."""
    started=time.monotonic();rt=None;art.mkdir(parents=True,exist_ok=True)
    try:
        rt=Runtime(source,runtime,art/'runtime')
        observed=fetch(rt.port,{'path':'/','timeout':45});expected=json.loads((source/'expected.json').read_text());actual=observed['body']
        passed=observed['status']==200 and actual==expected
        dump(art/'observation.json',{'http_status':observed['status'],'actual':actual,'expected':expected,'pass':passed})
        artifacts=[art/'observation.json',art/'runtime/runtime.log',art/'runtime/runtime.json']
        if not passed:
            diff=art/'expected.diff';diff.write_text(''.join(difflib.unified_diff(json.dumps(expected,indent=2,sort_keys=True).splitlines(True),json.dumps(actual,indent=2,sort_keys=True).splitlines(True),fromfile='expected',tofile=runtime)));artifacts.append(diff)
        return result(case,runtime,'pass' if passed else 'fail','fix-lane exact expected-output assertion passed' if passed else 'fix-lane expected-output mismatch; see diff',round((time.monotonic()-started)*1000),artifacts)
    except Exception as e:return result(case,runtime,'not-applicable' if isinstance(e,Unavailable) else 'fail',str(e),round((time.monotonic()-started)*1000),[art])
    finally:
        if rt:rt.stop()

def command_case(case,runtime,profile,source,art,cmd):
    cfg=case.get('regression',{});art.mkdir(parents=True,exist_ok=True)
    dump(art/'command.json',{'command':cmd,'source_commit_contract':case['source_sha256'],'harness_source_sha256':sha(ROOT/'crates/celld/js/harness.js'),'case_sources':{p.name:sha(p) for p in source.iterdir() if p.is_file()}})
    env=clean_env();env.update(CELLD_TEST_ARTIFACTS=str(art),CELLD_TEST_PORT_BASE='9840',CELLD_TEST_RUNTIME=runtime,CELLD_TEST_PROFILE=profile)
    try:
        env['CELLD_BIN']=executable('celld');env['WORKERD_BIN']=executable('workerd')
        code,ms=command(cmd,source,art/'run.log',cfg.get('timeout_seconds',120),env)
        return result(case,runtime,'pass' if code==0 else 'not-applicable' if code==77 else 'fail','regression command passed' if code==0 else 'unavailable prerequisite: '+(art/'run.log').read_text()[-600:].strip() if code==77 else 'fix-lane assertion or command failed (exit '+str(code)+'); see run.log',ms,[art/'run.log',art/'command.json'])
    except Unavailable as e:return result(case,runtime,'not-applicable',str(e))

def run(case,runtime,profile,out):
    cfg=case.get('regression',{});source=ROOT/case['fixture'];art=out/'regressions'/safe_id(case['id'])/runtime;art.mkdir(parents=True)
    if runtime not in cfg.get('runtimes',['celld']):return result(case,runtime,'not-applicable','finding regression declares no '+runtime+' adapter')
    cmd=cfg.get('command') or (['python3','run.py'] if (source/'run.py').exists() else ['bash','run.sh'])
    # The fix-lane HTTP command's celld-dev launcher selects an ephemeral internal
    # listener. Execute its unchanged fixture and exact expected.json oracle via
    # our deploy/node launcher, whose listeners stay in the assigned port range.
    if cfg.get('id')=='R4-02' and cmd==['python3','run.py']:
        dump(art/'adapter.json',{'original_command':cmd,'adapter':'unchanged injected-failure command on celld plus unchanged HTTP reference control on both runtimes; execute every applicable part','original_runner_sha256':sha(source.parent/'http_case.py'),'case_sources':{str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}})
        parts={}
        if runtime=='celld':parts['injected-failure']=command_case(case,runtime,profile,source,art/'injected-failure',['node','run.mjs'])
        parts['http']=http_fixture(case,runtime,source/'http',art/'http')
        dump(art/'parts.json',parts)
        status='fail' if any(r['status']=='fail' for r in parts.values()) else 'not-applicable' if any(r['status']=='not-applicable' for r in parts.values()) else 'pass'
        return result(case,runtime,status,'; '.join(name+': '+row['reason'] for name,row in parts.items()),sum(r['duration_ms'] for r in parts.values()),[art/'adapter.json',art/'parts.json',*[p for r in parts.values() for p in r['artifacts']]])
    if (cmd==['python3','../http_case.py'] and (source/'expected.json').exists()) or cfg.get('id') in HTTP_MODES:
        modes=HTTP_MODES.get(cfg.get('id'),['.'])
        dump(art/'adapter.json',{'original_command':cmd,'adapter':'unchanged HTTP fixtures + exact expected JSON via bounded Runtime; all modes required','modes':modes,'original_runner_sha256':sha(source.parent/'http_case.py'),'case_sources':{str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}})
        rows=[http_fixture(case,runtime,source/mode,art/mode) for mode in modes]
        dump(art/'modes.json',dict(zip(modes,rows)))
        status='fail' if any(r['status']=='fail' for r in rows) else 'not-applicable' if any(r['status']=='not-applicable' for r in rows) else 'pass'
        return result(case,runtime,status,'; '.join(mode+': '+row['reason'] for mode,row in zip(modes,rows)),sum(r['duration_ms'] for r in rows),[art/'adapter.json',art/'modes.json',*[p for r in rows for p in r['artifacts']]])
    if cfg.get('id')=='R5-03':
        from facet_regression import run_snapshot
        return run_snapshot(case,runtime,source,art)
    if cfg.get('id')=='R4-04':
        from native_regression import run_alarm
        return run_alarm(case,runtime,source,art)
    return command_case(case,runtime,profile,source,art,cmd)
