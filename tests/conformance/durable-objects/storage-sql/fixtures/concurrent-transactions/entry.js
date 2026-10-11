import {RootBase,Scope,Cell} from './fixture.js';
import {PROFILE,eq,ok,ScheduleBlocked} from './common.js';
import {cases} from './cases.js';
export {Cell};
export class Root extends RootBase {
 async run(spec,name){
  const caller=this.identity();let scope,value,failure;const started=Date.now();
  try{ok(!this.used,'fresh coordinator required');this.used=true;ok(Object.hasOwn(cases,spec.id),'unknown case');eq(caller,spec.expectedCaller,'coordinator identity mismatch');ok(spec.primary!==spec.secondary,'distinct recipients required');ok(spec.expectedPrimary.root!==spec.expectedSecondary.root,'distinct recipient identities required');scope=new Scope(this,spec);await scope.setup(name);value=await cases[spec.id](scope);ok(this.book.entered,'actual recipient trace entry missing');}catch(error){failure=error;}
  let cleanup={status:'UNKNOWN',reason:'scope unavailable'};if(scope)try{cleanup=await scope.cleanup();}catch(error){cleanup={status:'FAIL',run:spec.run,error:String(error),externalTeardown:'required'};}
  const entered=this.book?.entered===true,attempted=this.book?.dispatchAttempted===true,unknown=attempted&&!entered;let result;
  if(unknown)result={status:'BLOCKED',phase:'trace-unknown',error:String(failure??'terminal body receipt unavailable'),blocker:{type:'BLOCKED_UNCERTAIN_DISPATCH',detail:'Case dispatch attempted, but no validated body-entry receipt settled'}};
  else if(!entered)result={status:'BLOCKED',phase:'precondition',error:String(failure),blocker:{type:'BLOCKED_PREREQUISITE',detail:String(failure)}};
  else if(cleanup.status!=='ok')result={status:'FAIL',phase:'cleanup',error:String(failure??'fixture cleanup failed')};
  else if(failure instanceof ScheduleBlocked)result={status:'BLOCKED',phase:'trace',error:String(failure),blocker:{type:'BLOCKED_SCHEDULE',detail:failure.message}};
  else if(failure)result={status:'FAIL',phase:'trace',error:String(failure)};
  else result={status:'PASS',phase:'complete',value};
  const receipt={...result,id:spec.id,run:spec.run,profile:PROFILE,caller,recipients:{primary:spec.expectedPrimary,secondary:spec.expectedSecondary},traceEntered:entered,dispatchAttempted:attempted,traceAttempted:this.book?.traceAttempted===true,traceEntryUnknown:unknown,evidence:{events:this.book?.events??[],receipts:scope?.receipts??[],wallMs:Date.now()-started},cleanup,qualification:['T014','T021','T029'].includes(spec.id)?'NONPROMOTING_PINNED_CHARACTERIZATION':'PENDING_EXTERNAL_SUPERVISOR_REVIEW'};this.book=null;return receipt;
 }
}
export default {async fetch(request,env){let body;try{const path=new URL(request.url).pathname;if(path==='/health')return Response.json({profile:PROFILE,caseIds:Object.keys(cases)});body=await request.json();ok(typeof body.name==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(body.name),'bounded root name required');if(path==='/identity'){ok(['caller','recipient'].includes(body.role),'identity role required');return Response.json(await (body.role==='caller'?env.ROOT:env.CELLS).getByName(body.name).identity());}ok(path==='/run'&&typeof body.run==='string'&&/^[a-f0-9]{16}$/.test(body.run),'run dispatch contract');for(const field of ['primary','secondary'])ok(typeof body[field]==='string'&&/^[A-Za-z0-9_-]{1,100}$/.test(body[field]),'bounded recipient name required');return Response.json(await env.ROOT.getByName(body.name).run(body,body.name));}catch(error){return Response.json({id:body?.id,run:body?.run,profile:PROFILE,status:'BLOCKED',phase:'precondition',traceEntered:false,blocker:{type:'BLOCKED_PREREQUISITE',detail:String(error)},cleanup:{status:'UNKNOWN'}},{status:503});}}};
