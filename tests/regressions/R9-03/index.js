import {DurableObject,WorkerEntrypoint,RpcTarget,restore} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Leaf extends DurableObject {async read(){return [this.ctx.props.value,await this.ctx.props.cap.ping()];}}
export class Forward extends WorkerEntrypoint {echo(cls){return cls;}}
const code=`import {DurableObject} from 'cloudflare:workers';export class Leaf extends DurableObject {async read(){return [this.ctx.props.value,await this.ctx.props.cap.ping()];}}`;
export class Actor extends DurableObject {
 [restore](){return new Target();}
 async test(kind){
  const cap=await this.ctx.restore({}),props={value:1,cap};
  const worker=kind==='loaded'?this.env.LOADER.get('leaf',()=>({compatibilityDate:'2026-08-01',compatibilityFlags:['allow_irrevocable_stub_storage'],mainModule:'leaf.js',modules:{'leaf.js':code}})):null;
  const cls=worker?worker.getDurableObjectClass('Leaf',{props}):this.ctx.exports.Leaf({props});props.value=2;
  const original=await cap.ping();cap[Symbol.dispose]();
  const a=this.ctx.facets.get('a',()=>({class:cls})),b=this.ctx.facets.get('b',()=>({class:cls}));
  const values=[await a.read(),await b.read()];
  this.ctx.facets.abort('a',new Error('reopen'));values.push(await this.ctx.facets.get('a',()=>({class:cls})).read());
  if(!worker){
   for(const key of ['x','y']){await this.ctx.storage.put(key,cls);const stored=await this.ctx.storage.get(key);values.push(await this.ctx.facets.get(key,()=>({class:stored})).read());}
   for(const key of ['f','g']){const forwarded=await this.ctx.exports.Forward.echo(cls);values.push(await this.ctx.facets.get(key,()=>({class:forwarded})).read());}
  }
  const rejected=[];for(const invalid of [new Target(),new ReadableStream(),new WritableStream()])try{worker?worker.getDurableObjectClass('Leaf',{props:{invalid}}):this.ctx.exports.Leaf({props:{invalid}});rejected.push(false);}catch(e){rejected.push(e.name==='DataCloneError');}
  for(const key of ['a','b','x','y','f','g'])this.ctx.facets.abort(key,new Error('cleanup'));
  return {original,values,rejected};
 }
}
export default {async fetch(r,e){const out={};for(const kind of ['static','loaded'])try{out[kind]=await e.ACTOR.getByName(kind).test(kind);}catch(e){out[kind]={error:e.message};}return Response.json(out);}};
