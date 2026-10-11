import {WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
let disposed=0,entered=0;
class Parameter extends RpcTarget {[Symbol.dispose](){disposed++;}}
class Child extends RpcTarget {value(){return 43;}}
class Target extends RpcTarget {
 async ping(){entered++;await new Promise(r=>setTimeout(r,20));return 42;}
 async child(){await new Promise(r=>setTimeout(r,20));return new Child();}
 async fail(){await new Promise(r=>setTimeout(r,20));throw new Error('expected');}
}
export class Factory extends WorkerEntrypoint {
 make(p){this.parameter=p.dup();return new Target();}
}
export default {async fetch(request,env,ctx){
 const make=()=>ctx.exports.Factory.make(new Parameter());
 let stub=await make();let p=stub.ping();stub[Symbol.dispose]();const immediate=await p;
 stub=await make();p=stub.ping();while(entered<2)await new Promise(r=>setTimeout(r,2));
 stub[Symbol.dispose]();const waiting=await p;
 stub=await make();p=stub.child();const pipelined=p.value();stub[Symbol.dispose]();
 const child=await p;const descendant=await pipelined;child[Symbol.dispose]();p[Symbol.dispose]();
 stub=await make();p=stub.fail();stub[Symbol.dispose]();let failed=false;
 try{await p;}catch(e){failed=e.message==='expected';}
 for(let i=0;i<50&&disposed<4;i++)await new Promise(r=>setTimeout(r,10));
 return Response.json({immediate,waiting,descendant,failed,disposed});
}};
