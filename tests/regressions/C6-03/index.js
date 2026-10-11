import {DurableObject, RpcTarget} from 'cloudflare:workers';
class Channel extends RpcTarget { constructor(){super();this.n=0;} async ping(){await new Promise(r=>setTimeout(r,2));return ++this.n;} }
export class Target extends DurableObject {
  lease(){return new Channel();}
  init(){return true;}
}
export default {
  async fetch(request, env) {
    const u=new URL(request.url);
    if(u.pathname==='/pong')return new Response('pong');
    if(u.pathname==='/init')return Response.json(await env.TARGET.getByName('t').init());
    if(u.pathname==='/burst'){
      // Concurrent ordered capability calls to the owner node, plus plain
      // subrequests to the owner's public listener.
      const n=Number(u.searchParams.get('n')||'50'),edge=u.searchParams.get('edge');
      const s=await env.TARGET.getByName('t').lease();
      const calls=[];for(let i=0;i<n;i++)calls.push(s.ping());
      const fetches=[];if(edge)for(let i=0;i<Math.ceil(n/4);i++)fetches.push(fetch(edge+'/pong').then(r=>r.text()));
      const r=await Promise.all(calls);await Promise.all(fetches);s[Symbol.dispose]();
      return Response.json({calls:r.length,max:Math.max(...r),fetches:fetches.length});
    }
    return new Response('nf',{status:404});
  }
};
