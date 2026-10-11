"""Keep the authored facet oracles; supply only the lane's bounded launcher."""
import ast,json,os,time,traceback
from common import dump,result,sha
from runtime import Runtime

def run_snapshot(case,runtime,source,art):
    from regression import http_fixture
    started=time.monotonic()
    parts={'snapshot':http_fixture(case,runtime,source,art/'snapshot')}
    dump(art/'adapter.json',{'source_sha256':sha(source/'fault.py'),'adapter':'unchanged HTTP expected.json plus original fault.py call function; bounded launcher and .celld alias to owned storage replace only dev launch','fault_scope':'celld owned facet directories only; original finally restores modes'})
    if runtime=='celld':
        directory=art/'output-fault';directory.mkdir();rt=None
        saved={k:os.environ.get(k) for k in ['CELLD_TEST_ARTIFACTS','CELLD_TEST_PORT_BASE']}
        try:
            rt=Runtime(source,runtime,directory/'runtime',bounded=True)
            (directory/'.celld').symlink_to(rt.out/'celld-storage',target_is_directory=True)
            os.environ.update(CELLD_TEST_ARTIFACTS=str(directory),CELLD_TEST_PORT_BASE=str(rt.port))
            tree=ast.parse((source/'fault.py').read_text())
            # Drop only the shared dev launcher and the monkeypatch it needs.
            assert ast.unparse(tree.body[-2])=='urllib.request.urlopen = call'
            assert ast.unparse(tree.body[-1]).startswith('runpy.run_path(')
            tree.body=tree.body[:-2];namespace={'__file__':str(source/'fault.py')}
            exec(compile(tree,str(source/'fault.py'),'exec'),namespace)
            rt.guard.begin(case['id']+'/output-fault',90)
            value=json.load(namespace['call']('http://127.0.0.1:'+str(rt.port)+'/'))
            passed=value=={'blocked':True}
            dump(directory/'observation.json',{'actual':value,'expected':{'blocked':True},'pass':passed})
            status='pass' if passed else 'fail';reason='original copy-failure response assertion '+('passed' if passed else 'failed')
        except Exception as error:
            status='fail';reason=str(error);dump(directory/'error.json',{'error':str(error),'traceback':traceback.format_exc()})
        finally:
            for key,value in saved.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
            if rt:rt.stop()
        if rt and rt.guard and rt.guard.violations:status='fail';reason='independent resource/deadline guard rejected qualification'
        parts['output-fault']=result(case,runtime,status,reason,artifacts=[directory/'observation.json',directory/'copy-failure.json',directory/'error.json',directory/'runtime/runtime.log',directory/'runtime/resource-guard.json'])
    dump(art/'parts.json',parts)
    status='pass' if all(p['status']=='pass' for p in parts.values()) else 'fail'
    return result(case,runtime,status,'; '.join(name+': '+p['reason'] for name,p in parts.items()),round((time.monotonic()-started)*1000),[art/'adapter.json',art/'parts.json',*[a for p in parts.values() for a in p['artifacts']]])
