import {DurableObject} from 'cloudflare:workers';
export class Ledger extends DurableObject {
 async fetch(r){
  const url=new URL(r.url);
  if(url.pathname.endsWith('/stream-status'))return Response.json({bytes:(await this.ctx.storage.get('unacknowledged-stream-bytes'))??0});
  if(url.pathname.endsWith('/stream')){
   const reader=r.body.getReader();let bytes=0;
   for(;;){const x=await reader.read();if(x.done)break;bytes+=x.value.length;await this.ctx.storage.put('unacknowledged-stream-bytes',bytes);}
   return Response.json({bytes});
  }
  if(r.method==='POST'){
   const entry=await r.json();const key='entry/'+entry.id;
   const previous=await this.ctx.storage.get(key);
   if(previous!==undefined && previous!==entry.value)throw new Error('conflicting duplicate');
   await this.ctx.storage.put(key,entry.value);return Response.json({id:entry.id,value:entry.value});
  }
  const values=[...await this.ctx.storage.list({prefix:'entry/'})];return Response.json(values);
 }
}
export default {fetch(r,env){const cell=new URL(r.url).pathname.split('/')[1]||'default';return env.LEDGER.getByName(cell).fetch(r);}};
