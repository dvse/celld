import {WorkerEntrypoint,DurableObject,RpcTarget,restore} from 'cloudflare:workers';
class Value extends RpcTarget {ping(){return 73;} fetch(){return 'ordinary RPC';}}
async function endpoint(request,ctx) {
 const url=new URL(request.url);
 if(url.pathname==='/self')return new Response(String(await (await ctx.restore({inner:true})).ping()),{status:202});
 if(request.headers.get('Upgrade')?.toLowerCase()==='websocket'){
  const pair=new WebSocketPair();pair[1].accept();
  pair[1].addEventListener('message',event=>pair[1].send('echo:'+event.data));
  return new Response(null,{status:101,webSocket:pair[0],headers:{'x-channel':'upgrade'}});
 }
 const reader=request.body?.getReader();
 const body=new ReadableStream({async pull(controller){
  if(!reader){controller.close();return;}
  const chunk=await reader.read();if(chunk.done)controller.close();else controller.enqueue(chunk.value);
 },async cancel(reason){await reader?.cancel(reason);}});
 return new Response(body,{status:201,headers:{'x-channel':'http'}});
}
export class Receiver extends WorkerEntrypoint {
 [restore](){return new Value();}
 fetch(request){return endpoint(request,this.ctx);}
}
export class Echo extends DurableObject {
 [restore](){return new Value();}
 fetch(request){return endpoint(request,this.ctx);}
}
export class Leaf extends Echo {}
const DYNAMIC=`import {WorkerEntrypoint,RpcTarget,restore} from 'cloudflare:workers';
class Value extends RpcTarget {ping(){return 73;}}
${endpoint.toString()}
export class Receiver extends WorkerEntrypoint {
 [restore](){return new Value();}
 fetch(request){return endpoint(request,this.ctx);}
}`;
export class Root extends DurableObject {
 [restore]({kind}){
  if(kind==='service')return this.ctx.exports.Receiver;
  if(kind==='do')return this.env.ECHO.getByName('echo');
  if(kind==='facet')return this.ctx.facets.get('leaf',()=>({class:this.ctx.exports.Leaf}));
  if(kind==='dynamic'){
   this.worker??=this.env.LOADER.get('http-restore',()=>({compatibilityDate:'2026-08-01',compatibilityFlags:['allow_irrevocable_stub_storage'],mainModule:'w.js',modules:{'w.js':DYNAMIC}}));
   return this.worker.getEntrypoint('Receiver');
  }
  return new Value();
 }
 create(kind){return this.ctx.restore({kind});}
 async direct(kind){return http(await this.create(kind));}
}
export class Store extends DurableObject {
 async roundtrip(channel){await this.ctx.storage.put('channel',channel);return await this.ctx.storage.get('channel');}
}
async function http(channel){
 let next=0;const text=new TextEncoder();
 const body=new ReadableStream({async pull(controller){
  if(next++===0)controller.enqueue(text.encode('pay'));
  else if(next===2){await new Promise(resolve=>setTimeout(resolve,2));controller.enqueue(text.encode('load'));}
  else controller.close();
 }});
 const response=await channel.fetch('http://http.test/',{method:'POST',body});
 return {status:response.status,header:response.headers.get('x-channel'),body:await response.text()};
}
async function socket(channel){
 const response=await channel.fetch('http://http.test/socket',{headers:{Upgrade:'websocket'}});
 const ws=response.webSocket;if(!ws)throw new Error('missing WebSocket');ws.accept();
 const message=new Promise((resolve,reject)=>{
  const timeout=setTimeout(()=>reject(new Error('WebSocket timeout')),5000);
  ws.addEventListener('message',event=>{clearTimeout(timeout);resolve(event.data);},{once:true});
  ws.addEventListener('error',()=>{clearTimeout(timeout);reject(new Error('WebSocket error'));},{once:true});
 });
 ws.send('ping');const value=await message;ws.close(1000,'done');
 return {status:response.status,header:response.headers.get('x-channel'),message:value};
}
export default {async fetch(req,env){
 const root=env.ROOT.getByName('root'),result={};
 for(const kind of ['service','do','facet','dynamic']){
  try{
   result[kind]={};
   result[kind].direct=await root.direct(kind);
   const channel=await root.create(kind);result[kind].transferred=await http(channel);
   const stored=await env.STORE.getByName(kind).roundtrip(channel);result[kind].reloaded=await http(stored);
   result[kind].self=await (await stored.fetch('http://http.test/self')).text();
   result[kind].websocket=await socket(stored);
  }catch(error){result[kind]={...result[kind],error:error.message};}
 }
 try{result.rpc=await (await root.create('rpc')).fetch();}catch(error){result.rpc={error:error.message};}
 return Response.json(result);
}};
