from pathlib import Path
import json,os,shutil
from common import ROOT,TESTS,command,dump,result,sha,safe_id,clean_env
class Cargo:
    def __init__(self,out):self.out=out/'cargo';self.out.mkdir();self.ready=False;self.binary=None;self.error=None
    def prepare(self):
        self.ready=True;manifest=ROOT/'Cargo.toml';existing=Path.home()/'celld-tests-20261010/build-source'
        source_pins={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'crates').rglob('*') if p.is_file()}
        # Reuse this lane's build checkout only after every crate byte matches.
        if existing.is_dir() and all((existing/k).is_file() and sha(existing/k)==v for k,v in source_pins.items()) and (existing/'Cargo.lock').read_bytes()==(ROOT/'Cargo.lock').read_bytes():manifest=existing/'Cargo.toml'
        env=clean_env();env.update(CARGO_INCREMENTAL='0',CARGO_BUILD_JOBS='4',CARGO_PROFILE_DEV_DEBUG='0')
        dump(self.out/'source-pins.json',{'manifest':str(manifest),'files':source_pins})
        cargo=shutil.which('cargo')
        if not cargo:self.error='cargo is not installed';return
        code,_=command([cargo,'test','--locked','--manifest-path',manifest,'-p','celld','--lib','--no-run','--message-format=json'],ROOT,self.out/'build.log',900,env)
        if code:self.error='cargo library test build failed';return
        for line in (self.out/'build.log').read_text().splitlines():
            try:obj=json.loads(line)
            except ValueError:continue
            if obj.get('reason')=='compiler-artifact' and obj.get('executable') and obj.get('profile',{}).get('test'):self.binary=Path(obj['executable'])
        if not self.binary:self.error='cargo emitted no test executable';return
        dump(self.out/'binary.json',{'path':str(self.binary),'sha256':sha(self.binary)})
    def run(self,case,runtime):
        if runtime!='celld':return result(case,runtime,'not-applicable','Rust celld library unit test; stock workerd has no corresponding Rust crate')
        if not self.ready:self.prepare()
        if not self.binary:return result(case,runtime,'fail',self.error,artifacts=[self.out/'build.log'])
        log=self.out/(safe_id(case['id'])+'.log');code,ms=command([self.binary,case['test_filter'],'--exact','--nocapture','--test-threads=1'],ROOT,log,30)
        passed=code==0 and '1 passed;' in log.read_text()
        return result(case,runtime,'pass' if passed else 'fail','exact celld crate assertion passed' if passed else 'crate test failed, timed out or matched no tests',ms,[log,self.out/'source-pins.json',self.out/'binary.json'])
