#!/usr/bin/env python3
"""Owned official checksum-verified tools and source builds for phase two."""
import concurrent.futures,hashlib,json,os,shutil,subprocess,tarfile,urllib.request
from pathlib import Path
BASE=Path.home()/'celld-tests-20261010/phase2';INPUT=BASE/'inputs';TOOLS=BASE/'tools';TOOLS.mkdir(parents=True,exist_ok=True)
ENV={**os.environ,'PATH':str(Path.home()/'.local/share/mise/shims')+':'+str(Path.home()/'.cargo/bin')+':'+os.environ['PATH'],'RUSTUP_TOOLCHAIN':'1.98.1','CARGO_BUILD_JOBS':'8','CARGO_INCREMENTAL':'0','CARGO_PROFILE_DEV_DEBUG':'0'}
records=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def download(url,path,digest=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if not path.exists():
  with urllib.request.urlopen(url,timeout=90) as r,path.open('wb') as f:shutil.copyfileobj(r,f)
 value=sha(path)
 if digest and value!=digest:raise ValueError('checksum mismatch '+str(path))
 records.append({'url':url,'path':str(path),'sha256':value,'expected_sha256':digest});return path

def run(args,cwd,log,env=ENV):
 with log.open('ab') as f:subprocess.run(args,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=2700)

def packages():
 receipt=json.loads((INPUT/'vm/provenance/debian-installation-receipt.json').read_text());fs=json.loads((INPUT/'vm/provenance/filesystem-tools-package-verification.json').read_text())
 packages=receipt['packages'];wanted=[x for x in packages if '/sysroot/' in x['path']]
 if not wanted:wanted=[x for x in packages if x['package'] not in ['linux-image-6.12.107+deb13-amd64','busybox-static','python3.13-minimal','libpython3.13-minimal','libpython3.13-stdlib']]
 for x in fs:wanted.append({'repository_filename':'pool/main/e/e2fsprogs/'+Path(x['path']).name,'sha256':x['sha256'],'package':x['Package']})
 dest=TOOLS/'sysroot';dest.mkdir(exist_ok=True)
 for x in wanted:
  p=TOOLS/'downloads'/Path(x['repository_filename']).name
  urls=['https://deb.debian.org/debian/'+x['repository_filename'],'https://security.debian.org/debian-security/'+x['repository_filename'],'https://snapshot.debian.org/archive/debian/20260925T181338Z/'+x['repository_filename']]
  for url in urls:
   try:download(url,p,x['sha256']);break
   except urllib.error.HTTPError:continue
  else:raise RuntimeError('official package unavailable '+x['package'])
  subprocess.run(['dpkg-deb','-x',str(p),str(dest)],check=True)
 sea=json.loads((INPUT/'vm/provenance/seaweedfs-installation-receipt.json').read_text())
 p=download(sea['download_url'],TOOLS/'downloads/seaweedfs-4.48.tar.gz',sea['expected_archive_sha256'])
 with tarfile.open(p) as t:t.extractall(TOOLS/'seaweedfs',filter='data')
 assert sha(TOOLS/'seaweedfs/weed')==sea['binary']['sha256']
 dump(TOOLS/'official-downloads.json',records)
 print('Official QEMU, filesystem tools and SeaweedFS verified',flush=True)

def esbuild():
 # Official Go release metadata provides a checksum for the compiler archive.
 meta=json.load(urllib.request.urlopen('https://go.dev/dl/?mode=json&include=all',timeout=60))
 release=next(x for x in meta if x['version']=='go1.25.3');file=next(x for x in release['files'] if x['os']=='linux' and x['arch']=='amd64' and x['kind']=='archive')
 p=download('https://go.dev/dl/'+file['filename'],TOOLS/'downloads'/file['filename'],file['sha256'])
 if not (TOOLS/'go/bin/go').exists():
  with tarfile.open(p) as t:t.extractall(TOOLS,filter='data')
 source=TOOLS/'esbuild-source'
 if not source.exists():subprocess.run(['git','clone','--depth','1','--branch','v0.28.2','https://github.com/evanw/esbuild.git',str(source)],check=True,stdout=subprocess.DEVNULL)
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()
 env={**ENV,'GOPATH':str(TOOLS/'go-work'),'GOCACHE':str(TOOLS/'go-cache'),'GOTOOLCHAIN':'local','GOMAXPROCS':'8'}
 run([str(TOOLS/'go/bin/go'),'build','-mod=readonly','-trimpath','-o',str(TOOLS/'esbuild'),'./cmd/esbuild'],source,TOOLS/'esbuild-build.log',env)
 dump(TOOLS/'esbuild-build.json',{'version':'0.28.2','source_commit':commit,'go_version':'go1.25.3','binary_sha256':sha(TOOLS/'esbuild'),'go_archive':records[-1]})
 print('esbuild built from pinned source',flush=True)

def celld():
 commits=(INPUT/'commits.txt').read_text().splitlines();receipt=BASE/'builds/BUILD-RECEIPTS.json';outputs=json.loads(receipt.read_text()) if receipt.exists() else {}
 for label,commit in zip(['def239b','fixes'],commits):
  source=BASE/'builds'/commit;source.mkdir(parents=True,exist_ok=True)
  if not (source/'Cargo.toml').exists():
   with tarfile.open(INPUT/(label+'.tar')) as t:t.extractall(source,filter='data')
  # Cache remains inside this lane; build input and output receipts are independent.
  env={**ENV,'CARGO_TARGET_DIR':str(BASE/'target')}
  log=source/'build.log';run(['cargo','build','--locked','-p','celld'],source,log,env)
  binary=source/'celld'
  if binary.exists():assert sha(binary)==sha(BASE/'target/debug/celld'),'existing immutable build differs'
  else:shutil.copy2(BASE/'target/debug/celld',binary)
  pins={str(p.relative_to(source)):sha(p) for p in [source/'Cargo.toml',source/'Cargo.lock',*sorted((source/'crates').rglob('*'))] if p.is_file()}
  outputs[label]={'commit':commit,'binary':str(binary),'sha256':sha(binary),'source_sha256':hashlib.sha256(json.dumps(pins,sort_keys=True).encode()).hexdigest(),'files':pins,'command':['cargo','build','--locked','-p','celld'],'toolchain':'1.98.1','jobs':8}
  dump(BASE/'builds/BUILD-RECEIPTS.json',outputs);print('Built '+label+' '+commit,flush=True)

if __name__=='__main__':
 import sys
 {'packages':packages,'esbuild':esbuild,'celld':celld}[sys.argv[1]]()
