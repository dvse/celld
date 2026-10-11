import {RpcTarget, WorkerEntrypoint} from 'cloudflare:workers';
let disposals=0;
class Target extends RpcTarget { ping(){return 42;} [Symbol.dispose](){disposals++;} }
export class Source extends WorkerEntrypoint {
  make(){const t=new Target(); const result={a:t,b:t,map:new Map([['t',t]]),array:[t]}; result.self=result; return result;}
  count(){return disposals;}
}
export default {async fetch(req,env,ctx){
 const s=ctx.exports.Source;
 const r=await s.make();
 const identity=r.a===r.b&&r.a===r.map.get('t')&&r.a===r.array[0]&&r.self===r;
 const retained=r.a.dup(); r[Symbol.dispose]();
 let alive; try{alive=await retained.ping();}catch(e){alive=false;}
 const before=await s.count(); retained[Symbol.dispose]();
 await new Promise(resolve=>setTimeout(resolve,20));
 const after=await s.count();
 return Response.json({identity,alive,before,after});
}};
