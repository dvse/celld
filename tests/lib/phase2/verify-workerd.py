#!/usr/bin/env python3
import base64,hashlib,json,tarfile,urllib.request
from pathlib import Path
base=Path.home()/'celld-tests-20261010/phase2/tools';version='1.20261010.1';package='@cloudflare/workerd-linux-64'
meta=json.load(urllib.request.urlopen('https://registry.npmjs.org/'+package+'/'+version,timeout=45));dist=meta['dist'];data=urllib.request.urlopen(dist['tarball'],timeout=90).read();integrity='sha512-'+base64.b64encode(hashlib.sha512(data).digest()).decode();assert integrity==dist['integrity']
p=base/'downloads/workerd-linux-64.tgz';p.write_bytes(data)
with tarfile.open(p) as t:t.extractall(base/'stock-workerd',filter='data')
binary=base/'stock-workerd/package/bin/workerd'
(base/'stock-workerd/RECEIPT.json').write_text(json.dumps({'version':version,'package':package,'source':dist['tarball'],'integrity':integrity,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()},indent=2)+'\n')
print('Verified stock workerd',version)
