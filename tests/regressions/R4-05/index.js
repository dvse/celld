import {WorkerEntrypoint,restore} from 'cloudflare:workers';
export class Receiver extends WorkerEntrypoint {
 async fetch(req){return new Response(req.body,{status:201,headers:{'x-channel':'http'}});}
}
export class Source extends WorkerEntrypoint {
 [restore](){return this.ctx.exports.Receiver;}
 async restored(){return await this.ctx.restore({id:'receiver'});}
}
export default {async fetch(req,env,ctx){
 try{
  const channel=await ctx.exports.Source.restored();
  const response=await channel.fetch('https://example.test/',{method:'POST',body:'payload'});
  return Response.json({status:response.status,header:response.headers.get('x-channel'),body:await response.text()});
 }catch(e){return Response.json({error:e.name});}
}};
