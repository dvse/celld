"""Bounded private HTTP/WebSocket source; no external connections."""
import base64,hashlib,http.server,socket,struct,threading
class Peer:
 body=b'phase2\nprivate origin\n'
 url='http://127.0.0.1:9870'
 def __enter__(self):
  peer=self
  class Handler(http.server.BaseHTTPRequestHandler):
   def log_message(self,*args):pass
   def do_GET(self):
    if self.path!='/echo':
     self.send_response(200);self.send_header('Content-Length',str(len(peer.body)));self.end_headers();self.wfile.write(peer.body);return
    key=self.headers['Sec-WebSocket-Key'];value=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
    self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',value);self.end_headers();self.connection.settimeout(10)
    try:
     for _ in range(8):
      head=self.rfile.read(2)
      if len(head)!=2:break
      op=head[0]&15;size=head[1]&127
      if size>=126:break
      mask=self.rfile.read(4) if head[1]&128 else b'';data=self.rfile.read(size)
      if mask:data=bytes(x^mask[i%4] for i,x in enumerate(data))
      self.wfile.write(bytes([128|op,len(data)])+data);self.wfile.flush()
      if op==8:break
    except (OSError,TimeoutError):pass
  self.server=http.server.ThreadingHTTPServer(('127.0.0.1',9870),Handler);self.server.daemon_threads=True;self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();return self
 def __exit__(self,*args):self.server.shutdown();self.server.server_close();self.thread.join(2)
