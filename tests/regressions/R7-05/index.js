import {DurableObject,RpcTarget,restore} from 'cloudflare:workers';
const sleep=()=>new Promise(r=>setTimeout(r,10));
class Callback extends RpcTarget {constructor(done){super();this.done=done;}ping(){return 42;}[Symbol.dispose](){this.done();}}
class Target extends RpcTarget {
 constructor(actor){super();this.actor=actor;}
 callback(){this.actor.created=(this.actor.created??0)+1;return new Callback(()=>this.actor.disposed=(this.actor.disposed??0)+1);}
 async echo(arg,cb){await sleep();return {value:arg.nested.value,callback:cb?await cb.ping():0};}
}
export class Actor extends DurableObject {
 async [restore](){await sleep();if(this.failRestore)throw new Error('restore failed');return new Target(this);}
 async test(mode){
  let cap=await this.ctx.restore({mode});
  const callback=await cap.callback();
  if(mode!=='live'){await this.ctx.storage.put('cap',cap);cap[Symbol.dispose]();cap=await this.ctx.storage.get('cap');}
  const prior=mode==='pending'?cap.echo({nested:{value:0}},null):null;
  const arg={nested:{value:1}},call=cap.echo(arg,callback);arg.nested.value=2;callback[Symbol.dispose]();cap[Symbol.dispose]();
  const value=await call;if(prior)await prior;
  for(let i=0;i<50&&this.disposed!==this.created;i++)await sleep();
  return {...value,balanced:this.disposed===this.created};
 }
 async failures(){
  let cap=await this.ctx.restore({});const cb=await cap.callback();
  let encoding=false;try{await cap.echo({nested:{value:1},bad:Symbol()},cb);}catch(e){encoding=e.name==='DataCloneError';}
  const usable=await cb.ping();await this.ctx.storage.put('cap',cap);cap[Symbol.dispose]();cap=await this.ctx.storage.get('cap');this.failRestore=true;
  const call=cap.echo({nested:{value:1}},cb);cb[Symbol.dispose]();cap[Symbol.dispose]();
  let restoration=false;try{await call;}catch(e){restoration=e.message.includes('restore failed');}
  for(let i=0;i<50&&this.disposed!==this.created;i++)await sleep();
  return {encoding,usable,restoration,balanced:this.disposed===this.created};
 }
}
export default {async fetch(req,env){const out={};for(const mode of ['live','lazy','pending','failures'])try{const actor=env.ACTOR.getByName(mode);out[mode]=mode==='failures'?await actor.failures():await actor.test(mode);}catch(e){out[mode]={error:e.message};}return Response.json(out);}};
