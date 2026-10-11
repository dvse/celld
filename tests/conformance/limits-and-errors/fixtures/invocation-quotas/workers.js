// Real Worker Loader code. No Node/model execution of these modules is permitted.
export const WORKER = `
import { WorkerEntrypoint } from 'cloudflare:workers';
const token=crypto.randomUUID();
function burn(n) { let x=0x12345678; for(let i=0;i<n;i++) x=(Math.imul(x^i,1664525)+1013904223)|0; return x; }
export default class extends WorkerEntrypoint {
  probe(){return {token,kind:'bounded-resource',crypto:typeof crypto.subtle?.deriveBits==='function'};}
  async sequence(labels){const out=[];for(const label of labels){try{out.push({ok:true,value:await this.env.AUDIT.note(label)});}catch(e){out.push({ok:false,error:String(e)});}}return out;}
  async parallel(){return Promise.all(['a','b','c','d'].map(async label=>{try{return {label,ok:true,value:await this.env.AUDIT.note(label)};}catch(e){return {label,ok:false,error:String(e)};}}));}
  async failedThenContinue(){const out=[];for(const label of ['fail','ok','overflow']){try{out.push({ok:true,value:await this.env.AUDIT.note(label,label==='fail')});}catch(e){out.push({ok:false,error:String(e)});}}return out;}
  async mixed(){const out=[];try{const r=await this.env.AUDIT.fetch('https://fixture.invalid/mixed-fetch');out.push({ok:true,value:await r.json()});}catch(e){out.push({ok:false,error:String(e)});}for(const label of ['mixed-rpc','mixed-overflow']){try{out.push({ok:true,value:await this.env.AUDIT.note(label)});}catch(e){out.push({ok:false,error:String(e)});}}return out;}
  async deniedThenRpc(){const out=[];try{await fetch('https://fixture.invalid/never-network');out.push('UNEXPECTED-EGRESS');}catch(e){out.push(String(e));}try{await this.env.AUDIT.note('must-not-arrive');out.push('UNEXPECTED-RPC');}catch(e){out.push(String(e));}return out;}
  async held(label){await this.env.AUDIT.hold(label);try{await this.env.AUDIT.note('overflow:'+label);return 'UNEXPECTED';}catch(e){return {label,error:String(e)};}}
  async compute(){await this.env.AUDIT.note('compute-entered');return {token,value:burn(8000000)};}
  async wait(){const start=Date.now();await new Promise(resolve=>setTimeout(resolve,250));return {token,elapsed:Date.now()-start};}
  props(){return {token,length:this.ctx.props?.bytes?.byteLength??0};}
  randomQuota(){const out=[];for(let i=0;i<2;i++){const bytes=new Uint8Array(65537);try{crypto.getRandomValues(bytes);out.push({ok:true});}catch(e){out.push({ok:false,name:e.name,message:e.message,untouched:bytes.every(v=>v===0)});}}const good=new Uint8Array(65536);return {out,same:crypto.getRandomValues(good)===good,length:good.length};}
  async nativeKdf(){const key=await crypto.subtle.importKey('raw',new TextEncoder().encode('owned-fixture-password'),'PBKDF2',false,['deriveBits']);const value=await crypto.subtle.deriveBits({name:'PBKDF2',salt:new Uint8Array([1,2,3,4]),iterations:20000,hash:'SHA-256'},key,256);return {length:value.byteLength};}
  async allocateHeld(label){const bytes=new Uint8Array(1048576);bytes.fill(label==='left'?17:29);await this.env.AUDIT.hold(label);let sum=0;for(let i=0;i<bytes.length;i++)sum+=bytes[i];return {label,length:bytes.length,sum};}
}
`;
export const STARTUP = `
import { WorkerEntrypoint } from 'cloudflare:workers';
let value=0;for(let i=0;i<8000000;i++)value=(value+3)>>>0;
export default class extends WorkerEntrypoint { probe(){return {kind:'startup-finite',value};} }
`;
export const TINY = `import {WorkerEntrypoint} from 'cloudflare:workers';export default class extends WorkerEntrypoint{probe(){return {kind:'tiny'};}}`;
