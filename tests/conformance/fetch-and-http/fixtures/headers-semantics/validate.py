#!/usr/bin/env python3
"""Static packaging checks only. Does not execute test bodies or the SUT."""
import hashlib, json, pathlib, re, subprocess
HERE=pathlib.Path(__file__).resolve().parent
manifest=json.loads((HERE/'manifest.json').read_text())
pins=json.loads((HERE/'source-pins.json').read_text())
root=pathlib.Path(pins['source_root'])
for path,expected in pins['files'].items():
    assert hashlib.sha256((root/path).read_bytes()).hexdigest()==expected, path
source=(HERE/'cases.js').read_text()
functions=re.findall(r'^export (?:async )?function (V\d+)\(',source,re.M)
ids=[case['id'] for case in manifest]
assert len(ids)==18 and len(set(ids))==18
assert ids==functions, (ids,functions)
for case in manifest:
    assert case['status']=='NOT_RUN' and case['actual_runs']==0 and case['runtime_passes']==0
    assert case['independently_reviewed'] is False
    assert case['trace'] and case['oracle'] and case['source_refs'] and case['distinctness']
    body=source.split('function '+case['id']+'(t)',1)[1].split('\nexport ',1)[0]
    assert re.search(r't\.(?:eq|same|done)\(',body),case['id']
    for ref in case['source_refs']:
        assert ref['path'] in pins['files']
        lines=(root/ref['path']).read_text().splitlines()
        assert 1<=ref['line_start']<=ref['line_end']<=len(lines)
for name in ('cases.js','fixture.js'):
    subprocess.run(['node','--input-type=module','--check'],input=(HERE/name).read_bytes(),check=True)
config=json.loads((HERE/'wrangler.jsonc').read_text())
assert config['main']=='fixture.js'
result=dict(kind='STATIC_ONLY',source_pins_verified=len(pins['files']),candidate_functions=len(ids),javascript_syntax_files=2,runtime_executions=0,independent_review='pending')
(HERE/'static-report.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
