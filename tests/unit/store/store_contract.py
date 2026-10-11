#!/usr/bin/env python3
"""Store contract checks: a fake store must not manufacture recovery failures."""
import concurrent.futures,http.client,json,os,socket,sys,threading,urllib.request,urllib.error,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'lib'))
from s3_store import Store
p=Path(os.environ['CELLD_TEST_ARTIFACTS']);store=Store(p/'contract-store');store.listen(9838)
def req(method,path,data=None,headers=None):
 r=urllib.request.Request('http://127.0.0.1:9838/test/'+path,data=data,method=method,headers=headers or {})
 try:x=urllib.request.urlopen(r,timeout=3)
 except urllib.error.HTTPError as e:x=e
 with x:return x.status,x.read(),dict(x.headers)
try:
 with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:codes=list(ex.map(lambda i:req('PUT','owner',str(i).encode(),{'If-None-Match':'*'})[0],range(20)))
 assert codes.count(200)==1 and codes.count(412)==19,codes
 _,_,h=req('HEAD','owner');assert req('PUT','owner',b'new',{'If-Match':h['ETag']})[0]==200
 assert req('PUT','owner',b'stale',{'If-Match':h['ETag']})[0]==412
 for k in ['ltx/e1/0000/a','ltx/e1/0000/b','ltx/e2/0000/c']:assert req('PUT',k,b'abcdefgh')[0]==200
 _,body,_=req('GET','?list-type=2&prefix=ltx/&delimiter=/');xml=ET.fromstring(body);ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
 assert [x.text for x in xml.findall('s:CommonPrefixes/s:Prefix',ns)]==['ltx/e1/','ltx/e2/'],body
 _,body,_=req('GET','?list-type=2&prefix=ltx/&max-keys=1');xml=ET.fromstring(body);assert xml.find('s:IsTruncated',ns).text=='true'
 token=xml.find('s:NextContinuationToken',ns).text;_,body,_=req('GET','?list-type=2&prefix=ltx/&max-keys=1&continuation-token='+token);assert b'ltx/e1/0000/b' in body
 code,body,_=req('GET','ltx/e1/0000/a',headers={'Range':'bytes=2-4'});assert (code,body)==(206,b'cde')
 assert req('DELETE','owner')[0]==204;assert req('GET','owner')[0]==404
 assert store.db.execute('SELECT count(*) FROM versions WHERE key="owner"').fetchone()[0]==3
 payload=b'<Delete><Object><Key>ltx/e1/0000/a</Key></Object><Object><Key>missing</Key></Object></Delete>'
 code,body,_=req('POST','?delete',payload);assert code==200 and b'<Deleted>' in body
 assert req('GET','ltx/e1/0000/a')[0]==404
 assert store.db.execute('SELECT count(*) FROM versions WHERE key="ltx/e1/0000/a"').fetchone()[0]==2
 # Keep one accepted request blocked on its body until shutdown has closed
 # the database. It must get a 503 without using that closed connection.
 entered=threading.Event();handler=store.servers[0][0].RequestHandlerClass;original=handler.do_PUT
 def delayed(self):entered.set();return original(self)
 handler.do_PUT=delayed
 with socket.create_connection(('127.0.0.1',9838),timeout=3) as sock:
  sock.sendall(b'PUT /test/late HTTP/1.1\r\nHost: local\r\nContent-Length: 1\r\n\r\n')
  assert entered.wait(2),'late handler was not accepted'
  store.stop();sock.sendall(b'x');reply=http.client.HTTPResponse(sock);reply.begin()
  assert reply.status==503,reply.status;reply.read()
 print('PASS: multi-object delete, conditional race, stale CAS, delimiter epoch discovery, pagination, range, append-only deletion, shutdown with an accepted incomplete body')
finally:store.stop()
