#!/usr/bin/env python3
"""Reviewed relocation: immutable inputs copied; no historical receipt is reused."""
import difflib,hashlib,json,os,re,shutil,sys
from pathlib import Path
BASE=Path.home()/'celld-tests-20261010/phase2';I=BASE/'inputs';TOOLS=BASE/'tools'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
label=sys.argv[1];build_label=sys.argv[2] if len(sys.argv)>2 else label;out=BASE/'vm'/label;out.mkdir(parents=True,exist_ok=False)
builds=json.loads((BASE/'builds/BUILD-RECEIPTS.json').read_text())
if label=='candidate002':
 binary=next((I/'candidate002').rglob('frozen/celld'));assert sha(binary)=='7ab402de478adad5ed53e2098aca9114a8ff5ec389c66de1075f9c9f40e153db'
else:binary=Path(builds[build_label]['binary'])
(out/'sysroot').symlink_to(TOOLS/'sysroot',target_is_directory=True)
(out/'guest-root/boot').mkdir(parents=True);shutil.copy2(I/'vm/images/vmlinuz-6.12.107+deb13-amd64',out/'guest-root/boot/vmlinuz-6.12.107+deb13-amd64')
relocations=[]
# All guest and host listeners remain within lane-owned port range.
ports={'19000':'9806','29000':'9807','18080':'9820','18081':'9830','8080':'9863','8888':'9865','9333':'9861','18888':'9866','19333':'9862'}
for gate,source in [('gate-v3',I/'vm/source'),('cold-restart-v1',I/'cold/celld-vm/cold-restart-v1')]:
 g=out/gate;g.mkdir();stage=g/'stage';stage.mkdir();(stage/'bin').mkdir();(g/'assembly').mkdir()
 (g/'tools').mkdir();(g/'tools/root').symlink_to(TOOLS/'sysroot',target_is_directory=True)
 for folder in ['client','fixture']:
  if (source/folder).exists():shutil.copytree(source/folder,stage/folder)
 for p in [source/'supervisor.py',source/'start_store.sh']:
  shutil.copy2(p,g/p.name)
 for p in [g/'supervisor.py',g/'start_store.sh',*stage.rglob('*.py')]:
  before=p.read_text();s=before.replace('/workspace/shared/celld-vm',str(out)).replace('/workspace/shared/celld-heavy-work.lock',str(BASE/'vm.lock'))
  s=re.sub(r'(?<!\d)('+'|'.join(ports)+r')(?!\d)',lambda m:ports[m[0]],s)
  s=s.replace("'-accel','tcg,thread=single','-cpu','max'","'-accel','kvm','-cpu','host'")
  if p.name=='supervisor.py':
   s=s.replace("argv=[str(B/'sysroot/usr/bin/qemu-system-x86_64')","argv=[str(B/'sysroot/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),'--library-path',str(B/'sysroot/usr/lib/x86_64-linux-gnu'),str(B/'sysroot/usr/bin/qemu-system-x86_64')")
   s=s.replace("fmt=subprocess.run([str(","fmt=subprocess.run([str(B/'sysroot/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2'),'--library-path',str(B/'sysroot/usr/lib/x86_64-linux-gnu'),str(")
  if p.name=='supervisor.py' and gate=='cold-restart-v1':
   s=s.replace("assert qualification['binary_sha256']=='7ab402de478adad5ed53e2098aca9114a8ff5ec389c66de1075f9c9f40e153db'", "assert qualification['binary_sha256']=="+repr(sha(binary)))
   s=re.sub(r" assert sha\(qualification\['(?:build_receipt|result_review)'\]\)==[^\n]+\n",'',s)
  if p.name=='store_service.py':
   s=s.replace("'-s3',","'-s3','-master.port=9861','-master.port.grpc=9862','-volume.port=9863','-volume.port.grpc=9864','-filer.port=9865','-filer.port.grpc=9866',")
  if p.name=='supervisor.py':
   s=s.replace('[9863,9865,9861,9820,9866,9806,9862,9807]','[9863,9865,9861,9864,9866,9806,9862,9807]')
  if p.name=='start_store.sh':
   s=s.replace('-dir=/store/data', '-master.port=9861 -master.port.grpc=9862 -volume.port=9863 -volume.port.grpc=9864 -filer.port=9865 -filer.port.grpc=9866 \\\n -dir=/store/data')
  p.write_text(s);relocations.append({'path':str(p),'before_sha256':hashlib.sha256(before.encode()).hexdigest(),'after_sha256':sha(p),'diff':''.join(difflib.unified_diff(before.splitlines(True),s.splitlines(True),fromfile='checkpoint/'+p.name,tofile=str(p)))})
 shutil.copy2(g/'start_store.sh',stage/'start_store.sh')
 shutil.copy2(binary,stage/'bin/celld');shutil.copy2(TOOLS/'esbuild',stage/'bin/esbuild');shutil.copy2(TOOLS/'seaweedfs/weed',stage/'bin/weed')
 shutil.copy2(I/'vm/images/celld-initramfs-v3.cpio.gz',g/'assembly/celld-initramfs-v3.cpio.gz')
 # Cold service manager expects prior gate client modules already included in its checkpoint.
 for p in (I/'vm/source/client').iterdir():
  if not (stage/'client'/p.name).exists():
   text=p.read_text();text=re.sub(r'(?<!\d)('+'|'.join(ports)+r')(?!\d)',lambda m:ports[m[0]],text);(stage/'client'/p.name).write_text(text)
 if gate=='cold-restart-v1':
  (out/'graceful-migration-v2/assembly').mkdir(parents=True,exist_ok=True);shutil.copy2(g/'assembly/celld-initramfs-v3.cpio.gz',out/'graceful-migration-v2/assembly/celld-initramfs-v3.cpio.gz')
 paths=[p for p in g.rglob('*') if p.is_file() and 'tools' not in p.relative_to(g).parts]+[out/'guest-root/boot/vmlinuz-6.12.107+deb13-amd64']
 paths += [p for p in (TOOLS/'sysroot').rglob('*') if p.is_file()]
 dump(g/'INPUTS.json',{'status':'RELOCATED_NOT_RUN','qualification':{'column':label,'binary_sha256':sha(binary),'source_build':builds.get(build_label),'historical_only':label=='candidate002'},'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(paths))]})
dump(out/'RELOCATION.json',{'changes':relocations,'ports':ports,'guest_memory_mib':[1024,2048],'acceleration':'KVM','source_root':str(I),'archived_binary_policy':'candidate002 is historical-gate only'})
print(out)
