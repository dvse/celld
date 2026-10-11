#!/usr/bin/env python3
import hashlib,json,lzma,re,subprocess,urllib.request
from pathlib import Path
from provision import BASE,TOOLS,download,records,dump
# Official repository hashes, including every transitive runtime dependency.
release=urllib.request.urlopen('https://deb.debian.org/debian/dists/trixie/Release',timeout=60).read().decode()
part=release.split('SHA256:\n')[1].split('\n\n')[0];digest=next(line.split()[0] for line in part.splitlines() if line.split()[-1]=='main/binary-amd64/Packages.xz')
a=download('https://deb.debian.org/debian/dists/trixie/main/binary-amd64/Packages.xz',TOOLS/'downloads/trixie-Packages.xz',digest)
packages={}
for paragraph in lzma.decompress(a.read_bytes()).decode().split('\n\n'):
 row={}
 for line in paragraph.splitlines():
  if ': ' in line and not line.startswith(' '):k,v=line.split(': ',1);row[k]=v
 if 'Package' in row:packages[row['Package']]=row
installed={}
for p in (TOOLS/'downloads').glob('*.deb'):
 name=subprocess.check_output(['dpkg-deb','-f',str(p),'Package'],text=True).strip();installed[name]=p
queue=['qemu-system-x86','qemu-system-common','e2fsprogs'];seen=set()
while queue:
 name=queue.pop()
 if name in seen:continue
 seen.add(name)
 if name in installed:
  p=installed[name];deps=subprocess.check_output(['dpkg-deb','-f',str(p),'Depends','Pre-Depends'],text=True)
 else:
  if name not in packages:raise RuntimeError('Unresolved package '+name)
  row=packages[name];p=download('https://deb.debian.org/debian/'+row['Filename'],TOOLS/'downloads'/Path(row['Filename']).name,row['SHA256']);installed[name]=p;deps=row.get('Depends','')+','+row.get('Pre-Depends','')
 for dep in deps.replace('Depends:','').replace('Pre-','').split(','):
  choices=[re.split(r'[ (:\[]',s.strip())[0] for s in dep.split('|')]
  choice=next((c for c in choices if c in installed or c in packages),None)
  if choice:queue.append(choice)
 subprocess.run(['dpkg-deb','-x',str(p),str(TOOLS/'sysroot')],check=True)
dump(TOOLS/'sysroot-dependencies.json',{'packages':sorted(seen),'downloads':records,'release_sha256':hashlib.sha256(release.encode()).hexdigest()})
print('Verified and extracted',len(seen),'transitive packages')
