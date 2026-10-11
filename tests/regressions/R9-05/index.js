import {DurableObject} from 'cloudflare:workers';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export class Receiver extends DurableObject {
 init(){return true;}
 cleanup(){this.ctx.abort(new Error("test cleanup"));}
 async observe(value){const signal=value instanceof Request?value.signal:value;let notifications=0;signal.addEventListener('abort',()=>notifications++);if(!signal.aborted)await Promise.race([new Promise(r=>signal.addEventListener('abort',r,{once:true})),sleep(400)]);return {aborted:signal.aborted,reason:signal.reason??null,notifications};}
 relay(signal){return this.env.THIRD.getByName('third').observe(signal);}
 relayKeep(signal){return this.env.THIRD.getByName('third').keep(signal);}
 async never(signal){await sleep(5);return signal.aborted;}
 keep(signal){this.signal=signal;return !signal.aborted;}
 async check(){await sleep(100);return {aborted:this.signal.aborted,reason:this.signal.reason instanceof DOMException?{name:this.signal.reason.name,message:this.signal.reason.message}:this.signal.reason??null};}
 clear(){this.signal=null;return true;}
}
export class Third extends Receiver {}
export class Sender extends DurableObject {
 init(){return true;}
 cleanup(){this.ctx.abort(new Error("test cleanup"));}
 async armDeath(kind){this.death=new AbortController();return kind==='relay'?this.env.RECEIVER.getByName('receiver').relayKeep(this.death.signal):this.env.THIRD.getByName('third').keep(this.death.signal);}
 abortDeath(){this.death.abort('source abort after disconnect');return true;}
 async test(){const out={},receiver=this.env.RECEIVER.getByName('receiver');
  for(const kind of ['direct','forwarded','request','already']){
   const controller=new AbortController(),reason={kind,value:42};
   if(kind==='already')controller.abort(reason);
   const input=kind==='request'?new Request('http://test/',{signal:controller.signal}):controller.signal;
   const result=kind==='forwarded'?receiver.relay(input):receiver.observe(input);
   if(kind!=='already'){await sleep(40);controller.abort(reason);controller.abort('ignored');}
   out[kind]=await result;
  }
  const never=new AbortController();out.never=await receiver.never(never.signal);
  this.controller=new AbortController();out.kept=await receiver.keep(this.controller.signal);this.controller.abort('later');out.retained=await receiver.check();await receiver.clear();this.controller=null;
  return out;
 }
}
export default {async fetch(r,e){if(new URL(r.url).pathname==="/gate"){try{await e.RECEIVER.getByName('receiver').never(new AbortController().signal);return Response.json({gated:false});}catch(error){return Response.json({gated:error.name==='DataCloneError'});}}const u=new URL(r.url),[kind,method]=u.pathname.slice(1).split('/');if(kind)return Response.json(await e[kind.toUpperCase()].getByName(kind)[method](...JSON.parse(u.searchParams.get('args')||'[]')));try{return Response.json(await e.SENDER.getByName('sender').test());}catch(error){return Response.json({error:error.message});}}};
