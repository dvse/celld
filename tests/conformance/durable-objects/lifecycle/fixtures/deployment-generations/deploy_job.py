#!/usr/bin/env python3
"""Guest-only finite native deploy operator. Import/authoring never starts it."""
import hashlib,json,os,pathlib,signal,subprocess,sys,time
BINARY='62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
ALLOWED={'v1','v2-add','v2-rebuild','v2-unique','v2-abort','v2-code','v2-sibling','v2-binding','v2-omitted','v2-script','bad-syntax','bad-rename','front-old','front-new','front-missing'}
def atomic_json(path,value):
 temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value));temporary.replace(path)
def terminate_owned_child(p,fd):
 """Popen owns and exclusively reaps this child. An unreaped child PID cannot be reused."""
 if p.poll() is None:
  if fd is not None:signal.pidfd_send_signal(fd,signal.SIGKILL)
  else:p.kill()  # Popen's own unreaped child only; never an externally supplied PID.
 return p.communicate(timeout=3)
def main(version,bucket,directory):
 import re
 if version not in ALLOWED or not re.fullmatch('upg-[a-f0-9]{16}',bucket):raise ValueError('unowned deploy target')
 directory=pathlib.Path(directory)
 if not str(directory).startswith('/tmp/'+bucket+'-deploy-') or directory.exists():raise ValueError('fresh owned result directory required')
 directory.mkdir();binary=pathlib.Path('/stage/direct/celld')
 if hashlib.sha256(binary.read_bytes()).hexdigest()!=BINARY:raise ValueError('frozen deploy executable mismatch')
 env=os.environ.copy();env.update(AWS_ACCESS_KEY_ID='test-only',AWS_SECRET_ACCESS_KEY='test-only',AWS_ALLOW_HTTP='true',CELLD_TOKIO_THREADS='2')
 args=[str(binary),'deploy','/stage/deployment-recovery/versions/'+version,'--bucket',bucket,'--endpoint','http://192.168.77.2:19000','--region','us-east-1','--json']
 p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
 # Immediately own child lifetime, including every fallible identity/evidence step.
 fd=None;identity=None;operator_error=None;capture=None;out=b'';err=b'';timed_out=False;started=time.monotonic()
 try:
  fd=os.pidfd_open(p.pid)
  base=pathlib.Path('/proc',str(p.pid))
  try:
   fields=(base/'stat').read_text().rsplit(')',1)[1].split();exe=str((base/'exe').resolve(strict=True))
   if exe!=str(binary):raise RuntimeError('native child executable path differs')
   identity={'pid':p.pid,'exe':exe,'start_ticks':fields[19],'sha256':BINARY};capture='live-proc-executable-and-prelaunch-file-digest'
  except (FileNotFoundError,ProcessLookupError):
   # A fast refusal/success can exit before /proc/exe is available. Its Popen receipt
   # and publication or stderr oracle remain valid; it cannot be a fault target.
   if p.poll() is None:raise
   capture='exited-before-live-proc-witness'
  atomic_json(directory/'child.json',{'identity':identity,'launch_binary_sha256':BINARY,'capture':capture})
  try:out,err=p.communicate(timeout=max(.1,35-(time.monotonic()-started)))
  except subprocess.TimeoutExpired:
   timed_out=True;out,err=terminate_owned_child(p,fd)
 except Exception as error:
  operator_error=repr(error)
 finally:
  try:
   if p.poll() is None:out,err=terminate_owned_child(p,fd)
  except Exception as error:
   operator_error=(operator_error or '')+'; child cleanup: '+repr(error)
  finally:
   if fd is not None:os.close(fd)
 record={'version':version,'argv':args,'exit_code':p.returncode,'timed_out':timed_out,'operator_error':operator_error,'stdout':out[-65536:].decode(errors='replace'),'stderr':err[-65536:].decode(errors='replace'),'output_truncated':len(out)>65536 or len(err)>65536,'elapsed':time.monotonic()-started,'identity':identity,'identity_capture':capture,'launch_binary_sha256':BINARY}
 atomic_json(directory/'result.json',record)
if __name__=='__main__':main(*sys.argv[1:])
