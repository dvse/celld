import {PROFILE,LIMITS,check,bytes,equal,join,bounded} from './common.js';
import {Lab} from './lab.js';

export async function F001(t) {
  await t.config('unvisited');await t.redirect('manual','unvisited',{prefix:4096,outputN:12289,tailGate:'manual-tail'});
  const r=await t.open('manual','manual',{redirect:'manual'});check(r.status===302&&r.headers.get('location')===t.url('unvisited'),'manual redirect metadata');
  const held=await t.prefix(r,4096);equal(join(held.parts),bytes('manual',4096),'manual body prefix');
  await t.probe();await t.expect('unvisited',{entered:0});await t.wait('manual',o=>o.active&&o.outputBytes===4096,'manual body retained after independent upload commit');
  await t.release('manual-tail');await t.drainHeld(held,'manual');await t.expect('manual');await t.expect('unvisited',{entered:0});
}
export async function F002(t) {
  await t.config('final',{route:'branch/final',query:'?phase=done',headGate:'final-head',outputN:1777});
  await t.redirect('middle','final',{route:'branch/middle',query:'?phase=middle',location:'final?phase=done',outputN:0});
  await t.redirect('start','middle',{route:'origin/start',query:'?phase=start',location:'../branch/middle?phase=middle',outputN:0});
  const chain=t.watch(t.complete('start','final',{redirect:'follow'}));
  await t.wait('final',o=>o.entered===1&&o.inputTerminal==='eof','relative chain reached final query while response held');
  await t.probe();await t.expect('start');await t.expect('middle');await t.release('final-head');await t.success(chain);await t.expect('final');
  const s=await t.snapshot();const names=s.events.filter(e=>e.kind==='entered'&&['start','middle','final'].includes(e.name)).map(e=>e.name);check(names.join(',')==='start,middle,final','exact finite redirect path order');
  const actual=s.ops.find(o=>o.name==='final');check(actual.path==='/root/'+t.root+'/op/branch/final'&&actual.query==='?phase=done','second relative hop used current branch directory, not original origin directory');
}
export async function F003(t) {
  await t.config('result',{headGate:'result-head',outputN:619});
  await t.redirect('submit','result',{method:'POST',inputLabel:'document',inputN:8193,outputN:0});
  const task=t.watch(t.complete('submit','result',{method:'POST',body:bytes('document',8193),headers:{'content-type':'application/octet-stream'},redirect:'follow'}));
  await t.wait('result',o=>o.entered===1&&o.inputTerminal==='eof','POST302 followed as empty GET before result head');
  await t.expect('submit',{method:'POST',inputN:8193});await t.expect('result',{method:'GET',inputN:0});await t.probe();await t.release('result-head');await t.success(task);
}
export async function F004(t) {
  await t.config('final',{headGate:'final-head',outputN:701});
  await t.redirect('get-again','final',{status:307,outputN:0});
  await t.redirect('replace','get-again',{status:303,method:'PUT',inputLabel:'replacement',inputN:7169,outputN:0});
  const task=t.watch(t.complete('replace','final',{method:'PUT',body:bytes('replacement',7169),redirect:'follow'}));
  await t.wait('final',o=>o.entered===1&&o.inputTerminal==='eof','307 after 303 did not restore original PUT or body');
  await t.expect('replace',{method:'PUT',inputN:7169});await t.expect('get-again',{method:'GET',inputN:0});await t.expect('final',{method:'GET',inputN:0});
  await t.probe();await t.release('final-head');await t.success(task);
}
export async function F005(t) {
  await t.config('stored',{method:'PUT',inputLabel:'finite-upload',inputN:16387,commit:true,commitGate:'commit',outputN:89});
  await t.redirect('moved','stored',{status:307,method:'PUT',inputLabel:'finite-upload',inputN:16387,outputN:0});
  const task=t.watch(t.complete('moved','stored',{method:'PUT',body:bytes('finite-upload',16387),headers:{'content-type':'application/octet-stream'},redirect:'follow'}));
  const stored=await t.wait('stored',o=>o.inputTerminal==='eof'&&o.effect===0,'both requests consumed complete finite body before target effect');
  check(stored.contentType==='application/octet-stream','preserved content type');await t.expect('moved',{method:'PUT',inputN:16387});await t.expect('stored',{method:'PUT',inputN:16387});
  await t.probe();await t.release('commit');await t.success(task);await t.expect('stored',{effect:1});
}
export async function F006(t) {
  await t.config('head-final',{method:'HEAD',outputN:32771,headGate:'head-ready'});
  await t.redirect('head-start','head-final',{status:303,method:'HEAD',outputN:19});
  const task=t.watch(t.open('head-start','head-final',{method:'HEAD',redirect:'follow'}));
  await t.wait('head-final',o=>o.entered===1&&o.inputTerminal==='eof','HEAD preserved across303 while final head held');
  await t.probe();await t.release('head-ready');const r=await t.success(task);
  check(r.status===200&&r.headers.get('content-length')==='32771','final HEAD metadata');check((await t.raw(r)).length===0,'HEAD final payload empty');
  const a=await t.expect('head-start',{method:'HEAD'}),b=await t.expect('head-final',{method:'HEAD'});check(a.outputBytes===0&&b.outputBytes===0&&a.outputTerminal==='head'&&b.outputTerminal==='head','neither HEAD endpoint produced payload');
}
export async function F007(t) {
  await t.config('locationless',{status:302,outputN:10241,prefix:4096,tailGate:'tail'});
  const r=await t.open('locationless','locationless',{redirect:'follow'});check(r.status===302&&r.headers.get('location')===null,'missing Location leaves response terminal');
  const held=await t.prefix(r,4096);await t.probe();await t.wait('locationless',o=>o.active&&o.outputBytes===4096,'locationless body remains readable during sibling commit');
  await t.release('tail');await t.drainHeld(held,'locationless');await t.expect('locationless');
  const s=await t.snapshot();check(s.ops.every(o=>o.name==='locationless'||o.name==='probe'),'no fabricated redirect endpoint');
}
export async function F008(t) {
  await t.config('explicit-target',{headGate:'explicit-head',outputN:997});
  await t.redirect('decision','explicit-target',{outputN:12289,prefix:4096,tailGate:'unused-tail'});
  const r=await t.open('decision','decision',{redirect:'manual'}),held=await t.prefix(r,4096);
  check(r.status===302&&r.headers.get('location')===t.url('explicit-target'),'manual handoff target');await t.expect('explicit-target',{entered:0});
  await t.cancelHeld(held);await t.stop('decision'); // Application stop is separate from native reader cancellation.
  const task=t.watch(t.complete('explicit-target','explicit-target',{redirect:'manual'}));
  await t.wait('explicit-target',o=>o.entered===1,'fresh explicit request after cancellation');await t.probe();await t.release('explicit-head');await t.success(task);await t.expect('explicit-target');
}
export async function F009(t) {
  await t.config('never');await t.redirect('middle','never',{headGate:'middle-head',outputN:0});await t.redirect('first','middle',{outputN:0});
  await t.config('peer-final',{outputN:307});await t.redirect('peer-start','peer-final',{outputN:0});
  const controller=t.controller(),reason=new Error('F009 planned intermediate abort');
  const pending=t.watch(t.complete('first','never',{redirect:'follow',signal:controller.signal}));
  await t.wait('middle',o=>o.entered===1&&o.inputTerminal==='eof','first hop complete, intermediate response head withheld');await t.expect('first');
  controller.abort(reason);await t.aborted(pending,reason);await t.stop('middle');
  await t.complete('peer-start','peer-final',{redirect:'follow'});await t.expect('peer-start');await t.expect('peer-final');await t.expect('never',{entered:0});
  await t.wait('middle',o=>!o.active,'stopped intermediate handler settled without exposing Location');
}
export async function F010(t) {
  await t.config('final',{outputLabel:'final-only',outputN:16389,prefix:4096,tailGate:'final-tail'});
  await t.redirect('second','final',{outputLabel:'discard-second',outputN:8193,headGate:'second-head'});
  await t.redirect('first','second',{outputLabel:'discard-first',outputN:6151});
  const pending=t.watch(t.open('first','final',{redirect:'follow'}));
  await t.wait('second',o=>o.entered===1,'first nonempty redirect response discarded before intermediate head');await t.probe();await t.release('second-head');
  const r=await t.success(pending);check(r.status===200,'final status after discarded redirect bodies');const held=await t.prefix(r,4096);equal(join(held.parts),bytes('final-only',4096),'no intermediate-body contamination');
  await t.expect('first');await t.expect('second');await t.wait('final',o=>o.active&&o.outputBytes===4096,'final streaming body has independent held tail');await t.release('final-tail');await t.drainHeld(held,'final');await t.expect('final');
}
export async function F011(t) {
  await t.config('manual-target');await t.config('follow-target',{outputN:811});
  await t.redirect('manual-start','manual-target',{outputN:9217,prefix:4096,tailGate:'manual-tail'});await t.redirect('follow-start','follow-target',{outputN:0});
  const manual=await t.open('manual-start','manual-start',{redirect:'manual'}),held=await t.prefix(manual,4096);
  await t.complete('follow-start','follow-target',{redirect:'follow'});await t.expect('follow-start');await t.expect('follow-target');await t.expect('manual-target',{entered:0});
  await t.wait('manual-start',o=>o.active&&o.outputBytes===4096,'manual response still owned after same-origin follow request completed');
  await t.release('manual-tail');await t.drainHeld(held,'manual-start');check(manual.status===302,'per-call redirect mode did not bleed');await t.expect('manual-target',{entered:0});
}
export async function F012(t) {
  await t.config('direct',{outputN:419});await t.config('destination',{query:'?document=final',headGate:'destination-head',outputN:1237});await t.redirect('origin','destination',{outputN:0});
  const followed=t.watch(t.open('origin','destination',{redirect:'follow'}));await t.wait('destination',o=>o.entered===1,'redirect destination independently witnessed before metadata comparison');
  const direct=await t.complete('direct','direct',{redirect:'follow'});check(direct.url===t.url('direct')&&direct.redirected===false,'direct response metadata control');
  await t.release('destination-head');const r=await t.success(followed);equal(await t.raw(r),bytes('destination',1237),'redirect destination payload');await t.expect('origin');await t.expect('destination');
  check(r.url===t.url('destination','?document=final')&&r.redirected===true,'followed Response.url/redirected must describe final destination');
}

