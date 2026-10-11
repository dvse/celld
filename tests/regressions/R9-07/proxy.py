"""Private TCP fault proxy. Session sockets remain connected during RPC faults."""
import socket,threading,json,select
class Proxy:
 def __init__(self,port,target):
  self.target=target;self.mode='normal';self.events=[];self.tunnels=[];self.sessions=[];self.connections=[];self.running=True
  self.listener=socket.socket();self.listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);self.listener.bind(('127.0.0.1',port));self.listener.listen()
  threading.Thread(target=self.accept,daemon=True).start()
 def close(self):
  self.running=False;self.listener.close()
  for c in self.connections:
   try:c.shutdown(socket.SHUT_RDWR);c.close()
   except OSError:pass
 def cut_sessions(self):
  count=len(self.sessions)
  for pair in self.sessions:
   for c in pair:
    try:c.shutdown(socket.SHUT_RDWR);c.close()
    except OSError:pass
  self.sessions=[];self.events.append({'session_connections_cut':count})
  return count
 def arm(self,mode):
  self.mode=mode
  if mode=='tunnel':
   for pair in self.tunnels:
    for c in pair:
     try:c.shutdown(socket.SHUT_RDWR);c.close()
     except OSError:pass
   self.tunnels=[]
 def accept(self):
  while self.running:
   try:c,_=self.listener.accept()
   except OSError:return
   self.connections.append(c);threading.Thread(target=self.serve,args=(c,),daemon=True).start()
 def serve(self,c):
  upstream=None
  try:
   c.settimeout(30);head=b''
   while b'\r\n\r\n' not in head:
    chunk=c.recv(1)
    if not chunk:return
    head+=chunk
   rows=head.decode('latin1').split('\r\n');path=rows[0].split()[1]
   headers={row.split(':',1)[0].lower():row.split(':',1)[1].strip() for row in rows[1:] if ':' in row}
   rpc=path=='/peer/tunnel' and headers.get('x-cells-tunnel-kind')=='rpc'
   if rpc and self.mode=='tunnel':self.events.append({'fault':'tunnel','delivered':False});return
   body=b''
   length=int(headers.get('content-length','0'))
   while len(body)<length:
    chunk=c.recv(length-len(body))
    if not chunk:return
    body+=chunk
   direct=path=='/peer/capability'
   method=None
   if direct:method=json.loads(body).get('path',[None])[0] if json.loads(body).get('path') else None
   if direct and method=='accept' and self.mode=='request':self.events.append({'fault':'request','delivered':False});return
   upstream=socket.create_connection(('127.0.0.1',self.target),timeout=30);self.connections.append(upstream)
   if direct:
    rows=[r for r in rows[1:] if r and not r.lower().startswith('connection:')]
    head=(head.decode('latin1').split('\r\n',1)[0]+'\r\n'+'\r\n'.join(rows)+'\r\nConnection: close\r\n\r\n').encode('latin1')
   upstream.sendall(head+body)
   if direct:
    drop=(method=='makeReply' and self.mode=='reply') or (method=='accept' and self.mode=='ambiguous')
    size=0
    while True:
     chunk=upstream.recv(65536)
     if not chunk:break
     size+=len(chunk)
     if not drop:c.sendall(chunk)
    if drop:self.events.append({'fault':self.mode,'request_delivered':True,'reply_bytes_withheld':size})
    return
   c.settimeout(None);upstream.settimeout(None)
   if rpc:self.tunnels.append((c,upstream))
   if path=='/peer/capability-session':self.sessions.append((c,upstream))
   while self.running:
    ready,_,_=select.select([c,upstream],[],[],1)
    for source in ready:
     chunk=source.recv(65536)
     if not chunk:return
     (upstream if source is c else c).sendall(chunk)
  except (OSError,ValueError):pass
  finally:
   for sock in (c,upstream):
    if sock:
     try:sock.shutdown(socket.SHUT_RDWR);sock.close()
     except OSError:pass
