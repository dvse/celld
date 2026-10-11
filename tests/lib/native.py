"""Compile unchanged assertion bodies against this checkout's real decision core."""
from pathlib import Path
import os, re, shutil
from common import ROOT,TESTS,command,dump,result,sha,safe_id
class Native:
    def __init__(self,out,mutation=None):
        self.mutation=mutation;self.out=out/'native';self.out.mkdir(parents=True);self.cache={};self.core=None
    def compile(self,source):
        if source in self.cache:return self.cache[source]
        rustc=os.environ.get('RUSTC') or shutil.which('rustc')
        if not rustc:return None,'rustc is not installed',[]
        if self.core is None:
            lib=self.out/'libcelld_logic.rlib';log=self.out/'core-build.log'
            core_source=ROOT/'crates/logic/lib.rs'
            if self.mutation:
                copy=self.out/'mutated-logic';shutil.copytree(ROOT/'crates/logic',copy)
                core_source=copy/'lib.rs';original=core_source.read_text()
                anchor='if now_ms >= prior.record.expires_ms\n                || now_mono_ms.saturating_sub(prior.last_ok_mono_ms) >= prior.spec.ttl_ms'
                assert original.count(anchor)==1,'mutation anchor changed; requires review'
                replacement='if false' if self.mutation=='omit-prior-expiry' else 'if now_ms >= prior.record.expires_ms'
                core_source.write_text(original.replace(anchor,replacement))
                import difflib
                (self.out/'mutation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),core_source.read_text().splitlines(True),fromfile='production/lib.rs',tofile='mutant/lib.rs')))
            code,_=command([rustc,'--crate-name' ,'celld_logic','--crate-type','rlib','--edition=2021','-C','debuginfo=0','-C','codegen-units=1',core_source,'-o',lib],ROOT,log,90,limits={'cpu':60,'memory':1024**3,'cpus':1})
            self.core=(lib if code==0 else False)
            dump(self.out/'source-pins.json',{str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'crates/logic').glob('*.rs'))})
        if not self.core:return None,'current celld-logic failed to compile',[self.out/'core-build.log']
        source_path=ROOT/source;staged=self.out/(safe_id(source)+'.rs')
        if source.endswith('lease_continuity.rs'):
            staged.write_text(source_path.read_text()+'\n'+(source_path.parent/'guard_predicate.rs').read_text())
        elif source.endswith('simulation.rs'):
            # Include helpers and original assertions unchanged; select only sim_ filters.
            base=(TESTS/'logic/lease-continuity/lease_continuity.rs').read_text()
            staged.write_text(base+'\n'+source_path.read_text())
        else:staged.write_bytes(source_path.read_bytes())
        binary=staged.with_suffix('.bin');log=staged.with_suffix('.build.log')
        code,_=command([rustc,'--test','--edition=2021','--crate-name','suite','-C','debuginfo=0','-C','codegen-units=1',staged,'--extern',f'celld_logic={self.core}','-o',binary],ROOT,log,90,limits={'cpu':60,'memory':1024**3,'cpus':1})
        record=(binary if code==0 else None,'assertion source no longer compiles against current logic' if code else '',[log,self.out/'source-pins.json'])
        self.cache[source]=record;return record
    def run(self,case,runtime,profile):
        if runtime!='celld':return result(case,runtime,'not-applicable','Rust decision-core assertion; stock workerd has no celld-logic crate')
        if case.get('mutation') and not self.mutation:
            mutated=Native(self.out/('broken-'+case['mutation']),case['mutation'])
            return mutated.run(case,runtime,profile)
        binary,reason,artifacts=self.compile(case['source'])
        if not binary:return result(case,runtime,'fail' if self.core is False or artifacts else 'not-applicable',reason,artifacts=artifacts)
        log=self.out/(safe_id(case['id'])+'.log');env=os.environ.copy();env['CELLD_SIM_SEEDS']='10000' if profile=='full' else '64'
        code,ms=command([binary,case['test_filter'],'--exact','--test-threads=1','--nocapture'],ROOT,log,60 if case.get('mutation') or 'simulation/' in case['id'] else 10,env,limits={'cpu':60 if 'simulation/' in case['id'] else 10,'memory':1024**3,'cpus':1})
        text=log.read_text();passed=code==0 and '1 passed;' in text
        if self.mutation:
            caught=code not in (0,124) and 'expired lease returned:' in text and 'seed=' in text
            return result(case,runtime,'pass' if caught else 'fail','checker found pinned expired-authority counterexample in compiled broken protocol' if caught else 'broken protocol escaped checker or failed for an unrelated reason',ms,[log,*artifacts,self.out/'mutation.diff'])
        return result(case,runtime,'pass' if passed else 'fail','exact Rust assertion passed' if passed else ('assertion timeout' if code==124 else 'Rust assertion failed or filter matched no tests'),ms,[log,*artifacts])
