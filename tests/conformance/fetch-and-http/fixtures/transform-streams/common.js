export const PROFILE='native-transform-frozen-v1';
export class AssertionFailure extends Error {constructor(message){super(message);this.name='FixtureAssertion';}}
export class ScheduleBlocked extends Error {constructor(message){super(message);this.name='ScheduleBlocked';}}
export const ok=(v,label)=>{if(!v)throw new AssertionFailure(label);};
export const canonical=v=>JSON.stringify(v,(_,x)=>x&&typeof x==='object'&&!Array.isArray(x)?Object.fromEntries(Object.keys(x).sort().map(k=>[k,x[k]])):x);
export const eq=(a,b,label)=>ok(canonical(a)===canonical(b),label);
export const hex=v=>Array.from(new Uint8Array(v.buffer??v,v.byteOffset??0,v.byteLength)).map(x=>x.toString(16).padStart(2,'0')).join('');
export const same=(a,b,label)=>{a=new Uint8Array(a.buffer??a,a.byteOffset??0,a.byteLength);b=new Uint8Array(b.buffer??b,b.byteOffset??0,b.byteLength);ok(a.length===b.length&&a.every((v,i)=>v===b[i]),label);};
export function bound(p,ms,label,Type=AssertionFailure){let timer;return Promise.race([p,new Promise((_,reject)=>timer=setTimeout(()=>reject(new Type(label+' deadline')),ms))]).finally(()=>clearTimeout(timer));}
export function observed(p){const result=Promise.resolve(p).then(value=>({ok:true,value}),error=>({ok:false,error}));return result;}
const owners=new WeakMap();
export function registerPromise(p,owner){owners.set(p,owner);}
export async function rejection(p,predicate,label){const outcome=await observed(p);ok(!outcome.ok,label+': unexpectedly fulfilled');ok(!(outcome.error instanceof AssertionFailure)&&!(outcome.error instanceof ScheduleBlocked),label+': fixture error cannot satisfy native rejection');ok(predicate(outcome.error),label+': unexpected '+String(outcome.error));owners.get(p)?.acceptExpected(outcome.error);return {name:outcome.error?.name,message:String(outcome.error)};}
export const typeError=e=>e?.name==='TypeError';
export const decompressionError=e=>e?.name==='TypeError'&&e?.message==='Decompression failed.';
export const unsupported=e=>e?.name==='NotSupportedError';
export async function collect(reader,charge){const chunks=[];let size=0;for(let n=0;n<4096;n++){const r=await reader.read();if(r.done){const out=new Uint8Array(size);let at=0;for(const chunk of chunks){out.set(chunk,at);at+=chunk.length;}return out;}ok(r.value instanceof Uint8Array,'native byte output required');size+=r.value.byteLength;ok(size<=262144,'per-operation output cap');charge(r.value.byteLength);chunks.push(r.value.slice());}throw new AssertionFailure('finite reader step bound');}
