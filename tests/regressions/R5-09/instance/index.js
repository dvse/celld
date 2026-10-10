export default {fetch(){
 const c=new AbortController(),s=c.signal;
 const owner=(v,k)=>Object.hasOwn(v,k)?v:Object.getPrototypeOf(v);
 const get=(v,k)=>Object.getOwnPropertyDescriptor(owner(v,k),k);
 const shape=d=>({keys:Object.keys(d).sort(),writable:d.writable??null,enumerable:d.enumerable,configurable:d.configurable,get:typeof d.get,set:typeof d.set});
 const before=[get(c,'signal'),get(s,'aborted'),get(s,'reason')];
 const copied=Object.defineProperties({},Object.fromEntries(['aborted','reason'].map(k=>[k,get(s,k)])));
 const reflect=[Reflect.set(c,'signal',null),Reflect.set(s,'aborted',true),Reflect.set(s,'reason','fake')];
 let strict=false;try{s.aborted=true;}catch(e){strict=e instanceof TypeError;}
 c.abort('real');const after=[get(c,'signal'),get(s,'aborted'),get(s,'reason')];
 const data=before[1].get===undefined;
 let forged=false;try{AbortSignal.prototype.throwIfAborted.call({});}catch(e){forged=e instanceof TypeError;}
 let copy;try{copy=[copied.aborted,copied.reason??null];}catch(e){copy='illegal';}
 return Response.json({before:before.map(shape),after:after.map(shape),
 values:data?[before[0].value===s,before[1].value,before[2].value??null,after[0].value===s,after[1].value,after[2].value]:null,
 copy,reflect,strict,forged,aborted:s.aborted,reason:s.reason,same:c.signal===s,
 own:[Object.hasOwn(c,'signal'),Object.hasOwn(s,'aborted'),Object.hasOwn(s,'reason')]});
}};
