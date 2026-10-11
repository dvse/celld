"""Run tests-hyperbob shape runners (celld only) against their recorded output."""
import json,os,re,time
from common import ROOT,TESTS,clean_env,command,dump,result,safe_id
from runtime import Unavailable,executable

def cases():
    expected=json.loads((TESTS/'hyperbob-expected.json').read_text())
    out=[]
    for path in sorted((ROOT/'tests-hyperbob').iterdir()):
        if not path.is_dir():continue
        cfg=expected['cases'].get(path.name,{'runnable':False,'reason':'no recorded expectation in tests/hyperbob-expected.json'})
        runnable=cfg.get('runnable',True)
        out.append(dict(id='hyperbob/'+path.name,layer='regressions',behaviour='hyperbob-shapes',title='tests-hyperbob/'+path.name,
            origins=[{'source':'tests-hyperbob/'+path.name}],legacy_ids=[],source='tests-hyperbob/'+path.name,source_sha256=None,
            runnable=runnable,reason=None if runnable else cfg['reason'],profiles=['quick','full'],adapter='hyperbob' if runnable else 'none',
            hyperbob=dict(cfg,port=expected['port']),fixture='tests-hyperbob/'+path.name))
    return out

def run(case,runtime,out):
    if runtime!='celld':return result(case,runtime,'not-applicable','celld shape runner; no workerd adapter')
    cfg=case['hyperbob'];source=ROOT/case['fixture'];art=out/'hyperbob'/safe_id(case['id']);art.mkdir(parents=True,exist_ok=True)
    try:
        env=clean_env();env['CELLD_ESBUILD']=executable('esbuild');binary=executable('celld')
    except Unavailable as e:return result(case,runtime,'not-applicable',str(e))
    cmd=['bash','run.sh',binary,str(cfg['port'])] if cfg['runner']=='run.sh' else ['python3','run.py',binary]
    code,ms=command(cmd,source,art/'run.log',cfg.get('timeout_seconds',300),env)
    text='\n'.join(l for l in (art/'run.log').read_text(errors='replace').splitlines() if 'kill:' not in l).strip()
    passed=code==0 and re.fullmatch(cfg['expect'],text,re.S) is not None
    dump(art/'observation.json',{'command':cmd,'exit':code,'stdout':text,'expect':cfg['expect'],'pass':passed})
    return result(case,runtime,'pass' if passed else 'fail','recorded output matched' if passed else 'output or exit status differs from tests/hyperbob-expected.json (exit '+str(code)+')',ms,[art/'run.log',art/'observation.json'])
