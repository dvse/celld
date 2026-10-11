import {DurableObject, RpcTarget, RpcStub} from 'cloudflare:workers';
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
class Recorder extends RpcTarget {
  constructor(log){super();this.log=log;}
  record(x){this.log.push(x);return this.log.length;}
}
export class Sink extends DurableObject {
  log=[];
  // One long-lived local stub: every dup() sent out names the same export.
  get(){this.s??=new RpcStub(new Recorder(this.log));return this.s.dup();}
  seen(){return this.log.slice();}
}
export default {
  async fetch(request, env, ctx) {
    const u=new URL(request.url), sink=env.SINK.getByName('sink');
    if(u.pathname==='/init')return Response.json(await sink.seen());
    if(u.pathname==='/fire'){
      // Fire-and-forget: the request ends before the ordered call is sent.
      const s=await sink.get();
      const n=Number(u.searchParams.get('n')||'1');
      for(let i=0;i<n;i++)s.record('fire-'+u.searchParams.get('tag')+'-'+i).catch(()=>{});
      return Response.json({fired:n});
    }
    if(u.pathname==='/call'){
      const s=await sink.get(),t=Date.now();
      try{
        const r=await Promise.race([s.record('call-'+u.searchParams.get('tag')),sleep(Number(u.searchParams.get('wait')||'15000')).then(()=>'timeout')]);
        return Response.json({result:r,ms:Date.now()-t});
      }catch(e){return Response.json({error:String(e.message),ms:Date.now()-t});}
    }
    if(u.pathname==='/seen')return Response.json(await sink.seen());
    return new Response('not found',{status:404});
  }
};
