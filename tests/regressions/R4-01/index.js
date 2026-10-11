import {WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
let disposals=0, failedDisposals=0;
class Parameter extends RpcTarget {[Symbol.dispose](){++disposals;}}
class Failed extends RpcTarget {[Symbol.dispose](){++failedDisposals;}}
class Child extends RpcTarget {ping(){return 42;}}
export class Factory extends WorkerEntrypoint {
 bad(){return {target:new Failed(),unserializable:Symbol("bad")};}
 make(parameter){this.retained=parameter.dup();return {a:new Child(),b:new Child()};}
}
export default {async fetch(req,env,ctx){
 const p=ctx.exports.Factory.make(new Parameter());
 const value=await p;
 value.a[Symbol.dispose]();
 const alive=await value.b.ping();
 const before=disposals;
 value[Symbol.dispose]();p[Symbol.dispose]();
 for(let i=0;i<20&&disposals===0;i++)await new Promise(r=>setTimeout(r,10));
 let rejected=false;
 try{await ctx.exports.Factory.bad();}catch(e){rejected=e.name==='DataCloneError';}
 for(let i=0;i<20&&failedDisposals===0;i++)await new Promise(r=>setTimeout(r,10));
 return Response.json({before,alive,after:disposals,rejected,failedDisposals});
}};
