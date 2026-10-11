import {DurableObject, RpcTarget} from 'cloudflare:workers';
class Lease extends RpcTarget { constructor(n){super();this.n=n;} value(){return this.n;} }
export class Holder extends DurableObject {
  held=[];calls=0;
  // A long-lived holder that never releases what it opened (as an actor
  // whose context never ends keeps undisposed RPC results).
  async open(n){const s=await this.env.SVC.open(n);this.held.push(s);return s.ping();}
  async work(n){this.calls++;return this.env.SVC.work(n);}
  lease(n){return new Lease(n);}
  stats(){return {held:this.held.length,calls:this.calls};}
  async pingAll(){const out={ok:0,err:[]};for(const s of this.held){try{await s.ping();out.ok++;}catch(e){out.err.push(String(e.message).slice(0,120));}}return out;}
}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
export default {
  async fetch(request, env) {
    const u=new URL(request.url), h=env.HOLDER.getByName('holder');
    const n=Number(u.searchParams.get('n')||'1');
    if(u.pathname==='/stats')return Response.json(await h.stats());
    if(u.pathname==='/pingall')return Response.json(await h.pingAll());
    if(u.pathname==='/burst'){
      // Cross-node RPC: this stateless request runs on the ingress node and
      // calls the actor on its owner node. Every call also crosses the
      // owner's stateless service pool. Leases are exported by the actor and
      // released by this caller (capability/session churn).
      const work=[];
      for(let i=0;i<n;i++)work.push(h.work(i));
      const leases=[];
      for(let i=0;i<Math.ceil(n/10);i++)leases.push(h.lease(i));
      const got=await Promise.all(leases);
      let sum=0;for(const l of got){sum+=await l.value();l[Symbol.dispose]();}
      await Promise.all(work);
      if(u.searchParams.get('open')==='1')await h.open(Date.now());
      return Response.json({calls:n,leases:got.length,sum});
    }
    return new Response('not found',{status:404});
  }
};
