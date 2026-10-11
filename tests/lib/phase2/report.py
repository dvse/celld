#!/usr/bin/env python3
"""Publish two independently complete columns without collapsing oracle outcomes."""
import collections,datetime,hashlib,json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];T=ROOT/'tests'
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
export=Path(sys.argv[1]).resolve();meta=json.loads((export/'MATRIX.json').read_text());manifest=json.loads((T/'MANIFEST.json').read_text());pins=json.loads((T/'lib/phase2/PINS.json').read_text());columns={}
expected={(c['id'],r) for c in manifest['cases'] if 'full' in c['profiles'] for r in ['celld','workerd']}
for label in ['def239b','fixes']:
 x=json.loads((export/label/'RESULTS.json').read_text());assert x['source_commit']==pins['source_columns'][label]
 assert {(r['id'],r['runtime']) for r in x['results']}==expected,(label,'incomplete profile coverage')
 assert len(x['results'])==len(expected)
 for row in x['results']:
  row['artifacts']=[str((export/a).relative_to(ROOT)) for a in row['artifacts']]
  assert all((ROOT/a).exists() for a in row['artifacts'])
 columns[label]=x
status_changes=[]
a={(r['id'],r['runtime']):r for r in columns['def239b']['results']};b={(r['id'],r['runtime']):r for r in columns['fixes']['results']}
for key in sorted(expected):
 if a[key]['status']!=b[key]['status']:status_changes.append({'id':key[0],'runtime':key[1],'def239b':a[key]['status'],'fixes':b[key]['status'],'baseline_reason':a[key]['reason'],'fixes_reason':b[key]['reason']})
report={'schema_version':3,'kind':'source-column-matrix','profile':'full','source_pins':pins,'matrix':str(export.relative_to(ROOT)),'columns':columns,'status_changes':status_changes,'logical_case_count':len(manifest['cases']),'design_census':manifest['design_census'],'vm_evidence':'tests/evidence/phase2-vm/GATES.json'}
# Preserve the previous public report before publishing a new one.
stamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=10))).strftime('%Y%m%d-%H%M%S-AEST');history=T/'evidence/report-history'/stamp;history.mkdir(parents=True)
for name in ['RESULTS.json','RESULTS.md']:
 if (T/name).exists():shutil.copy2(T/name,history/name)
dump(T/'RESULTS.json',report)
text='# Phase 2 test results\n\n'
text+=f"Full qualification on the fleet host: **{len(manifest['cases'])} cases per source column**, with stock workerd executed independently alongside each. All 786 designs are accounted for: 671 primary and 115 non-promoting characterization designs.\n\n"
text+='Primary binaries were built here from `def239b8b5bea70bfe8674f3117d6862f140a711` and fixes HEAD snapshot `c877e5523378b189a4dc3e5798572b8d03a81345` (2026-10-10 18:53 AEST). Rust/unit/logic sources match each binary revision. Build/tool receipts and immutable harness hashes are included in the evidence.\n\n'
text+=f"Qualified Git trees: baseline `{pins['source_trees']['def239b']}`; fixes `{pins['source_trees']['fixes']}`. The later `ported` branch contains further changes and is outside this frozen qualification; it is the preferred ref for the next source refresh. These results do not claim coverage of its newer tree.\n\n"
text+='| Layer / runtime | def239b pass | fail | N/A | fixes pass | fail | N/A |\n|---|---:|---:|---:|---:|---:|---:|\n'
for layer in ['unit','logic','conformance','faults','regressions','TOTAL']:
 for runtime in ['celld','workerd']:
  counts=[collections.Counter(r['status'] for r in columns[label]['results'] if (layer=='TOTAL' or r['layer']==layer) and r['runtime']==runtime) for label in ['def239b','fixes']]
  text+='| '+layer+' / '+runtime+' | '+' | '.join(str(c[k]) for c in counts for k in ['pass','fail','not-applicable'])+' |\n'
improvements=[r for r in status_changes if r['runtime']=='celld' and r['def239b']=='fail' and r['fixes']=='pass']
new_failures=[r for r in status_changes if r['runtime']=='celld' and r['def239b']=='pass' and r['fixes']=='fail']
text+=f"\nCelld has {len(improvements)} fail-to-pass changes and {len(new_failures)} pass-to-fail changes between these executions. These observations alone do not establish the cause.\n"
for change in new_failures:
 text+=f"\n- Pass-to-fail: `{change['id']}` — {change['fixes_reason']}\n"
