// Synthetic OS-relevant application compositions. The original OS checkout was
// unavailable. Every query executes against the real Durable Object SQL API.
const bytes = value => new Uint8Array(value);
async function chunkMeta(c,size) {
  const rows=c.q('SELECT count(*) AS chunks,coalesce(sum(length(data)),0) AS stored FROM chunks')[0];
  await c.put('file',{size,chunks:rows.chunks,stored:rows.stored});
}
function readChunks(c,size) {
  const out=new Uint8Array(size);
  for(const row of c.q('SELECT off,data FROM chunks ORDER BY off'))out.set(new Uint8Array(row.data),row.off);
  return [...out];
}
async function overwrite(c,offset,input,size) {
  for(let i=0;i<input.length;) {
    const at=offset+i,base=Math.floor(at/4)*4,within=at-base;
    const prior=c.q('SELECT data FROM chunks WHERE off=?',base)[0];
    const take=Math.min(4-within,input.length-i),old=prior?new Uint8Array(prior.data):new Uint8Array();
    const next=new Uint8Array(Math.max(old.length,within+take));next.set(old);next.set(input.slice(i,i+take),within);
    c.q('INSERT INTO chunks VALUES(?,?) ON CONFLICT(off) DO UPDATE SET data=excluded.data',base,next);i+=take;
  }
  await chunkMeta(c,size);
}
export const CASES = {
  T201: {
    async seed(c) {
      c.q('CREATE TABLE quota(id INTEGER PRIMARY KEY,used INTEGER,cap INTEGER)');
      c.q('INSERT INTO quota VALUES(1,0,10)');
      c.q('CREATE TABLE allocation(id TEXT PRIMARY KEY,bytes INTEGER)');await c.put('count',0);
    },
    async left(c) {
      c.eq(c.q('UPDATE quota SET used=used+7 WHERE id=1 AND used+7<=cap RETURNING used'),[{used:7}],'first bounded reservation returns one accepted row');
      await c.pause();
      c.q("INSERT INTO allocation VALUES('a',7)");await c.put({'doc/a':{size:7},'index/a':true,count:1});return 'accepted';
    },
    async right(c) {
      const grant=c.q('UPDATE quota SET used=used+5 WHERE id=1 AND used+5<=cap RETURNING used');
      c.eq(grant,[],'queued five-byte reservation is a normal zero-row result');
      if(grant.length) {c.q("INSERT INTO allocation VALUES('b',5)");await c.put({'doc/b':{size:5},'index/b':true,count:2});}
      return 'capacity-exhausted';
    },
    async verify(c) {
      c.eq(c.q('SELECT used,cap FROM quota'),[{used:7,cap:10}],'quota never overcommits');
      c.eq(c.q('SELECT id,bytes FROM allocation ORDER BY id'),[{id:'a',bytes:7}],'accepted receipt equals complete allocation set');
      c.eq([...(await c.list())],[['count',1],['doc/a',{size:7}],['index/a',true]],'document index and count have no rejected-allocation residue');
    },
  },
  T202: {
    async seed(c) {c.q('CREATE TABLE blobs(key TEXT PRIMARY KEY,data BLOB,refs INTEGER)');c.q('CREATE TABLE links(id TEXT PRIMARY KEY,blob TEXT)');await c.put({documents:0,logical:0,physical:0});},
    async left(c) {
      c.eq(c.q("INSERT INTO blobs VALUES('content-123',?,1) ON CONFLICT(key) DO UPDATE SET refs=refs+1 RETURNING refs,length(data) AS n",bytes([1,2,3])),[{refs:1,n:3}],'new content row starts one reference');
      await c.pause();c.q("INSERT INTO links VALUES('a','content-123')");await c.put({'doc/a':{blob:'content-123',size:3},documents:1,logical:3,physical:3});
    },
    async right(c) {
      const row=c.q("INSERT INTO blobs VALUES('content-123',?,1) ON CONFLICT(key) DO UPDATE SET refs=refs+1 RETURNING refs,length(data) AS n",bytes([1,2,3]))[0];
      c.eq(row,{refs:2,n:3},'conflict-update branch increments existing refs without replacing data');
      c.q("INSERT INTO links VALUES('b','content-123')");await c.put({'doc/b':{blob:'content-123',size:3},documents:2,logical:6,physical:3});
    },
    async verify(c) {
      c.eq(c.q('SELECT key,refs,data FROM blobs'),[{key:'content-123',refs:2,data:[1,2,3]}],'one physical payload with two actual references');
      c.eq(c.q('SELECT id,blob FROM links ORDER BY id'),[{id:'a',blob:'content-123'},{id:'b',blob:'content-123'}],'both documents link to the same content row');
      c.eq([...(await c.list())],[['doc/a',{blob:'content-123',size:3}],['doc/b',{blob:'content-123',size:3}],['documents',2],['logical',6],['physical',3]],'logical bytes and physical bytes are separately exact');
    },
  },
  T203: {
    async seed(c) {
      c.q('CREATE TABLE folders(id TEXT PRIMARY KEY,n INTEGER,bytes INTEGER)');c.q("INSERT INTO folders VALUES('x',0,0),('y',0,0)");
      c.q('CREATE TABLE docs(id TEXT PRIMARY KEY,folder TEXT,bytes INTEGER)');
      c.q('CREATE TRIGGER docs_add AFTER INSERT ON docs BEGIN UPDATE folders SET n=n+1,bytes=bytes+new.bytes WHERE id=new.folder; END');
      c.q('CREATE TRIGGER docs_remove AFTER DELETE ON docs BEGIN UPDATE folders SET n=n-1,bytes=bytes-old.bytes WHERE id=old.folder; END');
      c.q('CREATE TRIGGER docs_move AFTER UPDATE ON docs BEGIN UPDATE folders SET n=n-1,bytes=bytes-old.bytes WHERE id=old.folder; UPDATE folders SET n=n+1,bytes=bytes+new.bytes WHERE id=new.folder; END');
      c.q("INSERT INTO docs VALUES('a','x',3),('b','x',4)");await c.put({'x/a':3,'x/b':4});
    },
    async left(c) {c.q("UPDATE docs SET folder='y',bytes=5 WHERE id='a'");await c.pause();await c.del('x/a');await c.put('y/a',5);},
    async right(c) {c.eq(c.q('SELECT id,n,bytes FROM folders ORDER BY id'),[{id:'x',n:1,bytes:4},{id:'y',n:1,bytes:5}],'queued delete sees both update-trigger sides');c.q("DELETE FROM docs WHERE id='b'");await c.del('x/b');},
    async verify(c) {
      c.eq(c.q('SELECT id,n,bytes FROM folders ORDER BY id'),[{id:'x',n:0,bytes:0},{id:'y',n:1,bytes:5}],'insert update and delete trigger deltas reconcile');
      c.eq(c.q('SELECT id,folder,bytes FROM docs'),[{id:'a',folder:'y',bytes:5}],'moved document survives peer deletion');
      c.eq([...(await c.list())],[['y/a',5]],'explicit KV secondary index matches triggered SQL accounting');
    },
  },
  T204: {
    async seed(c) {
      c.q('PRAGMA foreign_keys=ON');c.eq(c.q('PRAGMA foreign_keys'),[{foreign_keys:1}],'foreign key enforcement explicitly enabled');
      c.q('CREATE TABLE docs(id TEXT PRIMARY KEY,bytes INTEGER)');
      c.q('CREATE TABLE chunks(doc TEXT,seq INTEGER,data BLOB,PRIMARY KEY(doc,seq),FOREIGN KEY(doc) REFERENCES docs(id) ON UPDATE CASCADE ON DELETE CASCADE)');
      c.q("INSERT INTO docs VALUES('a',3),('keep',2)");c.q("INSERT INTO chunks VALUES('a',0,?),('a',1,?),('keep',0,?)",bytes([1,2]),bytes([3]),bytes([8,9]));
      await c.put({'doc/a':3,'doc/keep':2,bytes:5,count:2});
    },
    async left(c) {c.q("UPDATE docs SET id='renamed' WHERE id='a'");await c.pause();await c.del('doc/a');await c.put('doc/renamed',3);},
    async right(c) {
      c.eq(c.q("SELECT doc,seq,data FROM chunks WHERE doc='renamed' ORDER BY seq"),[{doc:'renamed',seq:0,data:[1,2]},{doc:'renamed',seq:1,data:[3]}],'ON UPDATE rewrites composite child ownership');
      c.q("DELETE FROM docs WHERE id='renamed'");await c.del('doc/renamed');await c.put({bytes:2,count:1});
    },
    async verify(c) {c.eq(c.q('SELECT * FROM docs'),[{id:'keep',bytes:2}],'only unrelated parent survives');c.eq(c.q('SELECT doc,seq,data FROM chunks'),[{doc:'keep',seq:0,data:[8,9]}],'ON DELETE removes all renamed children only');c.eq(c.q('PRAGMA foreign_key_check'),[],'cascade leaves no dangling references');c.eq([...(await c.list())],[['bytes',2],['count',1],['doc/keep',2]],'cross-surface index and counters match cascade');},
  },
  T205: {
    async seed(c) {
      c.q('PRAGMA foreign_keys=ON');c.eq(c.q('PRAGMA foreign_keys'),[{foreign_keys:1}],'deferred constraint enforcement explicitly enabled');
      c.q('CREATE TABLE docs(id TEXT PRIMARY KEY,head INTEGER,FOREIGN KEY(id,head) REFERENCES versions(doc,rev) DEFERRABLE INITIALLY DEFERRED)');
      c.q('CREATE TABLE versions(doc TEXT,rev INTEGER,bytes INTEGER,PRIMARY KEY(doc,rev),FOREIGN KEY(doc) REFERENCES docs(id) DEFERRABLE INITIALLY DEFERRED)');
      await c.transaction(async t=>{const d=c.child(t);d.q("INSERT INTO docs VALUES('a',1)");d.q("INSERT INTO versions VALUES('a',1,2)");await d.put('head',{revision:1,bytes:2});});
    },
    async left(c) {
      c.q("UPDATE docs SET head=2 WHERE id='a'");await c.pause();
      await c.transaction(async inner=>{const d=c.child(inner);d.q("INSERT INTO versions VALUES('a',2,4)");await d.put('head',{revision:2,bytes:4});});
    },
    async right(c) {
      c.eq(c.q('SELECT docs.head,versions.bytes FROM docs JOIN versions ON versions.doc=docs.id AND versions.rev=docs.head'),[{head:2,bytes:4}],'left commit resolves deferred head before the peer enters');
      c.q("UPDATE docs SET head=3 WHERE id='a'");
      await c.transaction(async inner=>{const d=c.child(inner);d.q("INSERT INTO versions VALUES('a',3,2)");await d.put('head',{revision:3,bytes:2});});
    },
    async verify(c) {c.eq(c.q('PRAGMA foreign_key_check'),[],'both deferred cycles are valid at commit');c.eq(c.q('SELECT rev,bytes FROM versions ORDER BY rev'),[{rev:1,bytes:2},{rev:2,bytes:4},{rev:3,bytes:2}],'nested successful writes retain complete revision history');c.eq(c.q('SELECT head FROM docs'),[{head:3}],'current pointer advances through both commits');c.eq(await c.get('head'),{revision:3,bytes:2},'KV head agrees with cyclic relational pointer');},
  },
  T206: {
    async seed(c) {
      c.q('CREATE TABLE docs(id INTEGER PRIMARY KEY,slug TEXT,live INTEGER,bytes INTEGER)');c.q('CREATE UNIQUE INDEX live_slug ON docs(slug) WHERE live=1');
      c.q("INSERT INTO docs VALUES(1,'report',1,2),(99,'report',0,7)");await c.put({active:1,bytes:2,'slug/report':1});
    },
    async left(c) {c.q('UPDATE docs SET live=0 WHERE id=1');c.q("INSERT INTO docs VALUES(2,'report',1,4)");await c.pause();await c.put({active:1,bytes:4,'slug/report':2});},
    async right(c) {
      c.eq(c.q("INSERT INTO docs VALUES(3,'report',1,6) ON CONFLICT(slug) WHERE live=1 DO UPDATE SET bytes=excluded.bytes RETURNING id,bytes"),[{id:2,bytes:6}],'partial conflict target selects current row rather than archived same-slug rows');
      await c.put('bytes',6);
    },
    async verify(c) {c.eq(c.q('SELECT id,slug,live,bytes FROM docs ORDER BY id'),[{id:1,slug:'report',live:0,bytes:2},{id:2,slug:'report',live:1,bytes:6},{id:99,slug:'report',live:0,bytes:7}],'archived identities persist while current slug is unique');c.eq(c.q('SELECT count(*) AS n,sum(bytes) AS bytes FROM docs WHERE live=1'),[{n:1,bytes:6}],'active subset has exact count and byte sum');c.eq([...(await c.list())],[['active',1],['bytes',6],['slug/report',2]],'public KV current index retains actual conflict winner identity');},
  },
  T207: {
    async seed(c) {c.q('CREATE TABLE archive(id TEXT PRIMARY KEY,bytes INTEGER)');await c.put({'pending/a':1,'pending/b':2,'pending/c':3,'pending/d':4,'pending/e':5,'pending0/decoy':99,remaining:15});},
    async left(c) {
      const page=[...(await c.list({prefix:'pending/',limit:2}))];c.eq(page,[['pending/a',1],['pending/b',2]],'first bounded partition selected');
      for(const [key,n] of page)c.q('INSERT INTO archive VALUES(?,?)',key,n);
      await c.pause();c.eq(await c.del(page.map(x=>x[0])),2,'first selected batch removed');await c.put('remaining',12);
    },
    async right(c) {
      const page=[...(await c.list({prefix:'pending/',limit:2}))];c.eq(page,[['pending/c',3],['pending/d',4]],'queued partition does not repeat already extracted rows');
      for(const [key,n] of page)c.q('INSERT INTO archive VALUES(?,?)',key,n);
      c.eq(await c.del(page.map(x=>x[0])),2,'second selected batch removed');await c.put('remaining',5);
    },
    async verify(c) {c.eq(c.q('SELECT id,bytes FROM archive ORDER BY id'),[{id:'pending/a',bytes:1},{id:'pending/b',bytes:2},{id:'pending/c',bytes:3},{id:'pending/d',bytes:4}],'two selected partitions form exact disjoint archive');c.eq(c.q('SELECT count(*) AS n,sum(bytes) AS bytes FROM archive'),[{n:4,bytes:10}],'archive count and byte accounting reconcile with remaining five');c.eq([...(await c.list())],[['pending/e',5],['pending0/decoy',99],['remaining',5]],'range decoy and unselected tail remain untouched');},
  },
  T208: {
    async seed(c) {
      c.q('CREATE TABLE dirs(id INTEGER PRIMARY KEY,parent INTEGER)');c.q('INSERT INTO dirs VALUES(0,NULL),(1,0),(2,1),(3,0)');c.q('CREATE TABLE docs(id TEXT PRIMARY KEY,dir INTEGER,bytes INTEGER)');c.q("INSERT INTO docs VALUES('a',2,3),('b',1,5),('c',3,7)");
      c.q('CREATE TABLE ancestry(doc TEXT,ancestor INTEGER,PRIMARY KEY(doc,ancestor))');
      c.q('WITH RECURSIVE climb(doc,ancestor,depth) AS (SELECT id,dir,0 FROM docs UNION ALL SELECT climb.doc,dirs.parent,depth+1 FROM climb JOIN dirs ON dirs.id=climb.ancestor WHERE dirs.parent IS NOT NULL AND depth<8) INSERT INTO ancestry SELECT doc,ancestor FROM climb');await c.put('total',15);
    },
    async left(c) {
      c.q('UPDATE dirs SET parent=3 WHERE id=1');c.q('DELETE FROM ancestry');
      c.q('WITH RECURSIVE climb(doc,ancestor,depth) AS (SELECT id,dir,0 FROM docs UNION ALL SELECT climb.doc,dirs.parent,depth+1 FROM climb JOIN dirs ON dirs.id=climb.ancestor WHERE dirs.parent IS NOT NULL AND depth<8) INSERT INTO ancestry SELECT doc,ancestor FROM climb');await c.pause();await c.put('parent/1',3);
    },
    async right(c) {
      c.eq(c.q('SELECT sum(bytes) AS n FROM docs JOIN ancestry ON ancestry.doc=docs.id WHERE ancestor=3'),[{n:15}],'moved subtree contributes every descendant exactly once');
      c.q("INSERT INTO docs VALUES('d',2,2)");
      c.q("WITH RECURSIVE climb(ancestor,depth) AS (VALUES(2,0) UNION ALL SELECT dirs.parent,depth+1 FROM climb JOIN dirs ON dirs.id=climb.ancestor WHERE dirs.parent IS NOT NULL AND depth<8) INSERT INTO ancestry SELECT 'd',ancestor FROM climb");await c.put('total',17);
    },
    async verify(c) {c.eq(c.q('SELECT ancestor,count(*) AS n,sum(bytes) AS bytes FROM ancestry JOIN docs ON docs.id=ancestry.doc GROUP BY ancestor ORDER BY ancestor'),[{ancestor:0,n:4,bytes:17},{ancestor:1,n:3,bytes:10},{ancestor:2,n:2,bytes:5},{ancestor:3,n:4,bytes:17}],'bounded recursive index and subtree byte totals remain coherent');c.eq(c.q('SELECT id,parent FROM dirs ORDER BY id'),[{id:0,parent:null},{id:1,parent:3},{id:2,parent:1},{id:3,parent:0}],'ordinary move has the exact acyclic parent graph');c.eq([...(await c.list())],[['parent/1',3],['total',17]],'stored parent and total match rebuilt index');},
  },
  T209: {
    async seed(c) {c.q('CREATE TABLE versions(doc TEXT,rev INTEGER,bytes INTEGER,pinned INTEGER,PRIMARY KEY(doc,rev))');c.q("INSERT INTO versions VALUES('a',1,1,1),('a',2,2,0),('a',3,3,0),('b',1,7,0)");await c.put({bytes:13,'head/a':3,'head/b':1});},
    async left(c) {
      c.q("INSERT INTO versions VALUES('a',4,4,0)");
      const deleted=c.q('DELETE FROM versions WHERE (doc,rev) IN (SELECT doc,rev FROM (SELECT doc,rev,pinned,row_number() OVER(PARTITION BY doc ORDER BY rev DESC) AS rank FROM versions) WHERE rank>2 AND pinned=0) RETURNING doc,rev,bytes');
      c.eq(deleted,[{doc:'a',rev:2,bytes:2}],'window pruning removes only unpinned row outside latest two');await c.pause();await c.put({bytes:15,'head/a':4});
    },
    async right(c) {
      c.q("INSERT INTO versions VALUES('a',5,5,0)");
      c.eq(c.q('DELETE FROM versions WHERE (doc,rev) IN (SELECT doc,rev FROM (SELECT doc,rev,pinned,row_number() OVER(PARTITION BY doc ORDER BY rev DESC) AS rank FROM versions) WHERE rank>2 AND pinned=0) RETURNING doc,rev,bytes'),[{doc:'a',rev:3,bytes:3}],'next pruning preserves pin and other document partition');await c.put({bytes:17,'head/a':5});
    },
    async verify(c) {c.eq(c.q('SELECT doc,rev,bytes,pinned FROM versions ORDER BY doc,rev'),[{doc:'a',rev:1,bytes:1,pinned:1},{doc:'a',rev:4,bytes:4,pinned:0},{doc:'a',rev:5,bytes:5,pinned:0},{doc:'b',rev:1,bytes:7,pinned:0}],'retention set is pinned first plus latest two and untouched other document');c.eq(c.q('SELECT sum(bytes) AS bytes FROM versions'),[{bytes:17}],'retained payload sum excludes pruned revisions');c.eq([...(await c.list())],[['bytes',17],['head/a',5],['head/b',1]],'current pointers never point to pruned revisions');},
  },
  T210: {
    async seed(c) {c.q('CREATE TABLE chunks(off INTEGER PRIMARY KEY,data BLOB)');c.q('INSERT INTO chunks VALUES(0,?),(4,?)',bytes([0,1,2,3]),bytes([4,5,6,7]));await chunkMeta(c,8);},
    async left(c) {await overwrite(c,2,bytes([9,8,7]),8);await c.pause();},
    async right(c) {c.eq(readChunks(c,8),[0,1,9,8,7,5,6,7],'overlapping peer starts from whole first byte-range update');await overwrite(c,3,bytes([6,5]),8);},
    async verify(c) {c.eq(readChunks(c,8),[0,1,9,6,5,5,6,7],'later overlapping range wins only its own two byte positions');c.eq(c.q('SELECT off,length(data) AS n FROM chunks ORDER BY off'),[{off:0,n:4},{off:4,n:4}],'cross-chunk overwrite changes no allocation boundaries');c.eq(await c.get('file'),{size:8,chunks:2,stored:8},'overwrite does not inflate stored-byte or chunk accounting');},
  },
  T211: {
    async seed(c) {c.q('CREATE TABLE chunks(off INTEGER PRIMARY KEY,data BLOB)');c.q('INSERT INTO chunks VALUES(0,?)',bytes([1,2]));await chunkMeta(c,2);},
    async left(c) {c.q('INSERT INTO chunks VALUES(8,?)',bytes([9,10]));await chunkMeta(c,10);await c.pause();},
    async right(c) {c.eq(c.q('SELECT prior_end AS gap_start,off AS gap_end FROM (SELECT off,lag(off+length(data)) OVER (ORDER BY off) AS prior_end FROM chunks) WHERE prior_end<off ORDER BY off'),[{gap_start:2,gap_end:8}],'native predecessor-boundary query identifies exact unallocated interval');c.eq(await c.get('file'),{size:10,chunks:2,stored:4},'sparse logical length excludes unallocated gap from physical bytes');c.eq(readChunks(c,10),[1,2,0,0,0,0,0,0,9,10],'sparse read zero fills only missing byte interval');c.q('INSERT INTO chunks VALUES(2,?)',bytes([3,4,5,6,7,8]));await chunkMeta(c,10);},
    async verify(c) {c.eq(c.q('SELECT prior_end AS gap_start,off AS gap_end FROM (SELECT off,lag(off+length(data)) OVER (ORDER BY off) AS prior_end FROM chunks) WHERE prior_end<off ORDER BY off'),[],'native gap query becomes empty after contiguous interval fill');c.eq(readChunks(c,10),[1,2,3,4,5,6,7,8,9,10],'gap-fill preserves both already allocated extents');c.eq(c.q('SELECT off,length(data) AS n FROM chunks ORDER BY off'),[{off:0,n:2},{off:2,n:6},{off:8,n:2}],'sparse extent boundaries retained');c.eq(await c.get('file'),{size:10,chunks:3,stored:10},'gap-fill increases physical bytes without extending logical file');},
  },
  T212: {
    async seed(c) {c.q('CREATE TABLE chunks(off INTEGER PRIMARY KEY,data BLOB)');c.q('INSERT INTO chunks VALUES(0,?),(4,?),(8,?)',bytes([1,2,3,4]),bytes([5,6,7,8]),bytes([9,10]));await chunkMeta(c,10);},
    async left(c) {c.q('DELETE FROM chunks WHERE off>=6');c.q('UPDATE chunks SET data=substr(data,1,6-off) WHERE off<6 AND off+length(data)>6');await chunkMeta(c,6);await c.pause();},
    async right(c) {c.eq(readChunks(c,6),[1,2,3,4,5,6],'truncate prunes whole tail and clips crossing BLOB');c.eq(await c.get('file'),{size:6,chunks:2,stored:6},'truncate releases exact byte charge');await overwrite(c,6,bytes([11,12,13]),9);},
    async verify(c) {c.eq(readChunks(c,9),[1,2,3,4,5,6,11,12,13],'append fills clipped terminal chunk then allocates one new chunk');c.eq(c.q('SELECT off,length(data) AS n FROM chunks ORDER BY off'),[{off:0,n:4},{off:4,n:4},{off:8,n:1}],'former discarded tail bytes never reappear');c.eq(await c.get('file'),{size:9,chunks:3,stored:9},'truncate then append retains exact length and accounting');},
  },
  T213: {
    async seed(c) {c.q('CREATE TABLE chunks(seq INTEGER PRIMARY KEY,off INTEGER,data BLOB)');c.q('INSERT INTO chunks VALUES(0,0,?),(1,2,?)',bytes([1,2]),bytes([3,4]));c.q('CREATE TABLE quota(id INTEGER PRIMARY KEY,reserved INTEGER,live INTEGER)');c.q('INSERT INTO quota VALUES(1,6,0)');c.q('CREATE TABLE manifest(id TEXT PRIMARY KEY,n INTEGER,bytes INTEGER)');await c.put('file',{status:'uploading',expected:6});},
    async left(c) {c.q('INSERT INTO chunks VALUES(2,4,?)',bytes([5,6]));await c.pause();await c.put('staged',6);},
    async right(c) {
      const complete=c.q('SELECT count(*) AS n,sum(length(data)) AS bytes FROM chunks HAVING count(*)=3 AND min(seq)=0 AND max(seq)=2 AND min(off)=0 AND max(off+length(data))=6 AND sum(length(data))=6 AND sum(CASE WHEN off=seq*2 AND length(data)=2 THEN 0 ELSE 1 END)=0');
      c.eq(complete,[{n:3,bytes:6}],'manifest admission requires exact contiguous chunk set');
      c.q("INSERT INTO manifest VALUES('f',3,6)");c.q('UPDATE quota SET reserved=reserved-6,live=live+6 WHERE id=1');await c.put('file',{status:'complete',expected:6});await c.del('staged');
    },
    async verify(c) {c.eq(c.q('SELECT * FROM manifest'),[{id:'f',n:3,bytes:6}],'committed manifest matches finite chunk aggregate');c.eq(c.q('SELECT reserved,live FROM quota'),[{reserved:0,live:6}],'publication transfers a charge rather than double counting it');c.eq(c.q('SELECT seq,off,data FROM chunks ORDER BY seq'),[{seq:0,off:0,data:[1,2]},{seq:1,off:2,data:[3,4]},{seq:2,off:4,data:[5,6]}],'all published payload bytes remain');c.eq([...(await c.list())],[['file',{status:'complete',expected:6}]],'staging marker removed with committed file state');},
  },
  T214: {
    async seed(c) {
      c.q('CREATE TABLE docs(id TEXT PRIMARY KEY,body TEXT,n INTEGER GENERATED ALWAYS AS(length(CAST(body AS BLOB))) STORED,chars INTEGER GENERATED ALWAYS AS(length(body)) VIRTUAL)');c.q('CREATE INDEX by_bytes ON docs(n,id)');c.q("INSERT INTO docs(id,body) VALUES('a','A'),('b','zz')");await c.put('bytes',3);
    },
    async left(c) {c.eq(c.q("UPDATE docs SET body=? WHERE id='a' RETURNING n,chars",'é🦉'),[{n:6,chars:2}],'generated storage length counts UTF-8 bytes rather than codepoints');await c.pause();await c.put('bytes',8);},
    async right(c) {c.eq(c.q('SELECT id,n FROM docs INDEXED BY by_bytes WHERE n>=6 ORDER BY n,id'),[{id:'a',n:6}],'generated-column index reflects the completed rewrite');c.eq(c.q("UPDATE docs SET body=? WHERE id='b' RETURNING n,chars",'λ'),[{n:2,chars:1}],'same byte size can change character count');},
    async verify(c) {c.eq(c.q('SELECT id,body,n,chars FROM docs ORDER BY id'),[{id:'a',body:'é🦉',n:6,chars:2},{id:'b',body:'λ',n:2,chars:1}],'stored and virtual generated values agree with exact text');c.eq(c.q('SELECT sum(n) AS bytes FROM docs'),[{bytes:8}],'generated byte aggregate reconciles');c.eq(await c.get('bytes'),8,'application charge remains bytes not character length');},
  },
  T215: {
    async seed(c) {c.q('CREATE VIRTUAL TABLE search USING fts5(doc UNINDEXED,body)');c.q("INSERT INTO search(rowid,doc,body) VALUES(1,'a','red blue'),(2,'b','red orange')");await c.put({'doc/a':'red blue','doc/b':'red orange',bytes:18,count:2});},
    async left(c) {c.q("UPDATE search SET body='green blue' WHERE rowid=1");await c.pause();await c.put({'doc/a':'green blue',bytes:20});},
    async right(c) {c.eq(c.q("SELECT doc FROM search WHERE search MATCH 'red' ORDER BY doc"),[{doc:'b'}],'FTS token rewrite removes old document posting before peer search');c.q('DELETE FROM search WHERE rowid=2');await c.del('doc/b');await c.put({bytes:10,count:1});},
    async verify(c) {c.eq(c.q("SELECT doc FROM search WHERE search MATCH 'red' ORDER BY doc"),[],'deleted document leaves no old-token postings');c.eq(c.q("SELECT doc,body FROM search WHERE search MATCH 'green AND blue' ORDER BY doc"),[{doc:'a',body:'green blue'}],'updated document remains searchable by both new tokens');c.eq(c.q('SELECT count(*) AS n,sum(length(CAST(body AS BLOB))) AS bytes FROM search'),[{n:1,bytes:10}],'virtual table row count and payload bytes reconcile');c.eq([...(await c.list())],[['bytes',10],['count',1],['doc/a','green blue']],'KV documents and counters agree with FTS index');},
  },
};