export const CASES={F001,F002,F003,F004,F005,F006,F007,F008,F009,F010,F011,F012};
export const CASE_IDS=Object.keys(CASES);
export async function runCase(input,caller,origin){
  const t=new Lab(input,caller,origin),result={id:input.id,run:input.run,profile:PROFILE,promotion:true,qualification:'correctness-stress-candidate',status:'BLOCKED',phase:'precondition',traceEntered:false,caller};let work,traceOutcome;
  try{await t.init();result.recipient=t.owner;result.traceEntered=true;result.status='FAIL';result.phase='trace';work=(async()=>{await CASES[input.id](t);await t.recovery();})().then(()=>({ok:true}),error=>({ok:false,error}));traceOutcome=await bounded(work,19000,'case trace');if(!traceOutcome.ok)throw traceOutcome.error;result.phase='assertions-complete';}
  catch(error){result.error=String(error);if(result.traceEntered)result.semanticStatus='FAIL';else result.blocker={type:'BLOCKED_PREREQUISITE',detail:String(error)};}
  finally{try{result.cleanup=await bounded(t.cleanup(),4000,'case cleanup');if(work){const settled=await bounded(work,250,'trace settlement');if(!traceOutcome&& !settled.ok)result.lateTraceError=String(settled.error);}}catch(error){result.cleanup={status:'BLOCKED',error:String(error)};result.status='BLOCKED';result.phase='cleanup';result.blocker={type:'BLOCKED_CLEANUP',detail:String(error)};}}
  if(result.phase==='assertions-complete'&&result.cleanup.status==='ok'){result.status='PASS';result.phase='complete';}
  result.evidence={events:t.events,logicalPayloadAllowance:t.logical,maxNetworkRequests:t.maxLive,networkAttempts:t.calls,wallMs:Date.now()-t.started};
  if(result.evidence.wallMs>LIMITS.wallMs){result.status='BLOCKED';result.phase='cleanup';result.blocker={type:'BLOCKED_WALL_ENVELOPE',detail:'active handler exceeded24s evidence envelope'};}
  return result;
}
