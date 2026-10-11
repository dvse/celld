// Individually authored native RPC lifecycle traces. No stream or RPC mocks.
import { DurableObject } from 'cloudflare:workers';
import { extendRoot, rpcCases } from './rpc.js';
const ISOLATE = crypto.randomUUID();
const delay = ms => new Promise(r => setTimeout(r, ms));
const check = (value, why) => { if (!value) throw new Error(why); };
const equal = (a, b, why) => check(JSON.stringify(a) === JSON.stringify(b), why + ': ' + JSON.stringify(a));
async function drain(stream) {
  const reader = stream.getReader(); const bytes = [];
  try { for (let reads=0;reads<64;reads++) { const r = await reader.read(); if (r.done) return bytes; check(bytes.length+r.value.length<=1048576,'fixture byte bound exceeded'); bytes.push(...r.value); } throw new Error('fixture read-count bound exceeded'); }
  finally { reader.releaseLock(); }
}
async function rejects(promise, why) {
  try { await promise; } catch (e) { return String(e); }
  throw new Error('expected rejection: ' + why);
}
class StreamRoot extends DurableObject {
  constructor(ctx, env) { super(ctx, env); this.items = new Map(); }
  inspect() { return { isolate: ISOLATE, root: String(this.ctx.id) }; }
  readable(tag, plan) {
    const state = { pulls: 0, sent: 0, closed: 0, cancelled: 0, reason: null, pullPending: false, failures: 0, failure: null }; let i = 0, resumePull;
    const stream = new ReadableStream({
      async pull(c) {
        state.pulls++; if (plan.hold) {state.pullPending=true;await new Promise(resolve=>{resumePull=resolve;});state.pullPending=false;if(state.cancelled)return;} if (plan.delay) await delay(plan.delay);
        if (plan.failAt === i) {state.failures++;state.failure='source-failure';throw new Error('source-failure');}
        if (i === plan.chunks.length) { state.closed++; c.close(); return; }
        const bytes = Uint8Array.from(plan.chunks[i++]); state.sent++;
        if (plan.offset) { const backing = new Uint8Array(bytes.length + 6).fill(251); backing.set(bytes, 3); c.enqueue(backing.subarray(3, 3 + bytes.length)); }
        else c.enqueue(bytes);
      },
      cancel(reason) { state.cancelled++; state.reason = reason; resumePull?.(); }
    }, { highWaterMark: 0 });
    this.items.set(tag, { stream, state }); return stream;
  }
  writable(tag, plan) {
    const state = { writes: [], events: [], active: 0, maxActive: 0, closed: 0, aborted: 0 };
    const stream = new WritableStream({
      async write(value) {
        const index = state.writes.length; state.writes.push(Array.from(value)); state.events.push('start:' + index);
        state.maxActive = Math.max(state.maxActive, ++state.active);
        try { if (plan.delay) await delay(plan.delay); if (plan.failAt === index) throw new Error('sink-failure'); }
        finally { state.active--; state.events.push('end:' + index); }
      },
      close() { state.events.push('close'); state.closed++; if (plan.failClose) throw new Error('close-failure'); },
      abort() { state.events.push('abort'); state.aborted++; }
    });
    this.items.set(tag, { stream, state }); return stream;
  }
  stats(tag) { const x = this.items.get(tag); check(x, 'missing fixture state'); return { ...x.state, locked: x.stream.locked }; }
  forget(tag) { const x = this.items.get(tag); check(!x || !x.stream.locked, 'cannot forget locked stream'); this.items.delete(tag); }
  async settle(tag) {
    for (let n = 0; n < 100; n++) { const s = this.stats(tag); if (!s.locked) return s; await delay(10); }
    throw new Error('origin lock still held at terminal state');
  }
  async run(id, peerName) {
    const peer=this.env.ROOT.getByName(peerName),origin=this.inspect(),tag=id+':'+crypto.randomUUID();
    let owner,phase='precondition',traceEntered=false,result;
    try {
      owner=await peer.inspect();
      check(origin.isolate!==owner.isolate,'roots must be in distinct isolates');
      check(Object.hasOwn(cases,id),'unknown case');
      phase='trace';traceEntered=true;
      const evidence=await cases[id]({peer,tag});
      result={id,status:'PASS',phase:'complete',origin,owner,evidence,traceEntered};
    } catch(error) {
      result={id,status:traceEntered?'FAIL':'BLOCKED',phase,origin,owner,error:String(error),traceEntered};
    }
    try {await peer.forget(tag);result.cleanup={status:'ok'};}
    catch(error) {result.cleanup={status:'FAIL',error:String(error)};if(result.status==='PASS'){result.status='FAIL';result.phase='cleanup';}}
    return result;
  }

}
export class Root extends extendRoot(StreamRoot) {}
const cases = {
  ...rpcCases,
  async S001({peer, tag}) {
    const r = (await peer.readable(tag, {chunks: []})).getReader();
    try { check((await r.read()).done, 'empty EOF missing'); check((await r.read()).done, 'repeated EOF unstable'); }
    finally { r.releaseLock(); }
    const s = await peer.settle(tag); equal([s.sent,s.closed,s.cancelled], [0,1,0], 'empty terminal counters'); return s;
  },
  async S002({peer, tag}) {
    const stream = await peer.readable(tag, {chunks: [[1],[2]]}); await stream.cancel({code: 'unread'});
    const s = await peer.settle(tag); check(s.cancelled === 1 && s.reason.code === 'unread', 'unread cancel lost'); check(s.sent <= 1, 'unread over-prefetch'); return s;
  },
  async S003({peer, tag}) {
    const r = (await peer.readable(tag, {chunks: [[3]]})).getReader();
    try { equal(Array.from((await r.read()).value), [3], 'payload'); check((await r.read()).done, 'EOF'); await r.cancel('late'); }
    finally { r.releaseLock(); }
    const s = await peer.settle(tag); check(s.closed === 1 && s.cancelled === 0, 'cancel reopened closed source'); return s;
  },
  async S004({peer, tag}) {
    const bytes = await drain(await peer.readable(tag, {chunks: [[],[4,5],[],[6],[]]})); equal(bytes,[4,5,6],'zero-length chunks truncate or invent bytes');
    const s = await peer.settle(tag); check(s.closed === 1, 'missing close'); return {bytes,stats:s};
  },
  async S005({peer, tag}) {
    const bytes = await drain(await peer.readable(tag, {chunks:[[0,255,7]],offset:true})); equal(bytes,[0,255,7],'subarray leaked backing bytes'); return {bytes,stats:await peer.settle(tag)};
  },
  async S006({peer, tag}) {
    const r = (await peer.readable(tag,{chunks:[[8]],failAt:0})).getReader();
    let error; try { error = await rejects(r.read(),'error before data'); await rejects(r.read(),'stable error'); } finally {r.releaseLock();}
    const s = await peer.settle(tag); check(error.includes('disconnected prematurely'),'wrong readable error category');check(s.sent===0 && s.closed===0 && s.failures===1 && s.failure==='source-failure' && s.pulls===1,'wrong source error witness'); return {error,stats:s};
  },
  async S007({peer, tag}) {
    const r = (await peer.readable(tag,{chunks:[[9,10],[11]],failAt:1})).getReader();
    let error; try {equal(Array.from((await r.read()).value),[9,10],'prefix corrupted'); error = await rejects(r.read(),'error after prefix');} finally {r.releaseLock();}
    const s = await peer.settle(tag); check(error.includes('disconnected prematurely'),'wrong readable error category');check(s.sent===1 && s.closed===0 && s.failures===1 && s.failure==='source-failure' && s.pulls===2,'wrong source error prefix witness'); return {error,stats:s};
  },
  async S008({peer, tag}) {
    const stream = await peer.readable(tag,{chunks:[[12],[13]]}); const first=stream.getReader(); equal(Array.from((await first.read()).value),[12],'first'); first.releaseLock();
    equal(await drain(stream),[13],'reacquired reader skipped/duplicated'); return await peer.settle(tag);
  },
  async S009({peer, tag}) {
    const r = (await peer.readable(tag,{chunks:[[14],[15],[16]],delay:5})).getReader();
    try {const results=await Promise.all([r.read(),r.read(),r.read(),r.read()]); equal(results.slice(0,3).map(x=>Array.from(x.value)),[[14],[15],[16]],'pending read order'); check(results[3].done,'queued EOF');}
    finally {r.releaseLock();} return await peer.settle(tag);
  },
  async S010({peer, tag}) {
    const stream=await peer.readable(tag,{chunks:[[17],[18]],hold:true}); const r=stream.getReader();
    let entered;
    try {const pending=r.read();for(let n=0;n<100;n++){entered=await peer.stats(tag);if(entered.pullPending)break;await delay(10);}check(entered.pullPending,'source pull never reached explicit barrier');await r.cancel('pending');check((await pending).done,'pending read not terminated by cancel');} finally {r.releaseLock();}
    const s=await peer.settle(tag);check(s.cancelled===1,'pending cancellation count');return {entered,stats:s};
  },
  async S011({peer, tag}) {
    const r=(await peer.readable(tag,{chunks:[[19,20,21]]})).getReader({mode:'byob'}); const bytes=[];
    try {for(let n=0;n<3;n++){const v=await r.read(new Uint8Array(1));check(!v.done && v.value.length===1,'single byte BYOB');bytes.push(v.value[0]);}check((await r.read(new Uint8Array(1))).done,'BYOB EOF');}
    finally {r.releaseLock();} equal(bytes,[19,20,21],'BYOB residual bytes'); return await peer.settle(tag);
  },
  async S012({peer, tag}) {
    const r=(await peer.readable(tag,{chunks:[[22,23,24]]})).getReader({mode:'byob'}); let bytes;
    try {const backing=new Uint8Array(12).fill(249);const v=await r.read(backing.subarray(4,9));bytes=Array.from(v.value); equal(bytes,[22,23,24],'offset BYOB data');check(v.value.byteOffset===4,'BYOB offset lost');check((await r.read(new Uint8Array(2))).done,'offset EOF');}
    finally {r.releaseLock();} return {bytes,stats:await peer.settle(tag)};
  },
  async S013({peer, tag}) {
    const stream=await peer.readable(tag,{chunks:[[25],[26,27]]});const r=stream.getReader({mode:'byob'});const bytes=[];
    try {let done=false;for(let reads=0;reads<64;reads++){const v=await r.read(new Uint8Array(8));if(v.done){done=true;break;}bytes.push(...v.value);}check(done,'BYOB read-count bound exceeded');}finally {r.releaseLock();}
    equal(bytes,[25,26,27],'BYOB chunk transition');return await peer.settle(tag);
  },
  async S014({peer, tag}) {
    const r=(await peer.readable(tag,{chunks:[]})).getReader({mode:'byob'});
    try {const v=await r.read(new Uint8Array(4));check(v.done && v.value.byteLength===0,'empty BYOB EOF shape');}finally {r.releaseLock();}return await peer.settle(tag);
  },
  async S015({peer, tag}) {
    const stream=await peer.readable(tag,{chunks:[[28],[29]]});const bytes=[];await stream.pipeTo(new WritableStream({write(v){bytes.push(...v);}}));equal(bytes,[28,29],'pipeTo transfer');return await peer.settle(tag);
  },
  async S016({peer, tag}) {
    const stream=await peer.readable(tag,{chunks:[[30],[31],[32]]});await rejects(stream.pipeTo(new WritableStream({write(){throw new Error('local sink stop');}})),'pipeTo sink failure');
    const s=await peer.settle(tag);check(s.cancelled===1,'pipeTo failed sink did not cancel source');return s;
  },
  async S017({peer, tag}) {
    const [a,b]=(await peer.readable(tag,{chunks:[[33],[34,35]]})).tee();const values=await Promise.all([drain(a),drain(b)]);equal(values,[[33,34,35],[33,34,35]],'tee branches diverged');return await peer.settle(tag);
  },
  async S018({peer, tag}) {
    const [a,b]=(await peer.readable(tag,{chunks:[[36],[37]]})).tee();const cancel=a.cancel('branch A');equal(await drain(b),[36,37],'one tee cancellation killed sibling');await cancel;
    const s=await peer.settle(tag);check(s.cancelled===0 && s.closed===1,'tee canceled source with live branch');return s;
  },
  async S019({peer, tag}) {
    const w=(await peer.writable(tag,{})).getWriter();try{await w.close();await w.closed;}finally{w.releaseLock();}const s=await peer.settle(tag);equal([s.writes,s.closed,s.aborted],[[],1,0],'empty writable close');return s;
  },
  async S020({peer, tag}) {
    const w=(await peer.writable(tag,{delay:20})).getWriter();try{const a=w.write(Uint8Array.of(38)),b=w.write(Uint8Array.of(39)),c=w.close();await Promise.all([a,b,c]);}finally{w.releaseLock();}
    const s=await peer.settle(tag);equal(s.writes,[[38],[39]],'queued write bytes');equal(s.events,['start:0','end:0','start:1','end:1','close'],'close overtook queued writes');check(s.maxActive===1,'parallel sink writes');return s;
  },
  async S021({peer, tag}) {
    const stream=await peer.writable(tag,{});await stream.abort('unused');const s=await peer.settle(tag);check(s.aborted===1 && s.closed===0 && s.writes.length===0,'unwritten abort counters');return s;
  },
  async S022({peer, tag}) {
    const w=(await peer.writable(tag,{failAt:0})).getWriter();w.closed.catch(()=>{});let error;
    try{error=await rejects(w.write(Uint8Array.of(40)),'first write');await rejects(w.write(Uint8Array.of(41)),'write after error');}finally{w.releaseLock();}
    const s=await peer.settle(tag);check(error.includes('sink-failure'),'wrong writable error category');check(s.writes.length===1 && s.closed===0,'errored writer re-entered sink');return {error,stats:s};
  },
  async S023({peer, tag}) {
    const w=(await peer.writable(tag,{failClose:true})).getWriter();w.closed.catch(()=>{});let error;
    try{await w.write(Uint8Array.of(42));error=await rejects(w.close(),'sink close');await rejects(w.closed,'closed promise');}finally{w.releaseLock();}
    const s=await peer.settle(tag);check(error.includes('close-failure'),'wrong close error category');check(s.closed===1 && s.writes.length===1,'failed close counters');return {error,stats:s};
  },
  async S024({peer, tag}) {
    const stream=await peer.writable(tag,{});const first=stream.getWriter();await first.write(Uint8Array.of(43));first.releaseLock();const second=stream.getWriter();
    try{await second.write(Uint8Array.of(44));await second.close();}finally{second.releaseLock();}
    const s=await peer.settle(tag);equal(s.writes,[[43],[44]],'writer reacquire reordered/lost writes');check(s.closed===1,'reacquired writer close');return s;
  }
};
export default {async fetch(request,env){
  let input;
  try {
    input=await request.json();const root=env.ROOT.getByName(input.root);const path=new URL(request.url).pathname;
    const value=path==='/identity'?await root.inspect():path==='/run'?await root.run(input.id,input.peer):(()=>{throw new Error('unknown endpoint');})();
    return Response.json(value,{status:value?.status==='FAIL'?500:value?.status==='BLOCKED'?503:200});
  }catch(error){return Response.json({id:input?.id,status:'BLOCKED',phase:'dispatch',traceEntered:false,error:String(error)},{status:503});}
}};
