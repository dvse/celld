import * as cf from 'cloudflare:workers';
import { RootBase, Scope, PROFILE, requireApi, eq, TOTAL } from './fixture.js';
import { cases } from './cases.js';
import { loadWorker, ZLIB_CODE } from './workers.js';
export class Audit extends cf.WorkerEntrypoint {
  hold(id,gate,fail=false){return this.env.ROOT.getByName(this.ctx.props.root).work(this.ctx.props.tag,id,gate,null,fail);}
  note(key,detail=null){return this.env.ROOT.getByName(this.ctx.props.root).note(this.ctx.props.tag,key,detail);}
}
export class Root extends RootBase {
  async run(id,peerName,requestId) {
    const tag=id+':'+requestId,origin=this.inspect();let owner,peer,s,probe,result,traceEntered=false,setupOperationsEntered=false;
    try {
      requireApi(Object.hasOwn(cases,id),'unknown authored case');requireApi(typeof peerName==='string'&&peerName.length>0,'peer required');
      peer=this.env.ROOT.getByName(peerName);owner=await peer.inspect();requireApi(owner.root!==origin.root&&owner.isolate!==origin.isolate,'distinct caller/provider roots and isolates required');
      for(const p of [this.profile(),await peer.profile()])requireApi(p.modern&&p.rpcStub&&p.dispose&&p.streams,'native RPC, modern parameter lifetimes, streams and disposal required');
      if(Number(id.slice(1))>=17)requireApi(this.profile().loader&&this.profile().waitUntil&&this.profile().crypto,'Worker Loader, waitUntil and native crypto required');
      setupOperationsEntered=true;probe=new Scope(this,peer,tag+':probe',peerName);
      const cb=probe.callback();eq(await peer.work(probe.tag,'callback',null,cb.stub),{id:'callback',value:'ok:callback'},'native callback precondition');
      const stream=await peer.source(probe.tag,'download',13);const d=probe.drain('download',stream,13);eq(await d.promise,{status:'ok',bytes:TOTAL},'native stream result precondition');
      eq(await peer.consume(probe.tag,'upload',probe.localSource('upload',14),14),{id:'upload',bytes:TOTAL},'native stream argument precondition');
      if(Number(id.slice(1))>=17){const entry=loadWorker(probe,'probe',id==='B024'?ZLIB_CODE:undefined),control=await entry.probe();requireApi(typeof control.token==='string'&&(id==='B024'?control.zlib:control.waitUntil&&control.streams&&control.crypto),'real loaded worker positive control unavailable');}
      if(id==='B015'){const sink=await peer.sink(probe.tag,'sink',15),writer=probe.writer(sink);for(let i=0;i<3;i++)await writer.write(Uint8Array.from({length:8192},(_,j)=>(15+(i*8192+j)*17)&255));await writer.close();}
      if(id==='B016')requireApi(typeof ReadableStream.prototype.tee==='function','native stream tee required');
      const setupCleanup=await probe.cleanup();probe=null;s=new Scope(this,peer,tag,peerName);traceEntered=true;
      const evidence=await cases[id](s);result={id,requestId,tag,status:'PASS',phase:'complete',traceEntered,setupOperationsEntered,origin,owner,profile:PROFILE,layer:'real-process-RPC',classification:'bounded-concurrent-stress',evidence,setupCleanup};
    }catch(error){result={id,requestId,tag,status:traceEntered?'FAIL':'BLOCKED',phase:traceEntered?'trace':'precondition',traceEntered,setupOperationsEntered,origin,owner,profile:PROFILE,error:String(error),errorCode:error?.code??null};}
    const cleanup=[];for(const value of [probe,s])if(value){try{cleanup.push(await value.cleanup());}catch(error){cleanup.push({status:'FAIL',error:String(error)});}}
    result.cleanup={status:cleanup.some(x=>x.status==='FAIL')?'FAIL':'ok',details:cleanup};if(result.cleanup.status!=='ok'){result.teardownRequired=true;if(result.status==='PASS'){result.status='FAIL';result.phase='cleanup';}}return result;
  }
}
export default {
  async fetch(request,env){let input;try{const path=new URL(request.url).pathname;if(path==='/health')return Response.json({profile:PROFILE,caseIds:Object.keys(cases),compatibilityDate:'2026-09-04',rpcParamsDupStubs:globalThis.Cloudflare?.compatibilityFlags?.rpc_params_dup_stubs===true});input=await request.json();if(typeof input.root!=='string'||!input.root)throw new Error('root required');const root=env.ROOT.getByName(input.root);if(path==='/identity')return Response.json(await root.inspect());if(path!=='/run'||typeof input.requestId!=='string'||!/^[-a-zA-Z0-9]{16,80}$/.test(input.requestId))throw new Error('dispatch contract');return Response.json(await root.run(input.id,input.peer,input.requestId));}catch(error){return Response.json({id:input?.id,requestId:input?.requestId??null,status:'BLOCKED',phase:'dispatch',traceEntered:false,error:String(error),cleanup:{status:'UNKNOWN'}},{status:503});}}
};
