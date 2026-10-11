import {RpcTarget,WorkerEntrypoint} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Source extends WorkerEntrypoint {async make(){await new Promise(r=>setTimeout(r,2)); return {child:new Target(),data:{x:1},opaque:new Date()};}}
export default {async fetch(req,env,ctx){
 const pending=ctx.exports.Source.make();
 const [a,b]=await Promise.all([pending.child,pending.child]);
 const original=await pending;
 const independent=a!==b&&a!==original.child;
 a[Symbol.dispose]();
 let alive;try{alive=await b.ping();}catch{alive=false;}
 const copy=await pending.data; copy.x=9;
 const cloned=original.data.x===1;
 let restricted;try{await pending.opaque.getTime(); restricted=false;}catch{restricted=true;}
 return Response.json({independent,alive,cloned,restricted});
}};
