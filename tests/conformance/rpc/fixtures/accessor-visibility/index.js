// Two new ordinary DO accessor-method traces. Base pilot copied byte-for-byte.
import baseFetch, { Root as PilotRoot } from './base-index.js';
const check=(value,message)=>{if(!value)throw new Error(message);};
const equal=(a,b,message)=>check(JSON.stringify(a)===JSON.stringify(b),message);
const observe=async fn=>{try{return {rejected:false,value:await fn()};}catch(error){return {rejected:true,name:error?.name,remote:error?.remote===true,error:String(error)};}};
export class Root extends PilotRoot {
  constructor(ctx,env){
    super(ctx,env);
    Object.defineProperty(this,'ownCallableAccessor',{get(){
      this.effect('own-accessor-get');
      return ()=>{this.effect('own-accessor-call');return 'hidden-own-callable';};
    }});
  }
  scheduled(){this.effect('scheduled-rpc');return {...this.inspect(),value:'ordinary-scheduled-method'};}
  get inheritedCallableAccessor(){
    this.effect('prototype-accessor-get');const owner=this;
    return function(value){
      check(this===owner,'prototype accessor callable lost receiver');
      this.effect('prototype-accessor-call');return {...this.inspect(),value};
    };
  }
  async run(id,peerName){
    if(!Object.hasOwn(accessorCases,id))return super.run(id,peerName);
    const peer=this.env.ROOT.getByName(peerName),origin=this.inspect();let owner,phase='precondition',traceEntered=false;
    try {
      owner=await peer.inspect();check(origin.isolate!==owner.isolate,'cross-isolate prerequisite');
      phase='trace';traceEntered=true;const evidence=await accessorCases[id]({peer,owner});
      return {id,status:'PASS',phase:'complete',traceEntered,origin,owner,evidence,cleanup:{status:'ok'}};
    }catch(error){return {id,status:traceEntered?'FAIL':'BLOCKED',phase,traceEntered,origin,owner,error:String(error),cleanup:{status:'ok'}};}
  }
}
const accessorCases={
  async V001({peer,owner}){
    equal(await peer.publicControl(),'public-control','positive public method');
    const before=[await peer.effectCount('own-accessor-get'),await peer.effectCount('own-accessor-call')];
    const observed=await observe(()=>peer.ownCallableAccessor());
    const after=[await peer.effectCount('own-accessor-get'),await peer.effectCount('own-accessor-call')];
    equal(await peer.publicControl(),'public-control','post-denial liveness');equal(await peer.inspect(),owner,'recipient changed');
    const intended=observed.rejected && observed.name==='TypeError' && observed.remote && observed.error.includes('The RPC receiver does not implement the method "ownCallableAccessor"');
    check(intended && JSON.stringify(before)===JSON.stringify(after),'DO own accessor visibility: '+JSON.stringify({observed,before,after}));
    return {observed,before,after,recipientUnchanged:true};
  },
  async V002({peer,owner}){
    const before=[await peer.effectCount('prototype-accessor-get'),await peer.effectCount('prototype-accessor-call')];
    const first=await peer.inheritedCallableAccessor('first-call');
    const second=await peer.inheritedCallableAccessor('second-call');
    equal(first,{...owner,value:'first-call'},'first callable-getter recipient/result');
    equal(second,{...owner,value:'second-call'},'second callable-getter recipient/result');
    const after=[await peer.effectCount('prototype-accessor-get'),await peer.effectCount('prototype-accessor-call')];
    equal(after,[before[0]+2,before[1]+2],'getter/call counts');
    equal(await peer.publicControl(),'public-control','post-call liveness');equal(await peer.inspect(),owner,'recipient changed');
    return {before,after,first,second,receiverPreserved:true};
  },
  async V003({peer,owner}){
    equal(await peer.publicControl(),'public-control','scheduled positive control');const before=await peer.effectCount('scheduled-rpc');
    const value=await peer.scheduled();equal(value,{...owner,value:'ordinary-scheduled-method'},'scheduled RPC recipient/result');
    const after=await peer.effectCount('scheduled-rpc');equal(after,before+1,'scheduled method call count');
    equal(await peer.publicControl(),'public-control','post-scheduled liveness');equal(await peer.inspect(),owner,'scheduled recipient changed');
    return {before,after,value,recipientUnchanged:true};
  }
};
export default baseFetch;
