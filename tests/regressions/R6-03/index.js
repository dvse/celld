import {DurableObject,WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
const text=new TextEncoder();
const bytes=()=>new ReadableStream({start(c){c.enqueue(text.encode('stream'));c.close();}});
const read=async s=>new Response(s).text();
class Value extends RpcTarget {ping(){return 42;}}
export class Factory extends WorkerEntrypoint {
 readable(label){const report=this.env.SOURCE.getByName('source');return new ReadableStream({cancel(){return report.record(label,'cancel');}},{highWaterMark:0});}
 writable(label){const report=this.env.SOURCE.getByName('source');return new WritableStream({write(chunk){return report.record(label,new TextDecoder().decode(chunk));},close(){return report.record(label,'close');},abort(){return report.record(label,'abort');}});}
}
export class Source extends DurableObject {
 init(){return true;}
 result(kind){if(kind==='mixed')return {stream:bytes(),stub:new Value()};if(kind==='response')return new Response(bytes());return bytes();}
 async consume(value){return value instanceof Request||value instanceof Response?value.text():read(value);}
 readable(label){return this.ctx.exports.Factory.readable(label);}
 writable(label){return this.ctx.exports.Factory.writable(label);}
 async record(label,value){const row=await this.ctx.storage.get(label)||[];row.push(value);await this.ctx.storage.put(label,row);}
 async ledger(){return Object.fromEntries(await this.ctx.storage.list());}
}
export class Holder extends DurableObject {
 init(){return true;}
 async matrix(){const s=this.env.SOURCE.getByName('source'),out={};
  out.readable=await read(await s.result('stream'));
  const mixed=await s.result('mixed');out.mixed=[await read(mixed.stream),await mixed.stub.ping()];mixed.stub[Symbol.dispose]();
  out.response=await (await s.result('response')).text();
  out.argument=await s.consume(bytes());out.request=await s.consume(new Request('http://test/',{method:'POST',body:bytes()}));out.responseArgument=await s.consume(new Response(bytes()));
  const writable=await s.writable('write'),writer=writable.getWriter();await writer.write(text.encode('written'));await writer.close();
  await (await s.writable('abort')).abort('stop');await (await s.readable('cancel')).cancel('stop');
  return out;
 }
 forward(label){return this.env.SOURCE.getByName('source').readable(label);}
 async hold(){this.stream=await this.env.SOURCE.getByName('source').readable('holder');return true;}
}
export class Receiver extends DurableObject {
 init(){return true;}
 async forwardBytes(){return read(await this.env.HOLDER.getByName('holder').forwardBytes());}
 async take(){this.stream=await this.env.HOLDER.getByName('holder').forward('forward');return true;}
}
Holder.prototype.forwardBytes=function(){return this.env.SOURCE.getByName('source').result('stream');};
export default {async fetch(request,env){const u=new URL(request.url);
 if(u.pathname==='/'){try{return Response.json(await env.HOLDER.getByName('holder').matrix());}catch(e){return Response.json({error:e.message});}}
 const [kind,method]=u.pathname.slice(1).split('/');
 try{return Response.json({ok:await env[kind.toUpperCase()].getByName(kind)[method](...JSON.parse(u.searchParams.get('args')||'[]'))});}
 catch(e){return Response.json({error:e.message},{status:500});}
}};
