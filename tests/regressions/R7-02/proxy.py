"""Gate authenticated RPC request bytes; never invent a stale-owner response."""
import socket,threading,select,time
class Proxy:
 def __init__(self,port,target):
  self.target=target;self.running=True;self.armed=False;self.arrived=threading.Event();self.release=threading.Event();self.sockets=[];self.events=[]
  self.listener=socket.socket();self.listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);self.listener.bind(('127.0.0.1',port));self.listener.listen();threading.Thread(target=self.accept,daemon=True).start()
 def arm(self):self.arrived.clear();self.release.clear();self.armed=True
 def close(self):
  self.running=False;self.release.set();self.listener.close()
  for c in self.sockets:
   try:c.shutdown(socket.SHUT_RDWR);c.close()
   except OSError:pass
 def accept(self):
  while self.running:
   try:c,_=self.listener.accept()
   except OSError:return
   self.sockets.append(c);threading.Thread(target=self.serve,args=(c,),daemon=True).start()
 def head(self,c):
  head=b''
  while not head.endswith(b'\r\n\r\n'):
   b=c.recv(1)
   if not b:raise EOFError()
   head+=b
  return head
 def pipe(self,a,b):
  try:
   while self.running:
    data=a.recv(65536)
    if not data:return
    b.sendall(data)
  except OSError:pass
  finally:
   for c in [a,b]:
    try:c.shutdown(socket.SHUT_RDWR)
    except OSError:pass
 def serve(self,c):
  up=None
  try:
   head=self.head(c);rpc=b'x-cells-tunnel-kind: rpc' in head.lower()
   up=socket.create_connection(('127.0.0.1',self.target),timeout=30);up.settimeout(None);self.sockets.append(up);up.sendall(head)
   if not rpc:
    threading.Thread(target=self.pipe,args=(up,c),daemon=True).start();self.pipe(c,up);return
   reply=self.head(up);c.sendall(reply)
   if b' 101 ' not in reply.split(b'\r\n')[0]:return
   threading.Thread(target=self.pipe,args=(up,c),daemon=True).start()
   while self.running:
    head=self.head(c)
    if self.armed and b'x-cells-rpc-method: accept' in head.lower():
     self.armed=False;self.events.append({'gated':True,'time_ns':time.time_ns()});self.arrived.set()
     if not self.release.wait(30):raise TimeoutError('gate')
    up.sendall(head)
    rows=head.decode('latin1').split('\r\n');h={r.split(':',1)[0].lower():r.split(':',1)[1].strip() for r in rows[1:] if ':' in r}
    n=int(h.get('content-length','0'))
    if 'chunked' in h.get('transfer-encoding',''):raise RuntimeError('unexpected chunked RPC')
    while n:
     data=c.recv(min(65536,n))
     if not data:raise EOFError()
     up.sendall(data);n-=len(data)
  except (EOFError,OSError,TimeoutError) as e:pass
  finally:
   for sock in [c,up]:
    if sock:
     try:sock.shutdown(socket.SHUT_RDWR);sock.close()
     except OSError:pass
