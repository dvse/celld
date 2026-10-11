import {DurableObject} from 'cloudflare:workers';
import {cases} from './cases.mjs';
import {scope,bounded,PROFILE} from './fixture.mjs';
import {DATE} from './graphs.mjs';
const ISOLATE=crypto.randomUUID();
export class Root extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.used=false;}
 identity(){return {root:String(this.ctx.id),name:this.ctx.id.name,isolate:ISOLATE};}
 async run(id,requestId){
  let traceEntered=false,result;const s=scope(this,requestId);
  try{
   if(this.used||!this.env.LOADER||!Object.hasOwn(cases,id))throw new Error('precondition: fresh root, Loader binding and known case required');this.used=true;
   await bounded(s.task('setup',()=>s.control()),3000,'real Loader precondition');traceEntered=true;
   const evidence=await bounded(s.task('trace',()=>cases[id](s)),18000,'active graph trace');
   result={status:'PASS',phase:'complete',traceEntered:true,evidence};
  }catch(error){result={status:traceEntered&&!error?.blocked?'FAIL':'BLOCKED',phase:traceEntered?'trace':'precondition',traceEntered,error:String(error)};}
  result.cleanup=await s.cleanup();if(result.cleanup.status!=='ok'){result.status='BLOCKED';result.phase='cleanup';}
  return {...result,id,requestId,profile:PROFILE,compatibilityDate:DATE,origin:this.identity(),layer:'real-process-RPC',overlapBoundary:'one supervisor request; receiver invocation IDs identify active loaded-worker RPCs',qualification:'PENDING_EXTERNAL_OWNED_TEARDOWN_AND_REVIEW'};
 }
}
export default {async fetch(request,env){
 const path=new URL(request.url).pathname;
 if(path==='/health')return Response.json({profile:PROFILE,compatibilityDate:DATE,caseIds:Object.keys(cases),hasLoader:!!env.LOADER});
 if(request.method!=='POST'||!['/run','/identity'].includes(path))return new Response('not found',{status:404});
 const value=await request.json();if(typeof value.root!=='string'||!/^M\d{3}:[a-f0-9-]{36}$/.test(value.root))return Response.json({error:'fresh owned root required'},{status:400});
 const root=env.ROOT.getByName(value.root);if(path==='/identity')return Response.json(await root.identity());
 if(!Object.hasOwn(cases,value.id)||value.root!==value.id+':'+value.requestId)return Response.json({error:'case/request correlation'},{status:400});
 return Response.json(await root.run(value.id,value.requestId));
}};
