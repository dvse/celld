export const PROFILE='sqlite-concurrency-frozen-v1';
export const canonical=value=>JSON.stringify(value,(_,v)=>v instanceof Map?{__map:[...v]}:v instanceof ArrayBuffer?{__bytes:[...new Uint8Array(v)]}:ArrayBuffer.isView(v)?{__bytes:[...new Uint8Array(v.buffer,v.byteOffset,v.byteLength)]}:v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.keys(v).sort().map(k=>[k,v[k]])):v);
export const eq=(actual,expected,label)=>{if(canonical(actual)!==canonical(expected))throw new Error(label+': '+JSON.stringify({actual,expected}));};
export const ok=(value,label)=>{if(!value)throw new Error(label);};
export async function rejects(fn,pattern){try{await fn();}catch(error){if(error instanceof ScheduleBlocked)throw error;ok(pattern.test(String(error)),'unexpected rejection: '+String(error));return String(error);}throw new Error('expected rejection '+pattern);}
export function throws(fn,pattern){try{fn();}catch(error){if(error instanceof ScheduleBlocked)throw error;ok(pattern.test(String(error)),'unexpected throw: '+String(error));return String(error);}throw new Error('expected throw '+pattern);}
export function bounded(promise,ms,label){let timer;return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error(label+' deadline')),ms);})]).finally(()=>clearTimeout(timer));}
export const rowRange=(start,end)=>Array.from({length:end-start},(_,i)=>({n:start+i,label:'v'+(start+i)}));

export class ScheduleBlocked extends Error {constructor(message){super(message);this.name='ScheduleBlocked';}}
export const schedule=(condition,message)=>{if(!condition)throw new ScheduleBlocked(message);};
export function scheduleBounded(promise,ms,label){let timer;return Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new ScheduleBlocked(label+' deadline')),ms);})]).finally(()=>clearTimeout(timer));}
