import {DurableObject,RpcTarget,restore} from 'cloudflare:workers';
const DUP=false,sleep=()=>new Promise(r=>setTimeout(r,10));
class Target extends RpcTarget {constructor(id){super();this.value=id;}id(){return this.value;}}
export class Receiver extends DurableObject {read(cap){return cap.id();}graph(value){return value.cap.id();}}
export class Actor extends DurableObject {
 async [restore](){this.restores=(this.restores??0)+1;const id=this.restores;await sleep();if(this.failRestore)throw new Error('restore failed');return new Target(id);}
 async prepare(mode){let cap=await this.ctx.restore({});if(mode!=='live'){await this.ctx.storage.put('cap',cap);cap[Symbol.dispose]();cap=await this.ctx.storage.get('cap');}return cap;}
 async test(mode){
  const cap=await this.prepare(mode),before=this.restores;
  const prior=mode==='pending'?cap.id():null;
  const remote=this.env.RECEIVER.getByName('receiver').read(cap);
  let local;try{local=await cap.id();}catch(e){local='disposed';}
  const id=await remote;if(prior)await prior;cap[Symbol.dispose]();
  return {same:DUP?local===id:local==='disposed',restores:this.restores-before,prior:prior===null||await prior===id};
 }
 async duplicate(){const cap=await this.prepare('lazy'),before=this.restores,copy=cap.dup();const ids=await Promise.all([cap.id(),copy.id(),this.env.RECEIVER.getByName('receiver').read(copy)]);cap[Symbol.dispose]();copy[Symbol.dispose]();return {same:ids.every(x=>x===ids[0]),restores:this.restores-before};}
 async failure(){const cap=await this.prepare('lazy'),before=this.restores;this.failRestore=true;const remote=this.env.RECEIVER.getByName('receiver').read(cap);let first=false,second=!DUP;try{await remote;}catch(e){first=e.message.includes('restore failed');}if(DUP)try{await cap.id();}catch(e){second=e.message.includes('restore failed');}cap[Symbol.dispose]();return {first,second,restores:this.restores-before};}
 async rollback(){const cap=await this.prepare('lazy');let rejected=false;try{await this.env.RECEIVER.getByName('receiver').graph({cap,bad:Symbol()});}catch(e){rejected=e.name==='DataCloneError';}let usable=false;try{usable=Number.isInteger(await cap.id());}catch{}finally{cap[Symbol.dispose]();}return {rejected,usable};}
 async makeReturn(mode,nested){this.sent=await this.prepare(mode);return nested?{cap:this.sent,...(nested==='disposer'?{[Symbol.dispose](){}}:{})}:this.sent;}
 async oldUse(){try{return {value:await this.sent.id(),restores:this.restores};}catch(e){return {disposed:e.message.includes('disposed'),restores:this.restores};}}
}
export default {async fetch(req,env){const out={};for(const mode of ['live','lazy','pending','duplicate','failure','rollback'])try{const actor=env.ACTOR.getByName(mode);out[mode]=['live','lazy','pending'].includes(mode)?await actor.test(mode):await actor[mode]();}catch(e){out[mode]={error:e.message};}
 for(const mode of ['live','lazy','pending'])try{const actor=env.ACTOR.getByName('returned-'+mode),cap=await actor.makeReturn(mode,false),id=await cap.id();cap[Symbol.dispose]();const state=await actor.oldUse();out['returned-'+mode]={id:Number.isInteger(id),disposed:state.disposed===true,restores:state.restores};}catch(e){out['returned-'+mode]={error:e.message};}
 for(const nested of ['nested','disposer'])try{const actor=env.ACTOR.getByName(nested),graph=await actor.makeReturn('live',nested),before=await actor.oldUse();await graph.cap.id();graph[Symbol.dispose]();let after;for(let i=0;i<50;i++){after=await actor.oldUse();if(after.disposed)break;await sleep();}out[nested]={before:Number.isInteger(before.value),after:after.disposed===true,sameRestores:before.restores===after.restores};}catch(e){out[nested]={error:e.message};}
 return Response.json(out);}};
