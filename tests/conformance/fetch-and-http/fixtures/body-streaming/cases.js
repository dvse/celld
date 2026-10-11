import { PROFILE, LIMITS, check, bytes, equal, join, hash, gate, bounded } from './common.js';
import { Lab } from './lab.js';

export async function H001(t) {
  await t.config('source','download',{label:'pack',prefix:4096,tailGate:'tail'});await t.config('sink','upload',{label:'pack'});await t.config('small','upload',{n:701});
  const transfer=t.watch(t.relay('source','sink'));await t.wait('sink',o=>o.inputBytes>=4096,'recipient observed logical prefix while upload remains open');
  await t.upload('small');await t.effect('small');await t.effect('sink',0);await t.release('tail');await t.success(transfer);await t.effect('sink');
}
export async function H002(t) {
  await t.config('download','download',{prefix:8192,tailGate:'tail'});await t.config('upload','upload');
  const held=await t.prefix(await t.open('download'),8192);await t.upload('upload');await t.effect('upload');await t.release('tail');await t.remainder(held,'download');
}
export async function H003(t) {
  await t.config('first','download',{headerGate:'first-ready',contentType:'application/x-git-pack'});await t.config('second','download',{headerGate:'second-ready',contentType:'application/x-blueprint'});await t.config('third','download',{buffered:true});
  const a=t.watch(t.open('first')),b=t.watch(t.open('second'));await t.wait('first',o=>o.entered===1,'first request accepted');await t.wait('second',o=>o.entered===1,'second request accepted');
  await t.download('third');await t.release('second-ready');const br=await t.success(b);check(br.headers.get('content-type')==='application/x-blueprint','second metadata');equal(await t.raw(br),bytes('second'),'second body');
  await t.release('first-ready');const ar=await t.success(a);check(ar.headers.get('content-type')==='application/x-git-pack','first metadata');equal(await t.raw(ar),bytes('first'),'first body');
}
export async function H004(t) {
  await t.config('slow','download',{n:65536,prefix:4096,tailGate:'slow-tail'});await t.config('independent','download',{buffered:true,n:313});
  const slow=await t.open('slow');const held=await t.prefix(slow,4096); // Pause at an observed byte count, not a transport chunk boundary.
  await t.download('independent');const s=await t.snapshot();check(s.ops.some(o=>o.name==='independent'&&o.outputTerminal==='eof'),'independent terminal while caller reader retained');check(s.ops.some(o=>o.name==='slow'&&o.active&&o.outputBytes===4096),'slow HTTP body remains gated');await t.release('slow-tail');await t.remainder(held,'slow');
}
export async function H005(t) {
  await t.config('source','download',{label:'archive',prefix:4096,tailGate:'source-tail'});await t.config('sink','upload',{label:'archive',consumeGate:'sink-resume',prefix:4096});await t.config('probe','download',{buffered:true,n:111});
  const transfer=t.watch(t.relay('source','sink'));await t.wait('sink',o=>o.inputBytes>=4096,'sink has prefix and is application-held');await t.release('source-tail');
  await t.download('probe');await t.effect('sink',0);await t.release('sink-resume');await t.success(transfer);await t.effect('sink');
}
export async function H006(t) {
  await t.config('document','download',{n:49153});await t.config('probe','upload',{n:555});
  const original=await t.open('document'),[left,right]=original.body.tee();t.branches.add(left);t.branches.add(right);
  const fast=t.watch(t.raw(new Response(left)));await t.upload('probe');const delayed=t.watch(t.raw(new Response(right)));equal(await t.success(fast),bytes('document',49153),'first HTTP tee branch');
  equal(await t.success(delayed),bytes('document',49153),'delayed HTTP tee branch');t.branches.delete(left);t.branches.delete(right);t.finish(original);await t.effect('probe');
}
export async function H007(t) {
  await t.config('document','download',{prefix:4096,tailGate:'tail'});await t.config('probe','upload',{n:919});
  const original=await t.open('document'),[left,right]=original.body.tee();t.branches.add(left);t.branches.add(right);const cancel=t.watch(right.cancel('one consumer leaves'));
  const wrapped=new Response(left),held=await t.prefix(wrapped,4096);await t.upload('probe');await t.release('tail');await t.remainder(held,'document');await t.success(cancel);t.branches.delete(left);t.branches.delete(right);t.finish(original);await t.effect('probe');
}
export async function H008(t) {
  await t.config('source','download',{label:'clonebytes',n:12289});await t.config('left','upload',{label:'clonebytes',n:12289,commitGate:'left-commit'});await t.config('right','upload',{label:'clonebytes',n:12289});
  const source=await t.open('source'),request=new Request(t.origin+'/root/'+t.root+'/op/left',{method:'POST',body:source.body}),copy=request.clone();
  const a=t.watch(t.upload('left',request.body));const b=t.watch(t.upload('right',copy.body));await t.success(b);await t.effect('right');await t.effect('left',0);await t.release('left-commit');await t.success(a);t.finish(source);await t.effect('left');
}
export async function H009(t) {
  await t.config('source','download',{label:'rewrapped',prefix:4096,tailGate:'tail'});await t.config('sink','upload',{label:'rewrapped'});await t.config('probe','download',{buffered:true,n:79});
  const source=await t.open('source'),rewrapped=new Response(source.body,{headers:{'content-type':'application/x-blueprint'}});
  const transfer=t.watch(t.upload('sink',rewrapped.body));await t.wait('sink',o=>o.inputBytes>=4096,'rewrapped host body forwarded incrementally');await t.download('probe');await t.release('tail');await t.success(transfer);t.finish(source);await t.effect('sink');
}
export async function H010(t) {
  await t.config('slice','upload',{label:'visible',n:8193,commitGate:'slice-commit'});await t.config('peer','upload',{n:887});
  const backing=new Uint8Array(8209).fill(251);backing.set(bytes('visible',8193),7);const transfer=t.watch(t.upload('slice',backing.subarray(7,8200)));
  await t.wait('slice',o=>o.inputTerminal==='eof','offset-view request consumed');await t.upload('peer');await t.release('slice-commit');await t.success(transfer);await t.effect('slice');await t.effect('peer');
}
export async function H011(t) {
  await t.config('text','download',{label:'invalidutf8',n:16391,contentType:'text/plain; charset=utf-8',headerGate:'text-headers'});await t.config('binary','download',{label:'invalidutf8',n:16391,buffered:true});
  const pending=t.watch(t.open('text'));await t.wait('text',o=>o.entered===1,'text request accepted');await t.download('binary');await t.release('text-headers');
  const response=await t.success(pending);try{const value=await response.text();check(value===new TextDecoder().decode(bytes('invalidutf8',16391)),'HTTP text decoding mismatch');check(response.bodyUsed,'text bodyUsed');}finally{t.finish(response);}
}
export async function H012(t) {
  await t.config('buffered','download',{label:'same',n:24577,buffered:true});await t.config('streamed','download',{label:'same',n:24577,prefix:4096,tailGate:'tail'});
  const stream=await t.open('streamed'),held=await t.prefix(stream,4096);const response=await t.open('buffered');let captured;try{captured=new Uint8Array(await response.arrayBuffer());}finally{t.finish(response);}
  equal(captured,bytes('same',24577),'buffered arrayBuffer');await t.release('tail');equal(await t.remainder(held,'streamed'),captured,'representations equal');
}
export async function H013(t) {
  await t.config('known','download',{n:32771,lengthHeader:true,prefix:4096,tailGate:'known-tail'});await t.config('unknown','download',{n:16387});
  const known=await t.open('known');check(known.headers.get('content-length')==='32771','known body length metadata');const held=await t.prefix(known,4096);
  await t.download('unknown');await t.release('known-tail');await t.remainder(held,'known');
}
export async function H014(t) {
  await t.config('get','download',{label:'screenshot',n:49157,prefix:4096,tailGate:'tail'});await t.config('head','download',{label:'screenshot',n:49157});
  const held=await t.prefix(await t.open('get'),4096),head=await t.open('head',{method:'HEAD'});check(head.status===200&&head.headers.get('content-length')==='49157','HEAD metadata');
  if(head.body)check((await t.raw(head)).length===0,'HEAD must have no payload');else t.finish(head);
  const s=await t.snapshot(),o=s.ops.find(o=>o.name==='head');check(o.outputBytes===0&&o.outputTerminal==='head','HEAD generated no body');await t.release('tail');await t.remainder(held,'get');
}
export async function H015(t) {
  await t.config('receiptless','empty',{n:16384,commitGate:'commit'});await t.config('document','download',{buffered:true,n:599});
  const upload=t.watch(t.upload('receiptless'));await t.wait('receiptless',o=>o.inputTerminal==='eof','upload complete before no-content commit');await t.download('document');await t.effect('receiptless',0);await t.release('commit');await t.success(upload);await t.effect('receiptless');
}
export async function H016(t) {
  await t.config('source','download',{label:'rejectbytes',prefix:4096,tailGate:'source-tail'});await t.config('reject','reject',{label:'rejectbytes'});await t.config('healthy','upload',{n:333});
  const source=await t.open('source');const rejected=t.watch(t.open('reject',{method:'POST',body:source.body}));await t.wait('reject',o=>o.entered===1,'recipient accepted headers before source EOF');
  await t.upload('healthy');await t.release('source-tail');const response=await t.success(rejected);check(response.status===409,'early rejection status');equal(await t.raw(response),bytes('rejection',31),'rejection body');t.finish(source);await t.effect('reject',0);await t.effect('healthy');
}
export async function H017(t) {
  await t.config('never','upload',{n:811});await t.config('live','download',{prefix:4096,tailGate:'tail'});
  const held=await t.prefix(await t.open('live'),4096),controller=t.controller();controller.abort(new Error('pre-dispatch abort'));
  await t.failure(t.watch(t.upload('never',undefined,{signal:controller.signal})),{same:controller.signal.reason,name:'Error',message:'pre-dispatch abort'});const s=await t.snapshot();check(s.ops.find(o=>o.name==='never').entered===0,'aborted request was dispatched');await t.release('tail');await t.remainder(held,'live');await t.effect('never',0);
}
export async function H018(t) {
  await t.config('abort','upload',{n:1231,headerGate:'headers'});await t.config('live','upload',{n:887});const controller=t.controller();
  const waiting=t.watch(t.upload('abort',undefined,{signal:controller.signal}));await t.wait('abort',o=>o.entered===1,'request accepted but response/consumption gated');controller.abort(new Error('cancel held headers'));await t.failure(waiting,{same:controller.signal.reason,name:'Error',message:'cancel held headers'});
  // HTTP disconnect observation is not used as a write-rollback promise: explicitly stop the application before releasing its gate.
  await t.stop('abort');await t.upload('live');await t.effect('abort',0);await t.effect('live');
}
export async function H019(t) {
  await t.config('abandoned','download',{prefix:4096,tailGate:'abandoned-tail'});await t.config('live','download',{prefix:4096,tailGate:'live-tail'});
  const abandoned=await t.prefix(await t.open('abandoned'),4096),live=await t.prefix(await t.open('live'),4096);await t.cancel(abandoned);await t.stop('abandoned');
  await t.release('live-tail');await t.remainder(live,'live');check(join(abandoned.parts).length>=4096,'abandoned observed prefix');
}
export async function H020(t) {
  await t.config('source','download',{label:'earlyerror',errorBefore:true,tailGate:'fail'});await t.config('sink','upload',{label:'earlyerror'});await t.config('healthy','upload',{n:777});
  const transfer=t.watch(t.relay('source','sink'));await t.wait('source',o=>o.entered===1,'source HTTP request entered');await t.upload('healthy');await t.release('fail');await t.failure(transfer);await t.effect('sink',0);await t.effect('healthy');
  const s=await t.snapshot(),src=s.ops.find(o=>o.name==='source');check(src.outputTerminal==='error'&&src.plannedError==='planned HTTP body error'&&src.outputBytes===0,'source zero-byte error witness');
}
export async function H021(t) {
  await t.config('source','download',{label:'lateerror',prefix:4096,tailGate:'fail',errorAfter:true});await t.config('sink','upload',{label:'lateerror'});await t.config('healthy','upload',{n:997});
  const transfer=t.watch(t.relay('source','sink'));await t.wait('sink',o=>o.inputBytes>=4096,'recipient observed prefix before source failure');await t.upload('healthy');await t.release('fail');await t.failure(transfer);await t.effect('sink',0);await t.effect('healthy');
  const s=await t.snapshot();check(s.ops.find(o=>o.name==='source').outputTerminal==='error'&&s.ops.find(o=>o.name==='source').plannedError==='planned HTTP body error','source failure witness');check(s.ops.find(o=>o.name==='sink').inputBytes<32768,'incomplete upload cannot become full bytes');
}
export async function H022(t) {
  await t.config('never','upload',{label:'localerror'});await t.config('live','download',{prefix:4096,tailGate:'tail'});const local=t.localGate();let pulls=0;
  const body=new ReadableStream({async pull(controller){if(pulls++===0)controller.enqueue(bytes('localerror',4096));else{await local.promise;controller.error(new Error('local producer failed before dispatch'));}}},{highWaterMark:0});
  const upload=t.watch(t.upload('never',body));const held=await t.prefix(await t.open('live'),4096);local.resolve();await t.failure(upload,{name:'Error',message:'local producer failed before dispatch'});const s=await t.snapshot();check(s.ops.find(o=>o.name==='never').entered===0,'buffer-fallback failure dispatched partial body');await t.release('tail');await t.remainder(held,'live');await t.effect('never',0);
}
export async function H023(t) {
  await t.config('source','download',{label:'disturbed',n:8192});await t.config('never','upload',{label:'disturbed',n:8192});await t.config('healthy','upload',{n:411});
  const source=await t.open('source'),reader=source.body.getReader();t.readers.add(reader);check(!(await reader.read()).done,'source has data');
  await t.failure(t.watch(t.upload('never',source.body)),{name:'TypeError'});await t.upload('healthy');const s=await t.snapshot();check(s.ops.find(o=>o.name==='never').entered===0,'locked input was dispatched');await t.effect('never',0);await t.effect('healthy');
  await reader.cancel('locked source cleanup');reader.releaseLock();t.readers.delete(reader);t.finish(source);
}
export async function H024(t) {
  await t.config('broken','download',{prefix:4096,tailGate:'fail',errorAfter:true});await t.config('healthy','download',{buffered:true,n:1025});
  const held=await t.prefix(await t.open('broken'),4096);equal(join(held.parts),bytes('broken',4096),'observed pre-error prefix');await t.download('healthy');await t.release('fail');await t.failure(t.watch(t.remainder(held,'broken')));
  const s=await t.snapshot();check(s.ops.find(o=>o.name==='broken').outputTerminal==='error'&&s.ops.find(o=>o.name==='broken').plannedError==='planned HTTP body error','error must not be normal EOF');
}
export async function H025(t) {
  await t.config('left','download',{headerGate:'left-headers'});await t.config('right','download',{headerGate:'right-headers'});await t.config('unrelated','upload',{n:1673});const controller=t.controller();
  const left=t.watch(t.open('left',{signal:controller.signal})),right=t.watch(t.open('right',{signal:controller.signal}));await t.wait('left',o=>o.entered===1,'left caller accepted');await t.wait('right',o=>o.entered===1,'right caller accepted');controller.abort(new Error('one controller cancels two requests'));
  await t.failure(left,{same:controller.signal.reason,name:'Error',message:'one controller cancels two requests'});await t.failure(right,{same:controller.signal.reason,name:'Error',message:'one controller cancels two requests'});await t.stop('left');await t.stop('right');await t.upload('unrelated');await t.effect('unrelated');
}
export async function H026(t) {
  await t.config('committed','upload',{n:6143,replyGate:'reply'});await t.config('peer','upload',{n:919});const controller=t.controller();
  const lost=t.watch(t.upload('committed',undefined,{signal:controller.signal}));await t.wait('committed',o=>o.effect===1,'complete request effect committed before response release');controller.abort(new Error('caller abandons committed response'));await t.failure(lost,{same:controller.signal.reason,name:'Error',message:'caller abandons committed response'});
  await t.upload('peer');await t.effect('peer');await t.effect('committed');await t.release('reply');await t.wait('committed',o=>!o.active,'abandoned handler settles');await t.effect('committed');
}

