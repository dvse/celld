import json,sys
from pathlib import Path
from common import ROOT,TESTS,dump
p=Path(sys.argv[1]);data=json.loads((p/'RESULTS.json').read_text());data['remote_snapshot']=sys.argv[2]
for row in data['results']:
 for i,art in enumerate(row['artifacts']):
  if '/tests/artifacts/' in art:row['artifacts'][i]=str((p/art.split('/tests/artifacts/',1)[1]).relative_to(ROOT))
dump(TESTS/'RESULTS.json',data)
text=(p/'RESULTS.md').read_text();text+='\nCollected remote evidence: `'+str(p.relative_to(ROOT))+'`.\n'
(TESTS/'RESULTS.md').write_text(text)
