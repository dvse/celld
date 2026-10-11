import {DurableObject,RpcTarget,WorkerEntrypoint,restore} from 'cloudflare:workers';
class Child extends RpcTarget {value(){return 43;}}
class Target extends RpcTarget {
 constructor(done){super();this.done=done;}
 [Symbol.dispose](){this.done();}
 async ping(){await new Promise(r=>setTimeout(r,10));return 42;}
 async child(){await new Promise(r=>setTimeout(r,10));return new Child();}
 async fail(){await new Promise(r=>setTimeout(r,10));throw new Error('expected');}
}
export class Actor extends DurableObject {
 [restore](params){if(params.http)return this.ctx.exports.Echo;
 this.created=(this.created??0)+1;return new Target(()=>this.disposed=(this.disposed??0)+1);}
 async http(mode){
  let cap=await this.ctx.restore({http:true});
  if(mode!=='live'){await this.ctx.storage.put('http',cap);cap[Symbol.dispose]?.();cap=await this.ctx.storage.get('http');}
  const prior=mode==='pending'?cap.fetch('http://echo/'):null;
  const call=cap.fetch('http://echo/'),disposable=typeof cap[Symbol.dispose]==='function';cap[Symbol.dispose]?.();
  const response=await call;const body=await response.text();
  if(prior)await (await prior).text();
  let rejected=!disposable;if(disposable)try{await cap.fetch('http://echo/');}catch(e){rejected=e.message.includes('disposed');}
  return {body,rejected};
 }
 async test(mode){
  let cap=await this.ctx.restore({id:mode});
  if(mode!=='live'){await this.ctx.storage.put('cap',cap);cap[Symbol.dispose]();cap=await this.ctx.storage.get('cap');}
  const prior=mode==='pending'?cap.ping():null;
  const copy=cap.dup(),call=cap.ping(),child=cap.child(),pipeline=child.value(),fail=cap.fail();
  cap[Symbol.dispose]();
  let rejected=false;try{await cap.ping();}catch(e){rejected=e.message.includes('disposed');}
  const immediate=await call, descendant=await pipeline;
  const result=await child;result[Symbol.dispose]();child[Symbol.dispose]();
  let failed=false;try{await fail;}catch(e){failed=e.message==='expected';}
  const duplicate=await copy.ping();copy[Symbol.dispose]();
  if(prior)await prior;
  for(let i=0;i<50&&this.disposed!==this.created;i++)await new Promise(r=>setTimeout(r,10));
  return {balanced:this.disposed===this.created,immediate,descendant,failed,rejected,duplicate,prior:prior===null?null:await prior};
 }
}
export class Echo extends WorkerEntrypoint {async fetch(){await new Promise(r=>setTimeout(r,10));return new Response('http');}}
export default {async fetch(req,env){const out={};for(const mode of ['live','lazy','pending']){
 try{const actor=env.ACTOR.getByName(mode);out[mode]={...await actor.test(mode),http:await actor.http(mode)};}catch(e){out[mode]={error:e.message};}}
 return Response.json(out);}};
