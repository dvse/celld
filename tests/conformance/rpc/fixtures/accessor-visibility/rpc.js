// Ordinary local Workers RPC conformance; no raw network/authentication forgery.
import { RpcTarget, restore } from 'cloudflare:workers';
const ok=(v,m)=>{if(!v)throw new Error(m);};
const eq=(a,b,m)=>ok(JSON.stringify(a)===JSON.stringify(b),m);
const denied=async(fn,label)=>{try{await fn();}catch(e){return String(e);}throw new Error('Expected denial: '+label);};
const dispose=x=>x?.[Symbol.dispose]?.();
const observe=async fn=>{try{return {rejected:false,value:await fn()};}catch(e){return {rejected:true,error:String(e),name:e?.name,remote:e?.remote===true};}};
const visibilityDenied=(result,name)=>result.rejected && result.name==='TypeError' && result.remote &&
  (result.error.includes('The RPC receiver does not implement the method "'+name+'"') || result.error.includes("'"+name+"' is a reserved method and cannot be called over RPC"));
const targetControl=async(x,peer)=>{const v=await x.method();eq(v,{root:(await peer.inspect()).root,value:'private-value'},'target positive/liveness control');};
const aliveAfter=async(peer,before)=>{eq(await peer.publicControl(),'public-control','post-denial liveness');eq(await peer.inspect(),before,'recipient changed after denial');};
class Surface extends RpcTarget {
  #secret='private-value';
  constructor(owner){super();this.owner=owner;this.instanceData='instance-only';this.arrow=()=>{owner.effect('arrow');return 'arrow';};this.bound=this.method.bind(this);}
  method(){return {root:this.owner.inspect().root,value:this.#secret};}
  inherited(){return 'inherited';}
  get exposed(){this.owner.effect('getter');return this.instanceData;}
  get exploding(){this.owner.effect('exploding');throw new Error('getter-rejection');}
  get nested(){return {child:new Child(this.owner,'getter-child')};}
  get functionBox(){return {invoke:()=>this.method()};}
  nestedResult(){return {array:[{child:new Child(this.owner,'method-child')}]};}
  boundResult(){return this.method.bind(this);}
  functionResult(){const f=(x)=>'called:'+x;f.label='own-function-value';return f;}
  privateControl(){return this.#secret;}
  ['#secret'](){return 'explicit-public-name';}
  alarm(){return 'target-alarm';}
  webSocketMessage(){return 'target-websocket';}
}
class DerivedSurface extends Surface {derived(){return 'derived';}}
class StringSurface extends Surface {toString(){return 'explicit-string';}}
class Child extends RpcTarget {
  constructor(owner,label){super();this.owner=owner;this.label=label;}
  identify(){return {...this.owner.inspect(),label:this.label};}
}
class PlainClass {constructor(){this.hidden='must-not-clone';}}
export const extendRoot=Base=>class extends Base {
  constructor(ctx,env){super(ctx,env);this.effects=new Map();this.arrowOnly=()=>{this.effect('do-arrow');return 'must-stay-private';};this.boundOnly=this.publicControl.bind(this);}
  effect(name){this.effects.set(name,(this.effects.get(name)||0)+1);}
  effectCount(name){return this.effects.get(name)||0;}
  publicControl(){this.effect('public');return 'public-control';}
  alarm(){this.effect('alarm');return 'alarm-called';}
  webSocketMessage(){this.effect('websocket');return 'websocket-called';}
  get publicValue(){return 'public-getter';}
  mint(kind){
    if(kind==='derived')return new DerivedSurface(this);
    if(kind==='string')return new StringSurface(this);
    if(kind==='proxy-synthetic')return new Proxy(new Surface(this),{get(target,key,receiver){if(key==='synthetic')return ()=>({...target.owner.inspect(),value:'proxy-synthetic'});return Reflect.get(target,key,receiver);}});
    if(kind==='proxy-own')return new Proxy(new Surface(this),{get(target,key,receiver){if(key==='instanceData'){target.owner.effect('proxy-own-get');return 'leaked';}return Reflect.get(target,key,receiver);}});
    if(kind==='proxy-throw')return new Proxy(new Surface(this),{get(target,key,receiver){if(key==='explode'){target.owner.effect('proxy-throw');throw new Error('proxy-trap-rejection');}return Reflect.get(target,key,receiver);}});
    return new Surface(this);
  }
  plainClass(){this.effect('plain-class-entered');return new PlainClass();}
  plainData(){const out={value:'snapshot',child:{n:1}};this.lastPlain=out;return out;}
  mutatePlain(){this.lastPlain.value='changed';this.lastPlain.child.n=2;}
  rejectBeforeTarget(){throw new Error('rejected-before-capability');}
  thenableResult(){return {then(resolve){resolve({value:'assimilated'});}};}
  async storeTransient(target){this.effect('storage-put-entered');await this.ctx.storage.put('transient-probe',target);return 'unexpected-store';}
  async storageControl(){await this.ctx.storage.put('storage-control',{value:'roundtrip'});const result=await this.ctx.storage.get('storage-control');await this.ctx.storage.delete('storage-control');return result;}
  async storedTransientExists(){return (await this.ctx.storage.get('transient-probe'))!==undefined;}
  async clearTransient(){await this.ctx.storage.delete('transient-probe');}
  persistent(label){return this.ctx.restore({label});}
  [restore](params){return new Child(this,params.label);}
};
export const rpcCases={
  async R001({peer}){const identity=await peer.inspect();eq(await peer.publicControl(),'public-control','positive method');const before=await peer.effectCount('do-arrow');const observed=await observe(()=>peer.arrowOnly());const after=await peer.effectCount('do-arrow');await aliveAfter(peer,identity);ok(visibilityDenied(observed,'arrowOnly') && after===before,'DO own arrow visibility: '+JSON.stringify({observed,before,after,identity}));return {observed,before,after,identity};},
  async R002({peer}){const identity=await peer.inspect();eq(await peer.publicControl(),'public-control','positive method');const before=[await peer.effectCount('alarm'),await peer.effectCount('websocket')];const observed=[await observe(()=>peer.alarm()),await observe(()=>peer.webSocketMessage('data'))];const after=[await peer.effectCount('alarm'),await peer.effectCount('websocket')];await aliveAfter(peer,identity);ok(visibilityDenied(observed[0],'alarm') && visibilityDenied(observed[1],'webSocketMessage') && JSON.stringify(before)===JSON.stringify(after),'DO lifecycle visibility: '+JSON.stringify({observed,before,after,identity}));return {observed,before,after,identity};},
  async R003({peer}){const identity=await peer.inspect(),controlBefore=await peer.effectCount('public');eq(await peer.publicControl(),'public-control','bound positive control');const before=await peer.effectCount('public');eq(before,controlBefore+1,'public control counter');const observed=await observe(()=>peer.boundOnly());const after=await peer.effectCount('public');await aliveAfter(peer,identity);ok(visibilityDenied(observed,'boundOnly') && after===before,'DO bound field visibility: '+JSON.stringify({observed,before,after,identity}));return {observed,before,after,identity};},
  async R004({peer}){const x=await peer.mint('derived');try{eq([await x.inherited(),await x.derived()],['inherited','derived'],'inherited prototype methods');const value=await x.method();eq(value.root,(await peer.inspect()).root,'inherited method owner');eq(value.value,'private-value','inherited private receiver');return value;}finally{dispose(x);}},
  async R005({peer}){eq(await peer.publicValue,'public-getter','DO public getter absent');return {value:'public-getter'};},
  async R006({peer}){const x=await peer.mint();try{await targetControl(x,peer);eq(await x.exposed,'instance-only','explicit getter');const observed=await observe(()=>x.instanceData);await targetControl(x,peer);ok(visibilityDenied(observed,'instanceData'),'wrong own-data rejection: '+JSON.stringify(observed));return {observed};}finally{dispose(x);}},
  async R007({peer}){const x=await peer.mint();const n=await peer.effectCount('arrow');try{await targetControl(x,peer);const observed=await observe(()=>x.arrow());const after=await peer.effectCount('arrow');await targetControl(x,peer);ok(visibilityDenied(observed,'arrow') && after===n,'wrong arrow rejection: '+JSON.stringify({observed,before:n,after}));return {observed};}finally{dispose(x);}},
  async R008({peer}){const x=await peer.mint();try{eq(await x.privateControl(),'private-value','private field receiver');eq(await x['#secret'](),'explicit-public-name','public spelling conflated with private field');return {privateReachableOnlyThroughPublicMethod:true};}finally{dispose(x);}},
  async R009({peer}){const x=await peer.mint();try{await x.method();return {error:await denied(()=>x.constructor,'RpcTarget constructor property')};}finally{dispose(x);}},
  async R010({peer}){const x=await peer.mint();try{await targetControl(x,peer);const observed=[await observe(()=>x.hasOwnProperty('owner')),await observe(()=>x.valueOf())];await targetControl(x,peer);ok(visibilityDenied(observed[0],'hasOwnProperty') && visibilityDenied(observed[1],'valueOf'),'wrong Object.prototype rejection: '+JSON.stringify(observed));return {observed};}finally{dispose(x);}},
  async R011({peer}){const x=await peer.mint('string');try{eq(await x.toString(),'explicit-string','explicit override hidden');return {value:'explicit-string'};}finally{dispose(x);}},
  async R012({peer}){const x=await peer.mint();const n=await peer.effectCount('getter');try{const property=x.exposed;eq(await peer.effectCount('getter'),n,'property access eagerly fetched');eq(await property,'instance-only','getter result');eq(await property,'instance-only','repeat await');eq(await peer.effectCount('getter'),n+2,'RpcProperty repeated await must refetch');return {getterDelta:2};}finally{dispose(x);}},
  async R013({peer}){const x=await peer.mint();const n=await peer.effectCount('exploding');try{const error=await denied(()=>x.exploding,'throwing getter');ok(error.includes('getter-rejection'),'getter error lost');eq(await peer.effectCount('exploding'),n+1,'getter not called exactly once');return {error};}finally{dispose(x);}},
  async R014({peer}){const x=await peer.mint();try{const identity=await x.nested.child.identify();eq(identity.root,(await peer.inspect()).root,'getter child owner');eq(identity.label,'getter-child','getter child label');return identity;}finally{dispose(x);}},
  async R015({peer}){const x=await peer.mint();let value;try{value=await x.nestedResult();const identity=await value.array[0].child.identify();eq(identity.root,(await peer.inspect()).root,'nested result recipient');eq(identity.label,'method-child','nested result label');return identity;}finally{dispose(value);dispose(x);}},
  async R016({peer}){const x=await peer.mint();try{const result=await x.functionBox.invoke();eq(result.root,(await peer.inspect()).root,'getter nested function bound owner');eq(result.value,'private-value','nested function result');return result;}finally{dispose(x);}},
  async R017({peer}){const x=await peer.mint();let f;try{f=await x.boundResult();const result=await f();eq(result.root,(await peer.inspect()).root,'bound function receiver');eq(result.value,'private-value','bound private receiver');return result;}finally{dispose(f);dispose(x);}},
  async R018({peer}){const x=await peer.mint();let f;try{f=await x.functionResult();eq(await f.label,'own-function-value','function own property missing');eq(await f('arg'),'called:arg','callable function');return {label:'own-function-value'};}finally{dispose(f);dispose(x);}},
  async R019({peer}){const x=await peer.mint();let f;try{f=await x.functionResult();eq(await f('control'),'called:control','function positive control');return {error:await denied(()=>f.apply(null,['bad']),'Function.prototype apply')};}finally{dispose(f);dispose(x);}},
  async R020({peer}){const x=await peer.mint('proxy-synthetic');try{const value=await x.synthetic();eq(value.root,(await peer.inspect()).root,'Proxy target receiver');eq(value.value,'proxy-synthetic','synthetic method missing');return value;}finally{dispose(x);}},
  async R021({peer}){const x=await peer.mint('proxy-own');const before=await peer.effectCount('proxy-own-get');try{const error=await denied(()=>x.instanceData,'Proxy own property');eq(await peer.effectCount('proxy-own-get'),before,'denied own get trap ran');return {error};}finally{dispose(x);}},
  async R022({peer}){const x=await peer.mint('proxy-throw');const before=await peer.effectCount('proxy-throw');try{const error=await denied(()=>x.explode(),'Proxy get trap');ok(error.includes('proxy-trap-rejection'),'Proxy trap exception lost');eq(await peer.effectCount('proxy-throw'),before+1,'Proxy trap invoked twice');return {error};}finally{dispose(x);}},
  async R023({peer}){eq(await peer.thenableResult(),{value:'assimilated'},'returned thenable assimilation');return {value:'assimilated'};},
  async R024({peer}){const x=await peer.mint();try{eq([await x.alarm(),await x.webSocketMessage()],['target-alarm','target-websocket'],'RpcTarget lifecycle names wrongly blocked');return {legalRpcTargetNames:true};}finally{dispose(x);}},
  async R025({peer}){const identity=await peer.inspect(),before=await peer.effectCount('plain-class-entered');const observed=await observe(()=>peer.plainClass());const after=await peer.effectCount('plain-class-entered');await aliveAfter(peer,identity);ok(observed.rejected && observed.name==='DataCloneError' && after===before+1,'wrong ordinary-class clone rejection: '+JSON.stringify({observed,before,after}));return {observed,before,after};},
  async R026({peer}){const value=await peer.plainData();await peer.mutatePlain();eq(value,{value:'snapshot',child:{n:1}},'plain object was not by-value snapshot');return value;},
  async R027({peer}){ok(!(await peer.storedTransientExists()),'precondition: probe key dirty');eq(await peer.storageControl(),{value:'roundtrip'},'storage positive control');const x=await peer.mint(),before=await peer.effectCount('storage-put-entered');try{const observed=await observe(()=>peer.storeTransient(x));const after=await peer.effectCount('storage-put-entered');ok(observed.rejected && observed.name==='DataCloneError' && observed.error.includes('transient RPC') && after===before+1,'wrong persistence rejection: '+JSON.stringify({observed,before,after}));ok(!(await peer.storedTransientExists()),'failed persistence left row');await targetControl(x,peer);eq(await peer.storageControl(),{value:'roundtrip'},'storage post-failure control');return {observed,before,after};}finally{await peer.clearTransient();dispose(x);}},
  async R028({peer}){const owner=await peer.inspect();const x=await peer.persistent('caller-controlled-label');try{const identity=await x.identify();eq(identity.root,owner.root,'restore provenance replaced by caller context');eq(identity.isolate,owner.isolate,'restore owner isolate changed');eq(identity.label,'caller-controlled-label','restore parameter lost');return identity;}finally{dispose(x);}}
};
