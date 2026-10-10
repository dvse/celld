import {WorkerEntrypoint,RpcTarget} from 'cloudflare:workers';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
class Target extends RpcTarget {ping(){return 42;}async echo(a,cb){await sleep(1);return [a.nested.value,await cb.ping()];}}
export class Source extends WorkerEntrypoint {
 async target(){await sleep(5);return new Target();}
 async plain(){await sleep(5);return {nested:{async echo(a,cb){return [a.nested.value,await cb.ping()];}}};}
 async callable(){await sleep(5);return async(a,cb)=>[a.nested.value,await cb.ping()];}
 async failure(){await sleep(5);throw new Error('parent failed');}
}
export default {async fetch(r,e,c){const out={};
 for(const kind of ['target','plain','callable'])for(const timing of ['pending','settled']){
  const key=kind+'-'+timing;
  try{const cb=await c.exports.Source.target(),parent=c.exports.Source[kind]();if(timing==='settled')await parent;
   const arg={nested:{value:1}},call=kind==='callable'?parent(arg,cb):kind==='plain'?parent.nested.echo(arg,cb):parent.echo(arg,cb);arg.nested.value=2;cb[Symbol.dispose]();
   out[key]=await call;parent[Symbol.dispose]();
  }catch(e){out[key]={error:e.message};}
 }
 try{const p=c.exports.Source.target(),original=await p,call=p.ping();original[Symbol.dispose]();out.disposedTarget=await call;}catch(e){out.disposedTarget={error:e.message};}
 try{const p=c.exports.Source.target();p[Symbol.dispose]();await p.ping();out.disposedRoot=false;}catch(e){out.disposedRoot=e.message.includes('disposed');}
 try{const p=c.exports.Source.failure();await p.ping();out.failedParent=false;}catch(e){out.failedParent=e.message.includes('parent failed');}
 return Response.json(out);
}};
