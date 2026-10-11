import {DurableObject} from 'cloudflare:workers';
export class Contract extends DurableObject {
 async foo(){return 'foo from remote';}
 async thisCheck(){return this instanceof Contract;}
 async fetch(){return new Response('OK');}
 async put(k,v){await this.ctx.storage.put(k,v);return await this.ctx.storage.get(k);}
 async list(){return [...await this.ctx.storage.list({prefix:'a'})];}
 async rollback(){try{await this.ctx.storage.transaction(async tx=>{await tx.put('aborted',1);throw new Error('rollback');});}catch(e){if(e.message!=='rollback')throw e;}return (await this.ctx.storage.get('aborted'))??null;}
 async sql(){this.ctx.storage.sql.exec('CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY, v TEXT)');this.ctx.storage.sql.exec('INSERT INTO t VALUES (1, ?)', 'hello');return [...this.ctx.storage.sql.exec('SELECT id,v FROM t')];}
}
export default {async fetch(r,env){const mode=new URL(r.url).pathname.slice(1),id=env.NS.idFromName(mode),s=env.NS.get(id);let value;
 if(mode==='stub'){const unique1=env.NS.newUniqueId(),unique2=env.NS.newUniqueId();value={name:id.name,roundTrip:env.NS.idFromString(id.toString()).equals(id),distinct:!unique1.equals(unique2),rpc:await s.foo(),receiver:await s.thisCheck(),fetch:await (await s.fetch('http://test/')).text()};}
 else if(mode==='kv'){await s.put('aa',1);await s.put('ab',{n:2});await s.put('z',3);value=await s.list();}
 else if(mode==='rollback')value=await s.rollback();else if(mode==='sql')value=await s.sql();else return new Response('unknown',{status:404});return Response.json(value);}};
