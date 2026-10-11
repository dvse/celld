#!/usr/bin/env python3
"""Static source/design validation only; never invokes the runtime adapter."""
import ast,collections,hashlib,json,pathlib,subprocess,sys
HERE=pathlib.Path(__file__).resolve().parent
PROJECT=pathlib.Path('/workspace/shared/celld-os-project')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    records=json.loads((HERE/'manifest.json').read_text());ids=[r['id'] for r in records]
    assert ids==['A001','A002','A003','A004','A005','A006','A007','A008','A009','A010','A011','A012','A013','A014','A015','A016','A017','A018','A019','A020','A021','A022','A023','A024','A025','A026','A027','A028']
    source=(HERE/'cases.py').read_text();tree=ast.parse(source);functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    assert all(i in functions for i in ids)
    assert len({ast.dump(ast.Module(body=functions[i].body,type_ignores=[]),include_attributes=False) for i in ids})==28
    for r in records:
        for field in ['intent','preconditions','trace','stress','oracle','stress_dimension','oracles','cleanup']:assert r[field],(r['id'],field)
        assert r['status']=='NOT_RUN' and r['runtime_runs']==r['runtime_passes']==0
        body=ast.get_source_segment(source,functions[r['id']]);assert ('check(' in body or 'exact(' in body),r['id']
        assert r['implementation']=='cases.py:'+r['id'] and r['test_function']==r['id']
    for path in sorted(HERE.glob('*.py')):ast.parse(path.read_text())
    result=subprocess.run(['node','--input-type=module','--check'],input=(HERE/'fixture.js').read_text(),text=True,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    pins=json.loads((HERE/'source-pins.json').read_text())
    for item in pins['sources']:assert sha(PROJECT/item['path'])==item['sha256'],item['path']
    for label,runtime in pins['runtimes'].items():
        path=PROJECT/runtime['manifest'];assert sha(path)==runtime['manifest_sha256'],label
        manifest=json.loads(path.read_text());assert manifest['binary_sha256']==runtime['binary_sha256'],label
        for item in runtime['contracts']:
            assert sha(PROJECT/item['path'])==item['sha256'],item['path']
            assert manifest['source_hashes'][item['key']]==item['sha256'],item['key']
    checks=subprocess.run([sys.executable,str(HERE/'test_preflight.py')],text=True,capture_output=True,timeout=20)
    assert checks.returncode==0,checks.stdout+checks.stderr
    names=['cases.py','fixture.js','driver.py','http_jobs.py','wrangler.jsonc','manifest.json','source-pins.json','bucket-profile.json','author_manifest.py','test_preflight.py','validate.py','README.md']
    output={'kind':'STATIC_ONLY_NOT_PRODUCT_EVIDENCE','authored':28,'executable_source':28,'independently_reviewed':0,'runtime_runs':0,'runtime_passes':0,'classifications':dict(collections.Counter(r['classification'] for r in records)),'python_parse':'PASS','javascript_syntax':'PASS','source_relationships':'PASS','pure_preflight_tests':checks.stderr.strip(),'implementation_hashes':{n:sha(HERE/n) for n in names}}
    (HERE/'static-evidence.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
if __name__=='__main__':main()
