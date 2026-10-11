import {DurableObject,restore} from 'cloudflare:workers';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export class Body extends DurableObject {
 init(){return true;}
 ping(){return 42;}
 open(mode){if(!this.stream)return false;if(mode==='error')this.stream.error(new Error('source body failure'));else{this.stream.enqueue(new TextEncoder().encode('suffix'));this.stream.close();}this.stream=null;return true;}
 fetch(){const owner=this;let controller;return new Response(new ReadableStream({start(c){controller=c;owner.stream=c;c.enqueue(new TextEncoder().encode('prefix'));},cancel(){if(owner.stream===controller)owner.stream=null;}}));}
}
export class Source extends DurableObject {
 init(){return true;}
 [restore](){return this.env.BODY.getByName('body');}
 create(){return this.ctx.restore({});}
}
export class Caller extends DurableObject {
 init(){this.seen='';return true;}
 prefix(){return this.seen??'';}
 async consume(mode){this.seen='';const cap=await this.env.SOURCE.getByName('source').create();try{const res=await cap.fetch('http://test/'),reader=res.body.getReader();let value='';for(;;){const item=await reader.read();if(item.done)return value;value+=new TextDecoder().decode(item.value);this.seen=value;}}catch(e){return 'rejected';}finally{cap[Symbol.dispose]();}}
 async fresh(){const cap=await this.env.SOURCE.getByName('source').create();try{return await cap.ping();}finally{cap[Symbol.dispose]();}}
}
export default {async fetch(r,e){const u=new URL(r.url),[kind,method]=u.pathname.slice(1).split('/');if(kind){try{return Response.json({ok:await e[kind.toUpperCase()].getByName(kind)[method](...JSON.parse(u.searchParams.get('args')||'[]'))});}catch(error){return Response.json({error:error.message},{status:500});}}
 const out={},caller=e.CALLER.getByName('caller');for(const mode of ['normal','error']){const call=caller.consume(mode);while(await caller.prefix()!=='prefix')await sleep(1);await e.BODY.getByName('body').open(mode);out[mode]=await call;}return Response.json(out);
}};
