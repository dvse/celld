"""Loopback S3-compatible fault store. Append-only SQLite versions retain evidence.

Implements the S3 subset exercised by celld: conditional PUT, HEAD, GET/range,
DELETE/tombstones, and ListObjectsV2. No credentials or Authorization are logged.
This is a test double for a linearizable object store, not MinIO qualification.
"""
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit,parse_qs,unquote
import datetime,email.utils,hashlib,json,sqlite3,threading,time,uuid,xml.etree.ElementTree as ET
class Store:
    def __init__(self,path):
        self.path=Path(path);self.path.mkdir(parents=True);self.db=sqlite3.connect(self.path/'versions.sqlite',check_same_thread=False)
        self.db.execute('CREATE TABLE versions (seq INTEGER PRIMARY KEY, key TEXT, etag TEXT, body BLOB, stamp REAL, deleted INTEGER)');self.db.commit()
        self.lock=threading.RLock();self.faults={};self.counts={};self.servers=[]
    def latest(self,key):return self.db.execute('SELECT etag,body,stamp,deleted FROM versions WHERE key=? ORDER BY seq DESC LIMIT 1',(key,)).fetchone()
    def append(self,key,body,deleted=0):
        etag=hashlib.sha256(body+uuid.uuid4().bytes).hexdigest();now=time.time()
        self.db.execute('INSERT INTO versions(key,etag,body,stamp,deleted) VALUES(?,?,?,?,?)',(key,etag,body,now,deleted));self.db.commit();return etag
    def listen(self,port):
        from common import port_available
        port_available(port);store=self
        class Handler(BaseHTTPRequestHandler):
            protocol_version='HTTP/1.1'
            def log_message(self,*args):pass
            def respond(self,code,body=b'',headers=None):
                self.send_response(code)
                for k,v in (headers or {}).items():self.send_header(k,str(v))
                self.send_header('Content-Length',str(len(body)));self.send_header('Connection','close');self.end_headers()
                if self.command!='HEAD':
                    try:self.wfile.write(body)
                    except (BrokenPipeError,ConnectionResetError):pass
            def error(self,code,name):self.respond(code,f'<Error><Code>{name}</Code><Message>{name}</Message></Error>'.encode(),{'Content-Type':'application/xml'})
            def handle_request(self):
                u=urlsplit(self.path);parts=unquote(u.path).lstrip('/').split('/',1);key=parts[1] if len(parts)>1 else '';q=parse_qs(u.query,keep_blank_values=True)
                fault=store.faults.get(port,'normal');code=0;start=time.monotonic()
                n=int(self.headers.get('Content-Length','0'));body=self.rfile.read(n) if n else b''
                with store.lock:store.counts[port]=store.counts.get(port,0)+1
                try:
                    if fault=='cut':self.error(503,'ServiceUnavailable');return
                    if fault=='throttle':self.error(429,'SlowDown');return
                    with store.lock:
                        row=store.latest(key);exists=row and not row[3]
                        if self.command=='POST' and 'delete' in q:
                            request=ET.fromstring(body);response=ET.Element('DeleteResult',xmlns='http://s3.amazonaws.com/doc/2006-03-01/')
                            keys=[x.text for x in request.iter() if x.tag.split('}')[-1]=='Key'];assert len(keys)<=1000
                            for selected in keys:
                                store.append(selected,b'',1);item=ET.SubElement(response,'Deleted');ET.SubElement(item,'Key').text=selected
                            self.respond(200,ET.tostring(response),{'Content-Type':'application/xml'});return
                        if self.command=='PUT':
                            if not key:self.respond(200);return
                            im=self.headers.get('If-Match');none=self.headers.get('If-None-Match')
                            if (im and (not exists or im.strip('"')!=row[0])) or (none=='*' and exists):self.error(412,'PreconditionFailed');return
                            etag=store.append(key,body);self.respond(200,headers={'ETag':'"'+etag+'"'});return
                        if self.command=='DELETE':
                            store.append(key,b'',1);self.respond(204);return
                        if self.command=='GET' and ('list-type' in q or not key):
                            prefix=q.get('prefix',[''])[0];startafter=q.get('continuation-token',q.get('start-after',['']))[0];limit=int(q.get('max-keys',['1000'])[0]);delimiter=q.get('delimiter',[''])[0]
                            entries=store.db.execute('SELECT key,etag,length(body),stamp FROM versions WHERE seq IN (SELECT MAX(seq) FROM versions GROUP BY key) AND deleted=0 ORDER BY key').fetchall()
                            grouped={}
                            for row in entries:
                                k=row[0]
                                if not k.startswith(prefix):continue
                                tail=k[len(prefix):]
                                if delimiter and delimiter in tail:
                                    common=prefix+tail.split(delimiter,1)[0]+delimiter;grouped[common]=None
                                else:grouped[k]=row
                            keys=[k for k in sorted(grouped) if k>startafter];page=keys[:limit];truncated=len(keys)>limit
                            root=ET.Element('ListBucketResult',xmlns='http://s3.amazonaws.com/doc/2006-03-01/');ET.SubElement(root,'Name').text=parts[0];ET.SubElement(root,'Prefix').text=prefix;ET.SubElement(root,'IsTruncated').text=str(truncated).lower();ET.SubElement(root,'KeyCount').text=str(len(page))
                            if delimiter:ET.SubElement(root,'Delimiter').text=delimiter
                            if truncated:ET.SubElement(root,'NextContinuationToken').text=page[-1]
                            for k in page:
                                row=grouped[k]
                                if row is None:
                                    c=ET.SubElement(root,'CommonPrefixes');ET.SubElement(c,'Prefix').text=k;continue
                                k,e,size,stamp=row;c=ET.SubElement(root,'Contents');ET.SubElement(c,'Key').text=k;ET.SubElement(c,'ETag').text='"'+e+'"';ET.SubElement(c,'Size').text=str(size);ET.SubElement(c,'LastModified').text=datetime.datetime.fromtimestamp(stamp,datetime.timezone.utc).isoformat().replace('+00:00','Z');ET.SubElement(c,'StorageClass').text='STANDARD'
                            self.respond(200,ET.tostring(root),{'Content-Type':'application/xml'});return
                        if self.command=='HEAD' and not key:self.respond(200);return
                        if not exists:self.error(404,'NoSuchKey');return
                        im=self.headers.get('If-Match')
                        if im and im.strip('"')!=row[0]:self.error(412,'PreconditionFailed');return
                        data=row[1];headers={'ETag':'"'+row[0]+'"','Last-Modified':email.utils.formatdate(row[2],usegmt=True),'Content-Type':'application/octet-stream','Accept-Ranges':'bytes'};code=200
                        rng=self.headers.get('Range')
                        if rng:
                            lo,hi=rng.removeprefix('bytes=').split('-');lo=int(lo or 0);hi=int(hi) if hi else len(data)-1
                            if lo>=len(data):self.error(416,'InvalidRange');return
                            hi=min(hi,len(data)-1);headers['Content-Range']=f'bytes {lo}-{hi}/{len(data)}';data=data[lo:hi+1];code=206
                        self.respond(code,data,headers)
                finally:
                    with store.lock:
                        with (store.path/'requests.jsonl').open('a') as f:f.write(json.dumps({'time':time.time(),'port':port,'method':self.command,'key':key,'query':q,'fault':fault,'duration_ms':round((time.monotonic()-start)*1000)})+'\n')
            do_GET=do_HEAD=do_PUT=do_POST=do_DELETE=handle_request
        server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True;thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();self.servers.append((server,thread))
    def stop(self):
        for s,t in self.servers:s.shutdown();s.server_close();t.join(2)
        self.db.close()
