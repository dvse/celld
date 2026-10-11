#!/usr/bin/env python3
"""Build pinned pako authors' TypeScript with our source-built esbuild."""
import hashlib,json,subprocess,urllib.request,tarfile,base64
from pathlib import Path
base=Path.home()/'celld-tests-20261010/phase2';root=base/'tools/pako-3.0.2';source=root/'source';dest=root/'built';dest.mkdir(parents=True,exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected_commit='32be8f8e0ead1e6e8a74a1586a34f84734382d01'
expected_integrity='sha512-uBv6IT2aT1A78iU6dpNEbf6+CyhlV/6g9JlJs9kpgjFGFhruIICVRysF/W0SLzXg5+hCl+KroH7e4YUyfEmgLg=='
archive=root/'package.tgz'
if not archive.exists():
 metadata=json.load(urllib.request.urlopen('https://registry.npmjs.org/pako/3.0.2',timeout=30))
 assert metadata['gitHead']==expected_commit and metadata['dist']['integrity']==expected_integrity
 assert metadata['dist']['tarball']=='https://registry.npmjs.org/pako/-/pako-3.0.2.tgz'
 archive.write_bytes(urllib.request.urlopen(metadata['dist']['tarball'],timeout=30).read())
assert 'sha512-'+base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()==expected_integrity
if not (root/'DOWNLOAD.json').exists():
 with tarfile.open(archive) as tar:tar.extractall(root,filter='data')
 record={'url':'https://registry.npmjs.org/pako/-/pako-3.0.2.tgz','version':'3.0.2','integrity':expected_integrity,'archive_sha256':sha(archive),'files':{str(p.relative_to(root/'package')):sha(p) for p in (root/'package').rglob('*') if p.is_file()}}
 (root/'DOWNLOAD.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
if not source.exists():
 subprocess.run(['git','clone','--no-checkout','https://github.com/nodeca/pako.git',str(source)],check=True)
 subprocess.run(['git','checkout','--detach',expected_commit],cwd=source,check=True)
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip();assert commit=='32be8f8e0ead1e6e8a74a1586a34f84734382d01'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=source,text=True).strip()
receipt=json.loads((base/'tools/esbuild-build.json').read_text());assert sha(base/'tools/esbuild')==receipt['binary_sha256']
args=[str(base/'tools/esbuild'),str(source/'src/index.ts'),'--bundle','--platform=neutral','--format=esm','--target=esnext','--outfile='+str(dest/'pako.mjs')]
p=subprocess.run(args,capture_output=True,text=True);(root/'build.log').write_text(p.stdout+p.stderr);p.check_returncode()
(dest/'package.json').write_text(json.dumps({'name':'pako','version':'3.0.2','type':'module','main':'pako.mjs','exports':{'.':'./pako.mjs'}})+'\n');(dest/'LICENSE').write_bytes((source/'LICENSE').read_bytes())
r={'version':'3.0.2','repository':'https://github.com/nodeca/pako.git','commit':commit,'published_package_receipt':json.loads((root/'DOWNLOAD.json').read_text()),'source_files':{str(p.relative_to(source)):sha(p) for p in (source/'src').rglob('*') if p.is_file()},'esbuild':receipt,'command':args,'built_files':{p.name:sha(p) for p in dest.iterdir() if p.is_file()}}
(root/'BUILD.json').write_text(json.dumps(r,indent=2,sort_keys=True)+'\n');print(json.dumps({'commit':commit,'built_files':r['built_files']}))
