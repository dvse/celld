#!/usr/bin/env python3
"""Materialize explicitly named immutable fixture versions. No case generation or SUT run."""
import json,pathlib
HERE=pathlib.Path(__file__).resolve().parent
body=(HERE/'fixture-body.js').read_text()
# Each entry is a distinct deployment feature/fault, not a version/size/seed case matrix.
versions={
 'v1':('v1','base','upgrade-test',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
 'v2-add':('v2-add','add','upgrade-test',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
 'v2-rebuild':('v2-rebuild','rebuild','upgrade-test',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
 'v2-unique':('v2-unique','unique','upgrade-test',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
 'v2-abort':('v2-abort','abort','upgrade-test',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
 'v2-code':('v2-code','base','upgrade-test',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
 'v2-sibling':('v2-sibling','base','upgrade-test',['UpgradeRoot','SiblingRoot'],{'ROOT':'UpgradeRoot','SIBLING':'SiblingRoot'}),
 'v2-binding':('v2-binding','base','upgrade-test',['UpgradeRoot'],{'RENAMED':'UpgradeRoot'}),
 'v2-omitted':('v2-omitted','base','upgrade-test',['SiblingRoot'],{'SIBLING':'SiblingRoot'}),
 'v2-script':('v2-script','base','upgrade-renamed',['UpgradeRoot'],{'ROOT':'UpgradeRoot'}),
}
for name,(build,mode,script,classes,bindings) in versions.items():
 root=HERE/'versions'/name;root.mkdir(parents=True,exist_ok=True)
 (root/'fixture.js').write_text('const BUILD = '+json.dumps(build)+'; const MODE = '+json.dumps(mode)+';\n'+body)
 config={'name':script,'main':'fixture.js','no_bundle':True,'compatibility_date':'2026-01-01','durable_objects':{'bindings':[{'name':k,'class_name':v} for k,v in bindings.items()]},'migrations':[{'tag':'initial','new_sqlite_classes':classes}]}
 (root/'wrangler.jsonc').write_text(json.dumps(config,indent=2)+'\n')
# Intentionally invalid JS is a native generation-build refusal, never syntax-checked as valid.
root=HERE/'versions'/'bad-syntax';root.mkdir(parents=True,exist_ok=True)
(root/'fixture.js').write_text('export default { fetch( { // intentionally truncated parser failure\n')
(root/'wrangler.jsonc').write_text((HERE/'versions/v1/wrangler.jsonc').read_text())
# Unsupported migration is submitted to the real CLI and must fail before publication.
root=HERE/'versions'/'bad-rename';root.mkdir(parents=True,exist_ok=True)
(root/'fixture.js').write_text((HERE/'versions/v1/fixture.js').read_text())
cfg=json.loads((HERE/'versions/v1/wrangler.jsonc').read_text());cfg['migrations'].append({'tag':'rename','renamed_classes':[{'from':'UpgradeRoot','to':'SiblingRoot'}]})
(root/'wrangler.jsonc').write_text(json.dumps(cfg,indent=2)+'\n')
for name,target,entry in [('front-old','upgrade-test','OldAPI'),('front-new','upgrade-test','NewAPI'),('front-missing','upgrade-missing','NewAPI')]:
 root=HERE/'versions'/name;root.mkdir(parents=True,exist_ok=True);(root/'fixture.js').write_text((HERE/'front.js').read_text())
 (root/'wrangler.jsonc').write_text(json.dumps({'name':'upgrade-front','main':'fixture.js','no_bundle':True,'compatibility_date':'2026-01-01','services':[{'binding':'BACKEND','service':target,'entrypoint':entry}]},indent=2)+'\n')
