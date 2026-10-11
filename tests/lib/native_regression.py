"""Stage fix-owned native assertions against unchanged production crate bytes."""
from pathlib import Path
import hashlib,json,os,shutil,time
from common import ROOT,TESTS,clean_env,command,dump,result,sha

def run_alarm(case,runtime,source,art):
    started=time.monotonic()
    files=[ROOT/'Cargo.toml',ROOT/'Cargo.lock',*[p for p in (ROOT/'crates').rglob('*') if p.is_file()]]
    pins={str(p.relative_to(ROOT)):sha(p) for p in files}
    snippet=source/'native.rs'
    module='crates/celld/js/ownership_tests.rs'
    already_included='tests/regressions/R4-04/native.rs' in (ROOT/module).read_text()
    addition=b'' if already_included else b'\ninclude!("regression_R4_04.rs");\n'
    key=hashlib.sha256(json.dumps({'files':pins,'snippet':sha(snippet),'adapter':2},sort_keys=True).encode()).hexdigest()
    stage=TESTS/'artifacts/native-regression-builds'/key/'source'
    if not stage.exists():
        stage.mkdir(parents=True)
        for p in files:
            dst=stage/p.relative_to(ROOT);dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
        target=stage/'crates/celld/js/ownership_tests.rs'
        with target.open('ab') as f:f.write(addition)
        shutil.copy2(snippet,target.parent/'regression_R4_04.rs')
    # Newer production modules include fix-owned native regression snippets.
    # Copy these unmodified dependencies even when reusing a staged crate.
    includes={}
    for dependency in (TESTS/'regressions').rglob('*.rs'):
        relative=dependency.relative_to(ROOT);target=stage/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists() and sha(target)!=sha(dependency):return result(case,runtime,'fail','native include cache differs from pinned regression source',artifacts=[target])
        if not target.exists():shutil.copy2(dependency,target)
        includes[str(relative)]=sha(dependency)
    dump(art/'source-includes.json',includes)
    module='crates/celld/js/ownership_tests.rs'
    expected_module=(ROOT/module).read_bytes()+addition
    intact=all((stage/k).is_file() and sha(stage/k)==v for k,v in pins.items() if k!=module)
    if not intact or (stage/module).read_bytes()!=expected_module or sha(stage/'crates/celld/js/regression_R4_04.rs')!=sha(snippet):
        return result(case,runtime,'fail','native staging cache differs from pinned source; retained for inspection',artifacts=[stage])
    # Share only this lane's dependency cache; the source checkout is immutable.
    baseline=Path.home()/'celld-tests-20261010/build-source'
    if not baseline.is_dir() or not all((baseline/k).is_file() and sha(baseline/k)==v for k,v in pins.items()):baseline=ROOT
    env=clean_env();env.update(CARGO_INCREMENTAL='0',CARGO_BUILD_JOBS='4',CARGO_PROFILE_DEV_DEBUG='0',CARGO_TARGET_DIR=os.environ.get('CARGO_TARGET_DIR',str(baseline/'target')))
    name='js::ownership_tests::r4_04_alarm_wall_time_revokes_incarnation_and_drops_ready_io'
    dump(art/'adapter.json',{'original_command':case['regression']['command'],'adapter':'isolated crate copy with unchanged native.rs included in ownership_tests; exact one-test selection','inclusion':'existing production include' if already_included else 'staged include appended','source_files':pins,'snippet_sha256':sha(snippet),'stage':str(stage),'target_dir':env['CARGO_TARGET_DIR'],'test_name':name,'staged_module_sha256':sha(stage/'crates/celld/js/ownership_tests.rs')})
    def finish(status,reason):
        return result(case,runtime,status,reason,round((time.monotonic()-started)*1000),[art/'adapter.json',art/'source-includes.json',art/'build.log',art/'binary.json',art/'selection.log',art/'run.log'])
    cargo=shutil.which('cargo')
    if not cargo:return finish('not-applicable','cargo is not installed for the native alarm ownership regression')
    code,_=command([cargo,'test','--locked','--manifest-path',stage/'Cargo.toml','-p','celld','--lib','--no-run','--message-format=json'],stage,art/'build.log',case['regression'].get('timeout_seconds',600),env)
    if code:return finish('fail','native regression build failed (exit '+str(code)+'); see build.log')
    binary=None
    for line in (art/'build.log').read_text().splitlines():
        try:obj=json.loads(line)
        except ValueError:continue
        if obj.get('reason')=='compiler-artifact' and obj.get('executable') and obj.get('profile',{}).get('test'):binary=Path(obj['executable'])
    if not binary:return finish('fail','cargo emitted no native regression test executable')
    dump(art/'binary.json',{'path':str(binary),'sha256':sha(binary)})
    code,_=command([binary,name,'--exact','--list'],stage,art/'selection.log',30,env)
    listing=(art/'selection.log').read_text().splitlines()
    if code or [line for line in listing if line.endswith(': test')]!=[name+': test']:
        return finish('fail','native regression did not select exactly its one assertion')
    code,_=command([binary,name,'--exact','--nocapture','--test-threads=1'],stage,art/'run.log',60,env,limits={'cpu':60,'cpus':1})
    passed=code==0 and '1 passed; 0 failed;' in (art/'run.log').read_text()
    return finish('pass' if passed else 'fail','exact native alarm assertion passed' if passed else 'exact native alarm assertion failed (exit '+str(code)+'); see run.log')
