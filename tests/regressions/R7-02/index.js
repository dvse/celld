import {DurableObject,RpcTarget} from 'cloudflare:workers';
class Callback extends RpcTarget {
 constructor(actor,label){super();this.actor=actor;this.label=label;}
 ping(){return 42;}
 [Symbol.dispose](){this.actor.disposals[this.label]=(this.actor.disposals[this.label]||0)+1;}
}
export class Sender extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.disposals={};this.writes={};}
 init(){return this.ctx.id.toString();}
 async warm(){return this.env.RECEIVER.getByName('receiver').init();}
 async send(label){
  const cap=new Callback(this,label);const input=new ReadableStream({start(c){c.enqueue(new Uint8Array([1,2,3]));c.close();}});
  const output=new WritableStream({write:v=>{this.writes[label]=Array.from(v);}});
  try{return await this.env.RECEIVER.getByName('receiver').accept(label,{cap,input,output});}catch(e){return {error:e.message};}
 }
 ledger(){return {disposals:this.disposals,writes:this.writes};}
}
export class Receiver extends DurableObject {
 async fill(){for(let i=0;i<20;i++)await this.env.RECEIVER.getByName('padding-'+i).init();return true;}
 init(){return this.ctx.id.toString();}
 async accept(label,{cap,input,output}){
  const count=(await this.ctx.storage.get(label)||0)+1;await this.ctx.storage.put(label,count);
  const value=await cap.ping(),bytes=Array.from(new Uint8Array(await new Response(input).arrayBuffer()));
  const writer=output.getWriter();await writer.write(new Uint8Array([4,5]));await writer.close();
  return {value,bytes,count};
 }
 ledger(){return this.ctx.storage.list().then(m=>Object.fromEntries(m));}
}
export default {async fetch(req,env){const u=new URL(req.url),[kind,method]=u.pathname.slice(1).split('/');try{return Response.json({ok:await env[kind.toUpperCase()].getByName(kind)[method](...JSON.parse(u.searchParams.get('args')||'[]'))});}catch(e){return Response.json({error:e.message},{status:500});}}};
