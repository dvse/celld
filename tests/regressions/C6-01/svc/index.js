import {RpcTarget, WorkerEntrypoint} from 'cloudflare:workers';
// A session object exported by the stateless service pool; its holder keeps it.
class Session extends RpcTarget {
  constructor(n){super();this.n=n;this.pad='s'.repeat(4096);}
  ping(){return this.n;}
}
export class Svc extends WorkerEntrypoint {
  open(n){return new Session(n);}
  work(n){let x=0;for(let i=0;i<2000;i++)x+=i%7;return n+x;}
}
export default {fetch(){return new Response('svc');}};
