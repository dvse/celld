#!/usr/bin/env python3
"""Validate complete column coverage and export every old N/A disposition."""
import argparse,collections,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('matrix',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=json.loads(a.baseline.read_text());current=json.loads(a.matrix.read_text());audit=[]
for label,column in current['columns'].items():
 rows=column['results'];keys={(r['id'],r['runtime']) for r in rows};assert len(keys)==len(rows)
 assert column['profile']=='full' and not column['arguments'].get('case') and not column['arguments'].get('layer')
 assert dict(collections.Counter(r['status'] for r in rows))==column['counts']
 index={(r['id'],r['runtime']):r for r in rows}
 for previous in old['results']:
  if previous['status']!='not-applicable':continue
  now=index[(previous['id'],previous['runtime'])]
  audit.append({'column':label,'id':previous['id'],'runtime':previous['runtime'],'previous_reason':previous['reason'],'status':now['status'],'reason':now['reason'],'artifacts':now['artifacts']})
a.output.write_text(json.dumps({'previous_run':old['run_id'],'dispositions':audit},indent=2)+'\n')
print('Audited',len(audit),'prior N/A dispositions across',len(current['columns']),'columns')
