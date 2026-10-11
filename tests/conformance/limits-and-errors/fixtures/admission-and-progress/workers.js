// Real dynamically loaded Worker modules. No transport model or substitute RPC.
export const CODE = `
import { WorkerEntrypoint, waitUntil } from 'cloudflare:workers';
const token=crypto.randomUUID(), SIZE=24576, FRAME=8192;
const byte=(seed,offset)=>(seed+offset*17)&255;
const bytes=(seed,start,size)=>Uint8Array.from({length:size},(_,i)=>byte(seed,start+i));
export default class extends WorkerEntrypoint {
  probe(){return {token,waitUntil:typeof waitUntil==='function',crypto:typeof crypto.subtle.digest==='function',streams:typeof ReadableStream==='function'};}
  ping(value){return {token,value};}
  async hold(id,gate,fail=false){const value=await this.env.AUDIT.hold(id,gate,false);if(fail)throw new Error('planned:loaded:'+id);return {id,token,value};}
  async upload(id,stream,seed){await this.env.AUDIT.note('upload-enter:'+id);const r=stream.getReader();r.closed.catch(()=>{});let n=0,ended=false;try{for(let reads=0;reads<65536;reads++){const x=await r.read();if(x.done){ended=true;break;}for(let i=0;i<x.value.length;i++)if(x.value[i]!==byte(seed,n+i))throw new Error('worker upload byte mismatch');if(n===0&&x.value.length>0)await this.env.AUDIT.note('upload-prefix:'+id);n+=x.value.length;if(n>SIZE)throw new Error('worker upload overflow');}if(!ended)throw new Error('worker upload read-operation bound');if(n!==SIZE)throw new Error('worker upload terminal length');await this.env.AUDIT.note('upload-effect:'+id);return {id,token,bytes:n};}catch(error){await r.cancel('worker-upload-stop:'+id);throw error;}finally{r.releaseLock();}}
  download(id,seed,gate){let n=0,cancelled=false;const audit=this.env.AUDIT;return new ReadableStream({async pull(c){if(n===FRAME){await audit.hold('worker-stream:'+id,gate);if(cancelled)return;}const value=bytes(seed,n,Math.min(FRAME,SIZE-n));n+=value.length;c.enqueue(value);if(n===SIZE){c.close();await audit.note('worker-source-close:'+id);}},async cancel(reason){cancelled=true;await audit.note('worker-source-cancel:'+id,String(reason));}},{highWaterMark:0});}
  background(id,gate,fail=false){const audit=this.env.AUDIT;const p=audit.hold(id,gate,fail).then(()=>audit.note('background-ok:'+id),error=>audit.note('background-failed:'+id,String(error)));waitUntil(p);return {id,token,scheduled:true};}
  async digest(id,gate,seed){await this.env.AUDIT.hold(id,gate);const payload=bytes(seed,0,131072);const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',payload));const digest=[...hash].map(x=>x.toString(16).padStart(2,'0')).join('');await this.env.AUDIT.note('digest-effect:'+id);return {id,token,bytes:payload.length,digest};}
}
`;
export const ZLIB_CODE = `
import { WorkerEntrypoint } from 'cloudflare:workers';
import { deflateSync, inflateSync } from 'node:zlib';
const token=crypto.randomUUID();
export default class extends WorkerEntrypoint {
  probe(){return {token,zlib:typeof deflateSync==='function'&&typeof inflateSync==='function'};}
  ping(value){return {token,value};}
  async roundtrip(id,gate,seed){await this.env.AUDIT.hold(id,gate);const input=Uint8Array.from({length:65536},(_,i)=>(seed+i*17)&255);const zipped=deflateSync(input);if(zipped.length===0||zipped.length>65800)throw new Error('compressed size bound');const output=inflateSync(zipped);if(output.length!==input.length)throw new Error('inflate length');for(let i=0;i<output.length;i++)if(output[i]!==((seed+i*17)&255))throw new Error('inflate byte mismatch');const hash=new Uint8Array(await crypto.subtle.digest('SHA-256',output));await this.env.AUDIT.note('zlib-effect:'+id);return {id,token,bytes:output.length,compressed:zipped.length,digest:[...hash].map(x=>x.toString(16).padStart(2,'0')).join('')};}
}
`;
export function loadWorker(s,label,source=CODE) {
  const audit=s.root.ctx.exports.Audit({props:{root:s.peerName,tag:s.tag}});
  const w=s.root.env.LOADER.load({compatibilityDate:'2026-09-04',compatibilityFlags:['rpc_params_dup_stubs','nodejs_compat'],mainModule:'worker.js',modules:{'worker.js':source},env:{AUDIT:audit},globalOutbound:null});
  s.workers.push(w);const entry=w.getEntrypoint(undefined,{props:{label}});s.entries.push(entry);return entry;
}
