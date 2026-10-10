export default {fetch(){
 const controller=new AbortController(), signal=controller.signal;
 const owner=(v,k)=>Object.hasOwn(v,k)?v:Object.getPrototypeOf(v);
 const descriptors=[Object.getOwnPropertyDescriptor(owner(controller,'signal'),'signal'),
  Object.getOwnPropertyDescriptor(owner(signal,'aborted'),'aborted'),Object.getOwnPropertyDescriptor(owner(signal,'reason'),'reason')];
 const readonly=descriptors.every(d=>typeof d.get==='function'?d.set===undefined:d.writable===false);
 const forged=descriptors.filter(d=>typeof d.get==='function').every(d=>{try{d.get.call({});return false;}catch{return true;}}) && (()=>{try{AbortSignal.prototype.throwIfAborted.call({});return false;}catch{return true;}})();
 const set=[Reflect.set(controller,'signal',null),Reflect.set(signal,'aborted',false),Reflect.set(signal,'reason','fake')];
 try{controller.abort('real');}catch{}
 let reason;try{signal.throwIfAborted();}catch(e){reason=e;}
 return Response.json({readonly,forged,set,reason,aborted:signal.aborted,same:controller.signal===signal,
 own:[Object.hasOwn(controller,'signal'),Object.hasOwn(signal,'aborted')]});
}};
