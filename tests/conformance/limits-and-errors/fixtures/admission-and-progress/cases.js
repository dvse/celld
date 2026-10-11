import { ok, eq, rejection, chunk, checkBytes, FRAME, TOTAL, MAX_READS } from './fixture.js';
import { loadWorker, ZLIB_CODE } from './workers.js';
const ids=(prefix,n)=>Array.from({length:n},(_,i)=>prefix+i);
const all=values=>Promise.all(values);
const count=(stats,key)=>stats.counts[key]??0;
function once(stats,prefix,names){for(const id of names)eq(count(stats,prefix+id),1,prefix+id+' exactly once');}
function none(stats,prefix,names){for(const id of names)eq(count(stats,prefix+id),0,prefix+id+' absent');}
function fulfilled(rows,names){eq(rows.map(x=>[x.id,x.status,x.value]),names.map(id=>[id,'fulfilled',{id,value:'ok:'+id}]),'fanout exact receipts');}
function streamsDone(receipts){for(const r of receipts)eq(r,{status:'ok',bytes:TOTAL},'exact complete stream');}
async function loaded(s,n=4,source){const entries=ids('worker',n).map(label=>loadWorker(s,label,source));const probes=await all(entries.map(e=>e.probe()));ok(new Set(probes.map(p=>p.token)).size===n,'anonymous worker identities must differ');return {entries,probes};}
async function workersAlive(entries,probes){for(let i=0;i<entries.length;i++)eq(await entries[i].ping('recovery'),{token:probes[i].token,value:'recovery'},'loaded worker identity/liveness');}
// Each body is an authored causal schedule. Loops issue operations within that
// schedule; they never generate counted IDs or inflate the case inventory.
export const cases={
  async B001(s){
    const names=ids('subscriber',6),cb=s.callback({gates:{subscriber0:'slow'}});
    const pending=s.watch(s.peer.broadcast(s.tag,names,cb.stub));await all(names.map(id=>cb.book.wait('callback-enter:'+id)));
    await all(names.slice(1).map(id=>s.wait('effect:'+id)));let before=await s.stats();none(before,'effect:',['subscriber0']);once(before,'effect:',names.slice(1));eq(before.active,1,'only slow subscriber remains');
    await s.healthy();cb.book.release('slow');fulfilled(await pending,names);const after=await s.stats();once(after,'effect:',names);eq(after.maxActive,6,'all fanout jobs overlapped');return {before,after};
  },
  async B002(s){
    const names=ids('subscriber',6),cb=s.callback({gates:Object.fromEntries(names.map(id=>[id,id])),fail:['subscriber2']});
    const pending=s.watch(s.peer.broadcast(s.tag,names,cb.stub));await all(names.map(id=>cb.book.wait('callback-enter:'+id)));eq(cb.target.maxActive,6,'six native callbacks simultaneously pending');
    cb.book.release('subscriber2');await s.wait('settle:subscriber2');const before=await s.stats();none(before,'effect:',names);eq(before.active,5,'failure leaves five blocked siblings');await s.healthy();
    for(const id of names)cb.book.release(id);const rows=await pending;eq(rows.filter(r=>r.status==='rejected').map(r=>r.id),['subscriber2'],'only intended callback fails');ok(rows[2].error.includes('planned:callback:subscriber2'),'intended error');fulfilled(rows.filter(r=>r.status==='fulfilled'),names.filter(x=>x!=='subscriber2'));
    const recovery=['again0','again1'];fulfilled(await s.peer.broadcast(s.tag,recovery,cb.stub),recovery);const after=await s.stats();none(after,'effect:',['subscriber2']);once(after,'settle:',names);once(after,'effect:',recovery);return {before,rows,after};
  },
  async B003(s){
    const names=['held0','held1','held2','reenter0','reenter1','reenter2'];
    const cb=s.callback({gates:{held0:'held',held1:'held',held2:'held'},reenter:async id=>{if(id.startsWith('reenter')){const value=await s.peer.note(s.tag,'nested:'+id);eq(value.owner,await s.peer.inspect(),'callback reentry owner');}}});
    const pending=s.watch(s.peer.broadcast(s.tag,names,cb.stub));await all(names.map(id=>cb.book.wait('callback-enter:'+id)));await all(names.slice(3).map(id=>s.wait('effect:'+id)));
    const before=await s.stats();once(before,'nested:',names.slice(3));none(before,'effect:',names.slice(0,3));eq(before.active,3,'nested requests completed around three held callbacks');
    cb.book.release('held');fulfilled(await pending,names);const after=await s.stats();once(after,'effect:',names);await s.healthy();return {before,after};
  },
  async B004(s){
    const names=ids('tail',6),cb=s.callback({gates:Object.fromEntries(names.map(id=>[id,'drain']))});
    eq(await s.peer.broadcast(s.tag,names,cb.stub,true),{scheduled:6},'background dispatch receipt');await all(names.map(id=>cb.book.wait('callback-enter:'+id)));
    const before=await s.stats();eq(before.active,6,'all detached callbacks outstanding after request returned');eq(count(before,'background-settled'),0,'background unexpectedly completed');await s.healthy();
    cb.book.release('drain');await s.wait('background-settled');const after=await s.stats();once(after,'effect:',names);eq(after.active,0,'background active count drained');fulfilled(after.events.find(e=>e.key==='background-settled').detail,names);return {before,after};
  },
  async B005(s){
    const names=ids('tail',6),cb=s.callback({gates:Object.fromEntries(names.map(id=>[id,id])),fail:['tail0']});await s.peer.broadcast(s.tag,names,cb.stub,true);
    await all(names.map(id=>cb.book.wait('callback-enter:'+id)));cb.book.release('tail0');await s.wait('settle:tail0');
    const foreground=ids('foreground',4);eq(await all(foreground.map(id=>s.peer.work(s.tag,id))),foreground.map(id=>({id,value:'ok:'+id})),'foreground progresses while background has failure and five stalls');
    let before=await s.stats();eq(before.active,5,'five background jobs still held');none(before,'effect:',['tail0']);once(before,'effect:',foreground);
    for(const id of names)cb.book.release(id);await s.wait('background-settled');let after=await s.stats();const rows=after.events.find(e=>e.key==='background-settled').detail;eq(rows.filter(x=>x.status==='rejected').map(x=>x.id),['tail0'],'one detached failure');ok(rows[0].error.includes('planned:callback:tail0'),'detached error marker');once(after,'effect:',names.slice(1));
    await s.healthy();return {before,rows,after};
  },
  async B006(s){
    const names=ids('request',8),pending=names.map((id,i)=>s.watch(s.peer.admit(s.tag,'document',id,i<2?'hold':null)));
    await all(names.map(id=>s.wait('admitted:'+id)));let saturated=await s.stats();eq(saturated.lanes.document.active,2,'admission width');eq(saturated.queued,names.slice(2).sort(),'six queued requests');
    for(const id of ['request3','request6'])eq(await s.peer.cancelQueued(s.tag,id),'cancelled:'+id,'queued cancellation control');
    const errors=await all([rejection(pending[3],'planned:cancel:request3'),rejection(pending[6],'planned:cancel:request6')]);await s.healthy();await s.release('hold');
    const survivors=names.filter(x=>!['request3','request6'].includes(x));eq(await all(survivors.map(id=>pending[names.indexOf(id)])),survivors.map(id=>({id,value:'ok:'+id})),'surviving admitted results');
    eq(await s.peer.admit(s.tag,'document','replacement',null),{id:'replacement',value:'ok:replacement'},'capacity recovers');const after=await s.stats();none(after,'enter:',['request3','request6']);none(after,'effect:',['request3','request6']);once(after,'effect:',[...survivors,'replacement']);eq(after.lanes.document,{active:0,maxActive:2,limit:2,queue:[]},'bounded lane drained');return {saturated,errors,after};
  },
  async B007(s){
    const names=ids('request',6),cb=s.callback({gates:{request0:'fail',request1:'slow'},fail:['request0']});
    const pending=names.map(id=>s.watch(s.peer.admit(s.tag,'document',id,null,cb.stub)));await all(names.map(id=>s.wait('admitted:'+id)));await cb.book.wait('callback-enter:request1');
    cb.book.release('fail');const error=await rejection(pending[0],'planned:callback:request0');eq(await all(pending.slice(2)),names.slice(2).map(id=>({id,value:'ok:'+id})),'queue makes progress on slot released by exception');
    let before=await s.stats();eq(before.lanes.document.active,1,'only slow admitted callback remains');none(before,'effect:',['request0','request1']);once(before,'effect:',names.slice(2));await s.healthy();
    cb.book.release('slow');eq(await pending[1],{id:'request1',value:'ok:request1'},'slow admitted request resumes');const after=await s.stats();eq(after.lanes.document.maxActive,2,'failed job did not leak capacity');once(after,'settle:',names);return {error,before,after};
  },
  async B008(s){
    const blocked=ids('document',6),pending=blocked.map((id,i)=>s.watch(s.peer.admit(s.tag,'documents',id,i<2?'documents-held':null)));await all(blocked.map(id=>s.wait('admitted:'+id)));
    const probes=['git0','git1'];eq(await all(probes.map(id=>s.peer.admit(s.tag,'git',id,null))),probes.map(id=>({id,value:'ok:'+id})),'independent lane progresses with full other lane');
    let before=await s.stats();eq(before.lanes.documents.active,2,'document lane remains occupied');eq(before.lanes.documents.queue,blocked.slice(2),'document backlog remains');once(before,'effect:',probes);none(before,'effect:',blocked);
    await s.release('documents-held');eq(await all(pending),blocked.map(id=>({id,value:'ok:'+id})),'backlogged lane recovers');let after=await s.stats();eq(after.queued,[],'both queues drained');once(after,'effect:',blocked);await s.healthy();return {before,after};
  },
  async B009(s){
    const names=ids('pack',4),streams=await all(names.map((id,i)=>s.download(id,31+i,id))),reads=streams.map((stream,i)=>s.drain(names[i],stream,31+i));
    await all(names.map(id=>s.wait('source-paused:'+id)));await all(names.map(id=>s.local.book.wait('read:'+id)));await s.healthy();
    await s.release('pack3','pack1');streamsDone(await all([reads[3].promise,reads[1].promise]));ok(!reads[0].settled&&!reads[2].settled,'unreleased pack readers finished');
    await s.release('pack0','pack2');streamsDone(await all([reads[0].promise,reads[2].promise]));let after=await s.stats();once(after,'source-close:',names);none(after,'source-cancel:',names);return {receipts:await all(reads.map(r=>r.promise)),after};
  },
  async B010(s){
    const names=ids('upload',6),pending=names.map((id,i)=>s.watch(s.peer.consume(s.tag,id,s.localSource(id,41+i),41+i,'receivers-held')));
    await all(names.map(id=>s.wait('consume-prefix:'+id)));let before=await s.stats();none(before,'consume-effect:',names);ok(before.pending>=6,'six upload receives are outstanding');
    const foreground=['metadata0','metadata1'];eq(await all(foreground.map(id=>s.peer.work(s.tag,id))),foreground.map(id=>({id,value:'ok:'+id})),'metadata survives saturated stream receivers');
    await s.release('receivers-held');eq(await all(pending),names.map(id=>({id,bytes:TOTAL})),'uploads drain exactly');let after=await s.stats();once(after,'consume-effect:',names);none(after,'consume-error:',names);await s.healthy();return {before,after};
  },
  async B011(s){
    const down=ids('download',4),up=ids('upload',4),reads=[];for(let i=0;i<4;i++)reads.push(s.drain(down[i],await s.download(down[i],51+i,down[i]),51+i));
    const uploads=up.map((id,i)=>s.watch(s.peer.consume(s.tag,id,s.localSource(id,61+i,id),61+i)));
    await all(down.map(id=>s.wait('source-paused:'+id)));await all(up.map(id=>s.wait('consume-prefix:'+id)));await all(up.map(id=>s.local.book.wait('source-paused:'+id)));
    let before=await s.stats();none(before,'source-close:',down);none(before,'consume-effect:',up);await s.healthy();
    for(const id of up)s.local.book.release(id);eq(await all(uploads),up.map(id=>({id,bytes:TOTAL})),'upload direction independently unblocks');ok(reads.every(r=>!r.settled),'download direction must remain gated');
    await s.release(...down);streamsDone(await all(reads.map(r=>r.promise)));let after=await s.stats();once(after,'consume-effect:',up);once(after,'source-close:',down);return {before,after};
  },
  async B012(s){
    const names=ids('pack',6),reads=[];for(let i=0;i<6;i++)reads.push(s.drain(names[i],await s.download(names[i],71+i,names[i]),71+i));
    await all(names.map(id=>s.wait('source-paused:'+id)));await all(names.map(id=>s.local.book.wait('read:'+id)));
    await all([s.cancel(reads[1],'planned:cancel:pack1'),s.cancel(reads[4],'planned:cancel:pack4')]);await all(['pack1','pack4'].map(id=>s.wait('source-cancel:'+id)));
    let before=await s.stats();for(const id of ['pack1','pack4']){eq(before.sources[id].cancelled,1,'one producer cancellation');eq(before.sources[id].closed,0,'cancelled source did not close normally');ok(before.sources[id].reason.includes('planned:cancel:'+id),'cancellation reason');ok(before.sources[id].bytes<=FRAME,'cancelled producer emitted beyond gate');}
    await s.healthy();await s.release('pack0','pack2','pack3','pack5');streamsDone(await all([0,2,3,5].map(i=>reads[i].promise)));for(const i of [1,4])eq((await reads[i].promise).status,'cancelled','consumer cancellation terminal');let after=await s.stats();once(after,'source-close:',['pack0','pack2','pack3','pack5']);return {before,after};
  },
  async B013(s){
    const names=ids('pack',6),reads=[];for(let i=0;i<6;i++)reads.push(s.drain(names[i],await s.download(names[i],81+i,names[i],i===2),81+i));
    await all(names.map(id=>s.wait('source-paused:'+id)));await all(names.map(id=>s.local.book.wait('read:'+id)));await s.release('pack2');const failed=await reads[2].promise;
    eq(failed.status,'error','planned producer error');ok(failed.error.includes('ReadableStream received over RPC disconnected prematurely.'),'normalized remote readable failure');ok(failed.bytes>0&&failed.bytes<=FRAME,'observed prefix retained before failure');ok(reads.filter((_,i)=>i!==2).every(r=>!r.settled),'unrelated streams still gated');
    await s.release(...names.filter(x=>x!=='pack2'));streamsDone(await all(reads.filter((_,i)=>i!==2).map(r=>r.promise)));const recovery=s.drain('fresh',await s.download('fresh',99),99);streamsDone([await recovery.promise]);let after=await s.stats();once(after,'source-error:',['pack2']);eq(after.sources.pack2.error,'planned:source:pack2','exact intended producer error');none(after,'source-close:',['pack2']);once(after,'source-close:',[...names.filter(x=>x!=='pack2'),'fresh']);return {failed,after};
  },
  async B014(s){
    const names=ids('upload',6),pending=names.map((id,i)=>s.watch(s.peer.consume(s.tag,id,s.localSource(id,101+i,'source:'+id),101+i,'consumer:'+id,i===3)));
    await all(names.map(id=>s.wait('consume-prefix:'+id)));await s.release('consumer:upload3');const error=await rejection(pending[3],'planned:consumer:upload3');await s.local.book.wait('source-cancel:upload3');
    eq(s.local.sources.get('upload3').cancelled,1,'abandoned upload cancels its source exactly once');ok(s.local.sources.get('upload3').reason.includes('planned:consumer-stop:upload3'),'receiver cancellation reason');
    let before=await s.stats();none(before,'consume-effect:',names);once(before,'consume-error:',['upload3']);await s.healthy();
    for(const id of names.filter(x=>x!=='upload3')){s.local.book.release('source:'+id);await s.release('consumer:'+id);}
    eq(await all(pending.filter((_,i)=>i!==3)),names.filter(x=>x!=='upload3').map(id=>({id,bytes:TOTAL})),'unaffected uploads drain');let after=await s.stats();once(after,'consume-effect:',names.filter(x=>x!=='upload3'));none(after,'consume-effect:',['upload3']);once(after,'consume-settle:',names);return {error,before,after};
  },
  async B015(s){
    const names=ids('sink',4),terminal=[];for(let i=0;i<4;i++){const stream=await s.peer.sink(s.tag,names[i],111+i,names[i],i===0),writer=s.writer(stream);const writes=[0,FRAME,FRAME*2].map(offset=>s.watch(writer.write(chunk(111+i,offset))));terminal.push({writes,close:s.watch(writer.close())});}
    await all(names.map(id=>s.wait('sink-enter:'+id)));let before=await s.stats();none(before,'sink-close:',names);await s.release('sink0');const error=await rejection(terminal[0].close,'planned:sink:sink0');await Promise.allSettled(terminal[0].writes);const lifecycle=await s.writers[0].lifecycle;eq(lifecycle.status,'rejected','writer.closed rejection observed');ok(lifecycle.error.includes('planned:sink:sink0'),'writer.closed preserves intended failure');
    await s.healthy();await s.release('sink1','sink2','sink3');await all(terminal.slice(1).map(async x=>{await all(x.writes);await x.close;}));let after=await s.stats();eq(after.sinks.sink0.bytes,0,'failing sink admits no bytes');eq(after.sinks.sink0.closed,0,'failed sink never reports normal close');once(after,'sink-error:',['sink0']);once(after,'sink-close:',names.slice(1));for(const id of names.slice(1))eq(after.sinks[id].bytes,TOTAL,'complete sink byte count');return {error,before,after,writeAcknowledgmentTiming:'not asserted'};
  },
  async B016(s){
    const names=ids('document',3),fast=[],slow=[];for(let i=0;i<3;i++){const branches=(await s.download(names[i],121+i)).tee();fast.push(s.drain('fast:'+names[i],branches[0],121+i));const reader=branches[1].getReader();s.local.readers.add(reader);s.watch(reader.closed);const first=await reader.read();ok(!first.done,'slow branch has prefix');checkBytes(first.value,121+i,0);slow.push({reader,prefix:first.value.length,seed:121+i});}
    streamsDone(await all(fast.map(x=>x.promise)));let before=await s.stats();once(before,'source-close:',names);none(before,'source-cancel:',names);await s.healthy();
    await all(slow.slice(0,2).map(async(x,i)=>{await x.reader.cancel('planned:slow-branch:'+i);x.reader.releaseLock();s.local.readers.delete(x.reader);}));
    let n=slow[2].prefix,ended=false;for(let reads=1;reads<MAX_READS;reads++){const next=await slow[2].reader.read();if(next.done){ended=true;break;}checkBytes(next.value,slow[2].seed,n);n+=next.value.length;ok(n<=TOTAL,'slow tee byte bound');}ok(ended,'slow tee read-operation bound');eq(n,TOTAL,'resumed tee branch has complete ordered bytes');slow[2].reader.releaseLock();s.local.readers.delete(slow[2].reader);
    const after=await s.stats();none(after,'source-cancel:',names);return {before,after,resumedBytes:n,cancelledBranches:2};
  },
  async B017(s){
    const {entries,probes}=await loaded(s),names=ids('request',8),pending=names.map((id,i)=>s.watch(entries[Math.floor(i/2)].hold(id,'worker:'+Math.floor(i/2))));
    await all(names.map(id=>s.wait('enter:'+id)));let before=await s.stats();eq(before.active,8,'eight outstanding loaded-worker delegates');
    await s.release('worker:1','worker:2','worker:3');const fast=await all(pending.slice(2));for(let i=2;i<8;i++)eq(fast[i-2],{id:names[i],token:probes[Math.floor(i/2)].token,value:{id:names[i],value:'ok:'+names[i]}},'fast worker receipt');
    const held=await s.stats();eq(held.active,2,'one worker remains gated');none(held,'effect:',names.slice(0,2));await workersAlive(entries,probes);
    await s.release('worker:0');const slow=await all(pending.slice(0,2));for(let i=0;i<2;i++)eq(slow[i].token,probes[0].token,'resumed worker identity');let after=await s.stats();once(after,'effect:',names);return {before,held,after,workerTokens:probes.map(x=>x.token)};
  },
  async B018(s){
    const {entries,probes}=await loaded(s),names=ids('request',8),pending=names.map((id,i)=>s.watch(entries[Math.floor(i/2)].hold(id,id,i===2)));
    await all(names.map(id=>s.wait('enter:'+id)));await s.release('request2');const error=await rejection(pending[2],'planned:loaded:request2');let before=await s.stats();once(before,'effect:',['request2']);none(before,'effect:',names.filter(x=>x!=='request2'));eq(before.active,7,'seven unaffected loaded requests still outstanding');
    const recovery=['same-worker-a','same-worker-b'];const values=await all(recovery.map(id=>entries[1].hold(id,null)));for(let i=0;i<values.length;i++)eq(values[i],{id:recovery[i],token:probes[1].token,value:{id:recovery[i],value:'ok:'+recovery[i]}},'same failed worker recovers under sibling load');
    await s.release(...names.filter(x=>x!=='request2'));const survivors=await all(pending.filter((_,i)=>i!==2));for(const value of survivors)eq(value.token,probes[Math.floor(names.indexOf(value.id)/2)].token,'survivor instance unchanged');let after=await s.stats();once(after,'effect:',[...names,...recovery]);once(after,'settle:',names);await workersAlive(entries,probes);return {error,before,after};
  },
  async B019(s){
    const {entries,probes}=await loaded(s),names=ids('document',4),pending=names.map((id,i)=>s.watch(entries[i].upload(id,s.localSource(id,131+i,id,i===1),131+i)));
    await all(names.map(id=>s.wait('upload-prefix:'+id)));await all(names.map(id=>s.local.book.wait('source-paused:'+id)));let before=await s.stats();once(before,'upload-enter:',names);none(before,'upload-effect:',names);
    s.local.book.release('document1');const error=await rejection(pending[1],'ReadableStream received over RPC disconnected prematurely.');eq(await entries[1].ping('recovery'),{token:probes[1].token,value:'recovery'},'failed upload worker remains alive');
    for(const id of names.filter(x=>x!=='document1'))s.local.book.release(id);const values=await all(pending.filter((_,i)=>i!==1));for(const value of values){eq(value.bytes,TOTAL,'successful loaded upload bytes');eq(value.token,probes[names.indexOf(value.id)].token,'upload worker identity');}
    let after=await s.stats();none(after,'upload-effect:',['document1']);once(after,'upload-effect:',names.filter(x=>x!=='document1'));eq(s.local.book.counts['source-error:document1'],1,'one intended source failure');eq(s.local.sources.get('document1').error,'planned:source:document1','exact local source error');await workersAlive(entries,probes);return {error,before,after};
  },
  async B020(s){
    const {entries,probes}=await loaded(s),names=ids('pack',4),notifications=ids('notification',4),cb=s.callback({gates:Object.fromEntries(notifications.map(id=>[id,'notifications']))});
    const fanout=s.watch(s.peer.broadcast(s.tag,notifications,cb.stub));const reads=[];for(let i=0;i<4;i++)reads.push(s.drain(names[i],await entries[i].download(names[i],141+i,names[i]),141+i));
    await all(notifications.map(id=>cb.book.wait('callback-enter:'+id)));await all(names.map(id=>s.wait('enter:worker-stream:'+id)));await all(names.map(id=>s.local.book.wait('read:'+id)));let before=await s.stats();eq(before.active,8,'four stream delegates overlap four callbacks');
    await s.release('pack0','pack2');streamsDone(await all([reads[0].promise,reads[2].promise]));await s.cancel(reads[3],'planned:loaded-cancel:pack3');await s.wait('worker-source-cancel:pack3');await s.release('pack3');await s.wait('settle:worker-stream:pack3');
    await s.release('pack1');streamsDone([await reads[1].promise]);eq((await reads[3].promise).status,'cancelled','loaded stream cancellation');await all(['pack0','pack1','pack2'].map(id=>s.wait('worker-source-close:'+id)));let middle=await s.stats();eq(middle.active,4,'only notification callbacks still held');none(middle,'worker-source-close:',['pack3']);once(middle,'worker-source-cancel:',['pack3']);
    cb.book.release('notifications');fulfilled(await fanout,notifications);let after=await s.stats();once(after,'effect:',notifications);await workersAlive(entries,probes);return {before,middle,after};
  },
  async B021(s){
    const {entries,probes}=await loaded(s),names=ids('background',8),receipts=await all(names.map((id,i)=>s.background(entries[Math.floor(i/2)],id,id)));
    for(let i=0;i<8;i++)eq(receipts[i],{id:names[i],token:probes[Math.floor(i/2)].token,scheduled:true},'background returned bounded dispatch receipt');await all(names.map(id=>s.wait('enter:'+id)));
    let before=await s.stats();eq(before.active,8,'background jobs survive initiating response');none(before,'background-ok:',names);await workersAlive(entries,probes);
    const first=['background0','background2','background4','background6'];await s.release(...first);await all(first.map(id=>s.wait('background-ok:'+id)));const foreground=ids('foreground',4);const values=await all(foreground.map((id,i)=>entries[i].hold(id,null)));for(let i=0;i<4;i++)eq(values[i].token,probes[i].token,'foreground worker unchanged while background remains');
    let middle=await s.stats();eq(middle.active,4,'second background cohort remains gated');once(middle,'effect:',foreground);await s.release(...names.filter(x=>!first.includes(x)));await all(names.map(id=>s.wait('background-ok:'+id)));let after=await s.stats();once(after,'background-ok:',names);none(after,'background-failed:',names);eq(after.active,0,'all bounded background work drained');return {before,middle,after};
  },
  async B022(s){
    const {entries,probes}=await loaded(s),background=ids('tail',4),foreground=ids('foreground',4);await all(background.map((id,i)=>s.background(entries[i],id,id,i===1)));
    const pending=foreground.map((id,i)=>s.watch(entries[i].hold(id,'foreground-held')));await all([...background,...foreground].map(id=>s.wait('enter:'+id)));await s.release('tail1');await s.wait('background-failed:tail1');let before=await s.stats();eq(before.active,7,'one failing background delegate settles independently');
    const failure=before.events.find(e=>e.key==='background-failed:tail1');ok(failure.detail.includes('planned:work:tail1'),'intended background error');none(before,'background-ok:',['tail1']);none(before,'effect:',foreground);
    await s.release('tail0','tail2','tail3');await all(['tail0','tail2','tail3'].map(id=>s.wait('background-ok:'+id)));eq(await entries[1].ping('recovery'),{token:probes[1].token,value:'recovery'},'worker survives rejected waitUntil subtask');
    await s.release('foreground-held');const values=await all(pending);for(let i=0;i<4;i++)eq(values[i].token,probes[i].token,'foreground results retained');let after=await s.stats();once(after,'effect:',[...background,...foreground]);once(after,'background-failed:',['tail1']);none(after,'background-failed:',['tail0','tail2','tail3']);eq(after.active,0,'background failure did not leak active work');return {failure,before,after};
  },
  async B023(s){
    const {entries,probes}=await loaded(s),names=ids('hash',8),pending=names.map((id,i)=>s.watch(entries[Math.floor(i/2)].digest(id,id,17)));
    await all(names.map(id=>s.wait('enter:'+id)));let before=await s.stats();eq(before.active,8,'eight pending digest requests observed at pre-compute audit barriers');await s.healthy();
    const first=[0,2,4,6];await s.release(...first.map(i=>names[i]));const early=await all(first.map(i=>pending[i]));const expected='76cdfa3abecd13b27aa85019f063e95da9ab8f1f729594293411c0a63e15e198';for(const value of early){eq(value.bytes,131072,'bounded native crypto input');eq(value.digest,expected,'independently precomputed SHA-256');eq(value.token,probes[Math.floor(names.indexOf(value.id)/2)].token,'digest owner');}
    let middle=await s.stats();eq(middle.active,4,'unreleased crypto cohort remains pending');none(middle,'digest-effect:',['hash1','hash3','hash5','hash7']);await s.release('hash1','hash3','hash5','hash7');for(const value of await all([1,3,5,7].map(i=>pending[i])))eq(value.digest,expected,'second cohort SHA-256');let after=await s.stats();once(after,'digest-effect:',names);await workersAlive(entries,probes);return {before,middle,after,logicalCryptoInputBytes:1048576};
  },
  async B024(s){
    const {entries,probes}=await loaded(s,4,ZLIB_CODE),names=ids('object',8),notifications=ids('notify',4),cb=s.callback({gates:Object.fromEntries(notifications.map(id=>[id,'notifications']))});
    const fanout=s.watch(s.peer.broadcast(s.tag,notifications,cb.stub));const pending=names.map((id,i)=>s.watch(entries[Math.floor(i/2)].roundtrip(id,'native-work',19)));
    await all(notifications.map(id=>cb.book.wait('callback-enter:'+id)));await all(names.map(id=>s.wait('enter:'+id)));let before=await s.stats();eq(before.active,12,'eight pre-compute audit delegates overlap four callbacks');
    await s.release('native-work');const values=await all(pending);for(const value of values){eq(value.bytes,65536,'bounded native codec output');eq(value.digest,'01e0998ccd387dccb4cb1335e9981d7861ab6402de8965553be8a5fa808bb837','independent restored-byte SHA-256');ok(value.compressed>0&&value.compressed<=65800,'bounded compressed payload');eq(value.token,probes[Math.floor(names.indexOf(value.id)/2)].token,'codec owner identity');}
    let middle=await s.stats();eq(middle.active,4,'codec batch does not require callbacks to drain');once(middle,'zlib-effect:',names);none(middle,'effect:',notifications);await s.healthy();cb.book.release('notifications');fulfilled(await fanout,notifications);await workersAlive(entries,probes);let after=await s.stats();once(after,'effect:',notifications);return {before,middle,after,logicalCodecInputBytes:524288};
  }
};
