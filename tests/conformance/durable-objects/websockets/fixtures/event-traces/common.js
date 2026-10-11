export const PROFILE = 'active-websocket-candidate-v1';
export const BINARY = '8d27f1d423e74dd582dd36d47cc61aef2017344da84720fd5bbe1ff7fbff105f';
export const ORIGIN = 'http://192.168.77.1:18080';
export const LIMIT = Object.freeze({peers:8,livePeers:4,messages:256,peerMessages:64,frameBytes:32768,wireBytes:524288,controls:128,events:1024,traceMs:16000,cleanupMs:4000,evidenceMs:24000});
export function check(ok, text) { if (!ok) throw new Error('ASSERT: '+text); }
export function need(ok,text) { if(!ok){const e=new Error(text);e.name='BlockedPrerequisite';throw e;} }
export function ident(s) { check(typeof s==='string'&&/^[A-Za-z0-9_-]{1,80}$/.test(s),'bounded identifier');return s; }
export function defer(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});promise.catch(()=>{});return {promise,resolve,reject};}
export async function bounded(p,ms,label){let timer;try{return await Promise.race([p,new Promise((_,r)=>{timer=setTimeout(()=>r(new Error('TIMEOUT: '+label)),ms);})]);}finally{clearTimeout(timer);}}
export function bytes(seed,n){check(Number.isInteger(n)&&n>=0&&n<=LIMIT.frameBytes,'frame allocation bound');const out=new Uint8Array(n);for(let i=0;i<n;i++)out[i]=(seed+i*31)%256;return out;}
export function shape(data){
  if(typeof data==='string')return {type:'text',value:data,bytes:new TextEncoder().encode(data).length};
  const a=data instanceof ArrayBuffer?new Uint8Array(data):ArrayBuffer.isView(data)?new Uint8Array(data.buffer,data.byteOffset,data.byteLength):null;
  check(a!==null,'message must be text or binary ArrayBuffer');return {type:'binary',value:Array.from(a,b=>b.toString(16).padStart(2,'0')).join(''),bytes:a.byteLength};
}
export function same(a,b,label){check(JSON.stringify(a)===JSON.stringify(b),label);}
export function fromSpec(s){check(s&&['text','binary'].includes(s.type),'valid fixture send kind');if(s.type==='text'){check(typeof s.value==='string','text payload');return s.value;}return bytes(s.seed,s.n);}
export function failInfo(e){return {name:e?.name||'Error',message:String(e?.message||e).slice(0,500)};}
export function closeValid(code,reason){check(code===1000||Number.isInteger(code)&&code>=3000&&code<=4999,'normal application close code');check(new TextEncoder().encode(reason).length<=123,'normal close reason');}
