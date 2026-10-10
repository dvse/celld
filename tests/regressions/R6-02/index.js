import {WorkerEntrypoint,RpcTarget,DurableObject,restore} from 'cloudflare:workers';
class Target extends RpcTarget {ping(){return 42;}}
export class Producer extends DurableObject {[restore](){return new Target();}make(){return this.ctx.restore({});}}
export class Forward extends WorkerEntrypoint {call(props){const worker=this.env.LOADER.get('forward',()=>({compatibilityDate:'2026-08-01',mainModule:'w.js',modules:{'w.js':code}}));return worker.getEntrypoint('Receiver',{props}).props();}}
const code=`import {WorkerEntrypoint} from 'cloudflare:workers';
export class Receiver extends WorkerEntrypoint {
 props(){return this.ctx.props.tag??'empty';}
 async target(){return await this.ctx.props.target.ping();}
 async fetch(){return new Response(await this.props());}
}`;
export default {async fetch(req,env,ctx){
 const worker=env.LOADER.get('props',()=>({compatibilityDate:'2026-08-01',mainModule:'w.js',modules:{'w.js':code}}));
 const result={};console.log('start');
 for(const [name,options] of [['absent',undefined],['empty',{props:{}}],['plain',{props:{tag:'x'}}]]){
  console.log(name);const entry=worker.getEntrypoint('Receiver',options);result[name]=[await entry.props(),await entry.props()];
  result[name].push(await (await entry.fetch('http://test/')).text());entry[Symbol.dispose]?.();
 }
 const rejected=[];
 for(const value of [new Target(),new ReadableStream(),new WritableStream()]){
  try{worker.getEntrypoint('Receiver',{props:{value}});rejected.push(false);}
  catch(e){rejected.push(e.name==='DataCloneError');}
 }
 result.rejected=rejected;
 if(rejected.some(value=>!value))return Response.json(result);
 console.log('target');const entry=worker.getEntrypoint('Receiver',{props:{target:await env.PRODUCER.getByName('source').make()}});
 result.target=[await entry.target(),await entry.target()];entry[Symbol.dispose]?.();
 result.forwarded=await ctx.exports.Forward.call({tag:'forward'});
 return Response.json(result);
}};