regressions=[r for r in columns['fixes']['results'] if r['runtime']=='celld' and r['layer']=='regressions']
failed_regressions=[r['id'] for r in regressions if r['status']=='fail']
text+=f"\nThe fixes column passes {sum(r['status']=='pass' for r in regressions)} of {len(regressions)} finding regressions. Remaining failures: {', '.join('`'+x+'`' for x in failed_regressions) or 'none'}.\n"
text+='\nCounts are case/runtime executions, not assertions or seeds. No expected-failure waiver converts a failure into a pass. The source-authored corpus reports each runtime’s assertions independently and records comparisons. Older exact HTTP differential cases mark both rows failed on mismatch; their raw observations remain available. Failure rows include source-fixture BLOCKED/unsupported-API outcomes and assertion failures; an attempted test is not automatically a completed passing trace.\n\n'
for label,x in columns.items():
 text+=f"- **{label}**: `{json.dumps(x['counts'],sort_keys=True)}`; run `{x['run_id']}`; {x['wall_duration_ms']/1000:.1f} seconds; [{label} evidence]({export.relative_to(T)}/{label}/RESULTS.json).\n"
text+='\nResumed columns retain all unaffected prior outcomes, including failures, after verifying the same source revision and each retained case contract. New or changed contracts and explicit invalidations always execute. All 31 runtime corpus waves were invalidated and executed with independent resource/deadline supervision and the original recovery freshness preconditions. The 16 newer campaign groups were subsequently replaced again under their exact source limits, kernel cgroup controls and an owned quota filesystem; both missing oracle bundle dependencies were repaired and rerun. Three stock namespace-routing groups and the native alarm include were then explicitly invalidated and requalified. Ancestor raw runs, stop times and both harness receipts are retained; the reported wall time is the final segment, with preceding spans in resumption metadata.\n' if any(x.get('resumption') for x in columns.values()) else ''
text+='\nAll 671 reviewed primary cases were dispatched on celld. Six declared conformance exclusions remain: two external model-service examples, container and sandbox execution requiring host-wide privileged Docker fencing, the missing Python ABI dependency bundle, and the full WPT tree. Stock workerd has additional explicit N/A rows for celld-specific bucket leases/deployment controls and service backends absent from its standalone binary. [Every former N/A disposition](NA-AUDIT.json) is recorded for both columns.\n\n'
text+='The two-VM shared-store gate passed on both primary builds. **Cold-restart-v1 failed on both**: count 4, celld snapshot durability and owner release passed, but SeaweedFS exceeded the unchanged 45-second TERM limit and required SIGKILL. Generation 2 was not entered. Exact historical candidate002 also passed shared-store and failed this shutdown boundary; it never entered a primary suite column. [All twelve VM attempts](evidence/phase2-vm/README.md) retain their receipts and raw-state hashes. The separate historical graceful-migration gate cannot be reconstructed from the supplied store helper/run records because its supervisor/client/fixture archive is absent.\n\n'
text+='[Verdict changes between source revisions](STATUS-CHANGES.json) are observations, not an attribution of every change to a production fix. The same file includes oracle variation between runs. Per-case failures, reasons, full traces and comparisons are indexed in each column’s RESULTS.json. [Harness and provenance](lib/phase2/README.md) describes process identity, clocks, fault controls, staging changes and qualification limits.\n\n'
text+='Campaign runs use kernel memory/swap/CPU/task limits and a bounded private filesystem; process-count, aggregate RSS and CPU-time checks add independent sampling. Every working file is retained and hash-verified before releasing its mount. [Real exhaustion and escaped-child checks](evidence/phase2-campaign-domain/20261010-202403-AEST/RECEIPT.json) verify those controls. Git-codec uses a fresh deployment/process per case and source-built pinned pako.\n\n'
text+='Three additional native facet-snapshot assertions passed on the exact fixes source; [their independent receipt](evidence/phase2-native-facet/RECEIPT.json) and source hashes are retained without adding logical-case credit.\n\n'
text+='All raw logs, stores, binaries and guest disks remain under `~/celld-tests-20261010/phase2` on the fleet host. The committed review export omits credentials and storage payloads and hashes retained files. Exploratory/superseded attempts remain separate and earn no final pass credit.\n'
if (export/'VERIFICATION.json').exists():
 verification=json.loads((export/'VERIFICATION.json').read_text());assert verification['status']=='PASS'
 hashes=sum(c['exported_file_hashes_verified'] for c in verification['columns'].values())
 text+=f"\n[Final integrity audit]({export.relative_to(T)}/VERIFICATION.json): PASS. Both complete columns, all {verification['prior_na_dispositions']:,} prior N/A dispositions, {verification['vm_attempts_verified']} VM attempts, {verification['selected_vm_gates_verified']} selected VM gates, binary/source pins, resource limits and {hashes:,} exported file hashes were verified. The audit also indexes retained log symlink targets and their content hashes; the earlier export is preserved.\n"
if (export/'TERMINAL.json').exists():
 terminal=json.loads((export/'TERMINAL.json').read_text());assert terminal['status']=='PASS'
 text+=f"\n[Terminal-state check]({export.relative_to(T)}/TERMINAL.json) found no owned processes, running units or listeners on ports 9800–9899.\n"
(T/'RESULTS.md').write_text(text);dump(T/'STATUS-CHANGES.json',status_changes)
print(json.dumps({k:v['counts'] for k,v in columns.items()},sort_keys=True))
