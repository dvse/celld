"""Only JSON, Python AST, hashes and Node --check. No fixture imports or workload."""
import ast,hashlib,json,pathlib,re,subprocess
HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def main():
 rows=json.loads((HERE/'manifest.json').read_text());assert len(rows)==24
 ids=[r['id'] for r in rows];assert ids==[f'W{i:03}' for i in range(1,25)]
 source=json.loads((HERE/'source-pins.json').read_text());assert source['binary_sha256']=='8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f'
 assert sha(source['runtime_manifest'])==source['runtime_manifest_sha256']
 runtime=json.loads(pathlib.Path(source['runtime_manifest']).read_text());assert runtime['binary_sha256']==source['binary_sha256']
 for item in source['sources']:
  assert sha(item['path'])==item['sha256']
  if item['role']=='candidate-direct':assert runtime['source_hashes'][item['manifest_key']]==item['sha256']
 cases=(HERE/'cases.js').read_text();assert re.findall(r'export async function (W\d{3})\(',cases)==ids
 for row in rows:
  for key in ('intent','failure_hypothesis','preconditions','trace','stress','oracle','executable_assertions','cleanup','distinctness','source_contracts'):assert row[key],(row['id'],key)
  assert len(row['trace'])>=4 and row['status']=='NOT_RUN'
  assert row['counts']=={'authored':1,'reviewed':0,'executable_qualified':0,'run':0,'passed':0}
 assert len({r['failure_hypothesis'] for r in rows})==24
 assert [r['id'] for r in rows if r['gate']=='characterization']==['W023','W024']
 for file in HERE.glob('*.py'):ast.parse(file.read_text(),filename=str(file))
 for name in ('common.js','fixture.js','lab.js','cases.js'):subprocess.run(['node','--check',str(HERE/name)],check=True,capture_output=True)
 for name in ('package.json','wrangler.jsonc','profile.json'):json.loads((HERE/name).read_text())
 profile=json.loads((HERE/'profile.json').read_text());assert profile['binary_sha256']==source['binary_sha256']
 assert profile['limits']['preflight_timeout_ms']+profile['limits']['trace_timeout_ms']+profile['limits']['cleanup_timeout_ms']<profile['limits']['fixture_evidence_wall_ms_max']
 hashes={str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in ('static-evidence.json','review.json')}
 out={'status':'STATIC_CHECKS_ONLY','authored_candidates':24,'promotion_candidates':22,'characterizations':2,'independent_review':0,'runtime_cases_executed':0,'runtime_passes':0,'native_tests_executed':0,'network_actions':0,'builds':0,'checks':['24 literal case IDs and schema','Python AST syntax','Node --check syntax only','candidate manifest and7 source snapshot digests','profile bounds and zero-execution counters'],'implementation_hashes':hashes,'does_not_prove':'Runtime APIs, transport behavior, imposed resource limits, supervisor suitability, cross-VM or OS workflow correctness; no fixture or system-under-test source was executed.'}
 (HERE/'static-evidence.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:out[k] for k in ('status','authored_candidates','runtime_cases_executed','runtime_passes','checks')}))
if __name__=='__main__':main()