export const CASES={H001,H002,H003,H004,H005,H006,H007,H008,H009,H010,H011,H012,H013,H014,H015,H016,H017,H018,H019,H020,H021,H022,H023,H024,H025,H026};
export const CASE_IDS=Object.keys(CASES);
export async function runCase(input,caller,origin) {
  const t=new Lab(input,caller,origin);const result={id:input.id,run:input.run,profile:PROFILE,promotion:input.id!=='H022',qualification:input.id==='H022'?'native-buffering-characterization':'contract-candidate',status:'BLOCKED',phase:'precondition',traceEntered:false,caller};
  let work;
  try {await t.init();result.recipient=t.owner;result.traceEntered=true;result.status='FAIL';result.phase='trace';work=(async()=>{await CASES[input.id](t);await t.recovery();})();work.catch(()=>{});await bounded(work,19000,'case trace');result.phase='assertions-complete';}
  catch(error){result.error=String(error);if(!result.traceEntered)result.blocker={type:'BLOCKED_PREREQUISITE',detail:String(error)};}
  finally {try{result.cleanup=await bounded(t.cleanup(),4000,'case cleanup');if(work)await bounded(work.catch(()=>{}),250,'trace settlement');}catch(error){result.cleanup={status:'FAILED',error:String(error)};if(result.traceEntered)result.status='FAIL';}}
  if(result.phase==='assertions-complete'&&result.cleanup.status==='ok'){result.status='PASS';result.phase='complete';}
  result.evidence={events:t.events,logicalPayloadAllowance:t.logical,maxNetworkRequests:t.maxLive,networkAttempts:t.calls,wallMs:Date.now()-t.started};
  if(result.evidence.wallMs>LIMITS.wallMs){result.status='FAIL';result.error='fixture wall budget exceeded';}
  return result;
}
