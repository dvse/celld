import {RpcTarget,WorkerEntrypoint} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Source extends WorkerEntrypoint {
 make(){const array=new Array(5);array[0]=new Target();array.extra=new Target();
 const result={array};Object.defineProperty(result,'__proto__',{value:{sentinel:7},enumerable:true});return result;}
}
export default {async fetch(req,env,ctx){
 const r=await ctx.exports.Source.make(); const a=r.array;
 let extra;try{extra=await a.extra.ping();}catch{extra=false;}
 return Response.json({ownProto:Object.hasOwn(r,'__proto__'),proto:r.__proto__.sentinel??null,
  length:a.length,holes:[1,2,3,4].every(k=>!(k in a)),extra,first:await a[0].ping()});
}};
