#!/usr/bin/env python3
"""Refresh human-readable behaviour indexes from the one manifest."""
import json
from pathlib import Path
T=Path(__file__).resolve().parents[2];m=json.loads((T/'MANIFEST.json').read_text())
for layer in ['unit','logic','conformance','faults']:
 groups={}
 for c in m['cases']:
  if c['layer']==layer:groups.setdefault(c['behaviour'],[]).append(c)
 for group,cases in groups.items():
  d=T/layer/group
  text=f'# {group}\n\n{len(cases)} cases; {sum(c["runnable"] for c in cases)} dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.\n\n| Case | Quick | Adapter |\n|---|---|---|\n'
  for c in cases:text+='| ['+c['title'].replace('|','\\|')+']('+Path(c['header']).name+') | '+('yes' if 'quick' in c['profiles'] else 'no')+' | '+(c['adapter'] if c['runnable'] else 'N/A; see header')+' |\n'
  (d/'INDEX.md').write_text(text)

 groups={}
 for c in m['cases']:
  if c['layer']==layer:groups.setdefault(c['behaviour'],[]).append(c)
 if layer=='conformance':
  text='# Workers and Durable Objects conformance\n\nBrowse by observable behaviour. Source fixtures and review contracts are immutable; runtime applicability and outcomes are recorded per column.\n\n| Behaviour | Cases | Dispatched |\n|---|---:|---:|\n'
  for group,cases in sorted(groups.items()):text+=f'| [{group}]({group}/INDEX.md) | {len(cases)} | {sum(c["runnable"] for c in cases)} |\n'
  (T/layer/'README.md').write_text(text)
