export const PROFILE='fetch-redirect-stress-candidate8d27-v1';
export const LIMITS=Object.freeze({wallMs:24000,payloadBytes:4194304,operationBytes:131072,operations:24,networkRequests:6,events:512,readOperations:262144});
export const check=(ok,message)=>{if(!ok)throw new Error(message);};
export class Blocked extends Error {constructor(message){super(message);this.name='Blocked';this.code='BLOCKED_PREREQUISITE';}}
export const ready=(ok,message)=>{if(!ok)throw new Blocked(message);};
export const ident=x=>{check(typeof x==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(x),'bounded identifier');return x;};
export function privateOrigin(value){const u=new URL(value);check(u.origin==='http://192.168.77.1:18080'&&u.pathname==='/'&&!u.username&&!u.password&&!u.search&&!u.hash,'fixed private fixture origin required');return u.origin;}
export function routeName(value){check(typeof value==='string'&&value.length<=200,'bounded fixture route');const parts=value.split('/');check(parts.length>=1&&parts.length<=3,'fixture route depth');for(const part of parts)ident(part);return value;}
export function configuredLocation(location,base,origin,root,routes){
  const u=new URL(location,base),prefix='/root/'+ident(root)+'/op/';
  check(u.origin===privateOrigin(origin)&&!u.username&&!u.password&&!u.hash&&u.pathname.startsWith(prefix),'redirect stays in owned fixture');
  const route=routeName(u.pathname.slice(prefix.length)),target=routes.get(route);
  check(target&&target.query===u.search,'redirect targets earlier configured endpoint/query');
  return {url:u.href,route,target};
}
export function bytes(label,n=8193){ident(label);check(Number.isInteger(n)&&n>=0&&n<=LIMITS.operationBytes,'body bound');const out=new Uint8Array(n);let seed=0;for(const c of label)seed=(seed*33+c.charCodeAt(0))>>>0;for(let i=0;i<n;i++)out[i]=(seed+29*i+(i>>>7))&255;return out;}
export function join(parts){let n=0;for(const p of parts)n+=p.length;check(n<=LIMITS.operationBytes,'joined body bound');const out=new Uint8Array(n);let at=0;for(const p of parts){out.set(p,at);at+=p.length;}return out;}
export function equal(a,b,label){check(a.length===b.length,label+': length');for(let i=0;i<a.length;i++)check(a[i]===b[i],label+': byte '+i);}
export const hash=async value=>[...new Uint8Array(await crypto.subtle.digest('SHA-256',value))].map(x=>x.toString(16).padStart(2,'0')).join('');
export function gate(){let resolve;const promise=new Promise(r=>{resolve=r;});return {promise,resolve,open:false};}
export async function bounded(promise,ms,label){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(label+' deadline')),ms);})]);}finally{clearTimeout(timer);}}
