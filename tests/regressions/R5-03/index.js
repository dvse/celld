import {DurableObject,RpcTarget} from 'cloudflare:workers';
class Gate extends RpcTarget {
 constructor(){super();this.count=0;this.block=new Promise(r=>this.release=r);}
 wait(){this.count++;return this.block;}
}
const CODE=`import {DurableObject} from 'cloudflare:workers';
export class Leaf extends DurableObject {
 child(){return this.ctx.facets.get('nested',()=>({class:this.ctx.exports.Leaf}));}
 put(n){this.ctx.storage.kv.put('n',n);}
 read(){return this.ctx.storage.kv.get('n')??0;}
 async seed(){this.put(1);await this.child().put(1);}
 async arm(gate){await gate.wait();this.put(2);}
 armChild(gate){return this.child().arm(gate);}
 async tree(){return [this.read(),await this.child().read()];}
}`;
const ready=new Set(),resumes=new Map();
export class Leaf extends DurableObject {
 child(){return this.ctx.facets.get('child',()=>({class:this.ctx.exports.Leaf}));}
 put(n){this.ctx.storage.kv.put('n',n);}
 read(){return this.ctx.storage.kv.get('n')??0;}
 async seed(){this.put(1);await this.child().put(1);}
 async arm(key){ready.add(key);await new Promise(r=>resumes.set(key,r));this.put(2);}
 armChild(){return this.child().arm('child');}
 async tree(){return [this.read(),await this.child().read()];}
}
export class Root extends DurableObject {
 leaf(name){return this.ctx.facets.get(name,()=>({class:this.ctx.exports.Leaf}));}
 observed(){return this.observations??{};}
 async test(){
  this.observations={};
  const a=this.leaf('a');await a.seed();
  const p=a.arm('a'),q=a.armChild();
  while(!ready.has('a')||!ready.has('child'))await new Promise(r=>setTimeout(r,1));
  this.ctx.facets.clone('a','b');for(const resume of resumes.values())resume();
  await Promise.all([p,q]);
  const snapshot=await this.leaf('b').tree(),source=await a.tree();
  Object.assign(this.observations,{snapshot,source});
  this.ctx.facets.clone('a','c');this.leaf('c');this.ctx.facets.abort('c',new Error('test abort'));
  const reopen=await this.leaf('c').tree();
  this.ctx.facets.clone('a','d');this.ctx.facets.clone('d','d');
  const self=await this.leaf('d').tree();
  this.ctx.facets.clone('a','e');this.ctx.facets.delete('e');
  const deleted=await this.leaf('e').read();
  this.ctx.facets.delete('f');this.ctx.facets.clone('a','f');
  const afterDelete=await this.leaf('f').tree();
  this.ctx.facets.clone('a','g');this.ctx.facets.clone('g','h');
  const chained=await this.leaf('h').tree();
  for(const name of ['b','c','d','f','g','h'])this.ctx.facets.abort(name,new Error('test reload'));
  const reloaded=await this.leaf('b').tree();
  return {snapshot,source,reopen,self,deleted,afterDelete,chained,reloaded};
 }
 async dynamic(){
  const worker=this.env.LOADER.get('snapshot-cross-isolate',()=>({compatibilityDate:'2026-08-01',mainModule:'leaf.js',modules:{'leaf.js':CODE}}));
  const leaf=name=>this.ctx.facets.get(name,()=>({class:worker.getDurableObjectClass('Leaf')}));
  const a=leaf('loaded-a'),gate=new Gate();await a.seed();
  const p=a.arm(gate),q=a.armChild(gate);
  while(gate.count<2)await new Promise(r=>setTimeout(r,1));
  this.ctx.facets.clone('loaded-a','loaded-b');gate.release();
  await Promise.all([p,q]);
  return {snapshot:await leaf('loaded-b').tree(),source:await a.tree()};
 }
 async initFailure(){await this.leaf('source').put(1);await this.leaf('destination').put(9);return 1;}
 failClone(){this.ctx.facets.clone('source','destination');return 'acknowledged';}
}
export default {async fetch(req,env){const url=new URL(req.url);const actor=env.ROOT.getByName(url.pathname==='/failure'?'failure':'test');
 if(url.pathname==='/init-failure')return Response.json(await env.ROOT.getByName('failure').initFailure());
 if(url.pathname==='/failure')return Response.json(await actor.failClone());
 try{return Response.json({...await actor.test(),dynamic:await actor.dynamic()});}catch(e){return Response.json({...await actor.observed(),error:e.message});}}};
