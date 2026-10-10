import {WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
let saved, finished=false, calls=0;
class Target extends RpcTarget {ping(){calls++;return 42;} get value(){calls++;return 42;}}
export class Source extends WorkerEntrypoint {make(){return new Target();}}
export class Holder extends WorkerEntrypoint {
 async hold(){saved=await this.ctx.exports.Source.make(); const own=await saved.ping();
   while(!finished)await new Promise(r=>setTimeout(r,2)); return own;}
 async foreign(){const errors=[];
  for(const action of [()=>saved.ping(),()=>saved.value,()=>saved.dup()]) {
   try{const result=await action(); result?.[Symbol.dispose]?.(); errors.push(false);}
   catch(e){errors.push(e.message.includes('different request'));}
  }
  finished=true; return errors;
 }
}
export default {async fetch(req,env,ctx){
 const holding=ctx.exports.Holder.hold();
 while(!saved)await new Promise(r=>setTimeout(r,2));
 const errors=await ctx.exports.Holder.foreign();
 const own=await holding; return Response.json({errors,own,calls});
}};
