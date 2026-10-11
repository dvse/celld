import {check,same,shape,bytes} from './common.js';
export const CASE_IDS=['W001','W002','W003','W004','W005','W006','W007','W008','W009','W010','W011','W012','W013','W014','W015','W016','W017','W018','W019','W020','W021','W022','W023','W024'];

// Each exported trace is authored separately; shared methods own transport and budgets.
export async function W001(l){
  const a=await l.held('duplex','a0'),b=await l.open('progress');
  const up=['a0','a1','a2','a3'];for(const s of up.slice(1))l.send(a,s);
  await l.serverSend(a,[{type:'text',value:'server-first'},{type:'text',value:'server-second'}]);
  l.send(b,'b-progress');await l.expect(b,['b-progress']);
  const s=await l.assertReceived(a,up);check(s.peers.find(p=>p.id===a.id).held===4,'uplink held during downlink');
  await l.expect(a,['server-first','server-second']);await l.release(a);await l.expect(a,['server-first','server-second',...up]);
  await l.cleanClose(a);await l.cleanClose(b);
}
export async function W002(l){
  const a=await l.held(),b=await l.open('mixed');const vals=['text-start',bytes(7,19),'text-end',bytes(199,257)];
  for(const v of vals)l.send(b,v);await l.expect(b,vals);await l.assertReceived(b,vals);
  same(b.messages.map(x=>x.eventType),['text','arraybuffer','text','arraybuffer'],'per-message opcode identity');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(b);await l.cleanClose(a);
}
export async function W003(l){
  const a=await l.held(),b=await l.open('snapshot',{hold:true});const buf=bytes(17,4096),expected=buf.slice();
  l.send(b,buf.buffer);buf.fill(0);l.send(b,'after-mutation');await l.assertReceived(b,[expected,'after-mutation']);
  await l.release(b);await l.expect(b,[expected,'after-mutation']);await l.release(a);await l.expect(a,['held-prefix']);
  await l.cleanClose(a);await l.cleanClose(b);
}
export async function W004(l){
  const a=await l.held(),b=await l.open('views');const backing=bytes(31,71),view=backing.subarray(7,39),dv=new DataView(backing.buffer,43,11),v=view.slice(),d=new Uint8Array(backing.buffer,43,11).slice();
  l.send(b,view);l.send(b,dv);backing.fill(255);await l.expect(b,[v,d]);await l.assertReceived(b,[v,d]);
  check(b.messages.every(x=>x.value.bytes<backing.length),'view boundaries exclude guards');await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(b);await l.cleanClose(a);
}
export async function W005(l){
  const a=await l.held(),b=await l.open('representations',{binaryType:'blob'}),first=bytes(43,33),second=bytes(79,65);
  l.send(b,first);await l.expect(b,[first]);check(b.messages[0].eventType==='blob','explicit blob receive');
  b.socket.binaryType='arraybuffer';l.send(b,second);l.send(b,'text-does-not-become-blob');await l.expect(b,[first,second,'text-does-not-become-blob']);
  same(b.messages.map(x=>x.eventType),['blob','arraybuffer','text'],'binaryType applies at separate witnessed deliveries');await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);await l.cleanClose(b);
}
export async function W006(l){
  const a=await l.held(),b=await l.open('empty-boundaries');const vals=['left','',new Uint8Array(0),'\u0000雪🙂','right'];
  for(const v of vals)l.send(b,v);await l.expect(b,vals);await l.assertReceived(b,vals);same(b.messages.map(v=>v.value.bytes),[4,0,0,8,5],'empty frames and UTF-8 widths remain separate');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(b);await l.cleanClose(a);
}
export async function W007(l){
  const a=await l.held('red','red:0'),b=await l.held('blue','blue:0');
  await l.serverSend(a,[{type:'text',value:'for:red:1'},{type:'binary',seed:21,n:113}]);await l.serverSend(b,[{type:'text',value:'for:blue:1'},{type:'binary',seed:91,n:73}]);
  await Promise.all([l.expect(a,['for:red:1',bytes(21,113)]),l.expect(b,['for:blue:1',bytes(91,73)])]);
  await l.release(b);await l.expect(b,['for:blue:1',bytes(91,73),'blue:0']);const s=await l.control('state');check(s.peers.find(p=>p.id===a.id).held===1,'red remained held while blue drained');
  await l.release(a);await l.expect(a,['for:red:1',bytes(21,113),'red:0']);await l.cleanClose(a);await l.cleanClose(b);
}
export async function W008(l){
  const a=await l.held('uploader-a','a0'),b=await l.held('uploader-b','b0');
  for(const [x,y] of [['a1','b1'],['a2','b2'],['a3','b3']]){l.send(a,x);l.send(b,y);}
  await Promise.all([l.assertReceived(a,['a0','a1','a2','a3']),l.assertReceived(b,['b0','b1','b2','b3'])]);
  await l.release(b);await l.expect(b,['b0','b1','b2','b3']);await l.release(a);await l.expect(a,['a0','a1','a2','a3']);await l.cleanClose(a);await l.cleanClose(b);
}
export async function W009(l){
  const a=await l.held(),b=await l.open('client-tail',{echo:false});const vals=['before-close',bytes(101,8192),'last-frame'];
  for(const v of vals)l.send(b,v);b.socket.close(1000,'client-tail');await l.cleanClose(b);const s=await l.assertReceived(b,vals);same(s.peers.find(p=>p.id===b.id).close[0],{code:1000,reason:'client-tail',wasClean:true},'close follows all client sends');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W010(l){
  const a=await l.held(),b=await l.open('server-tail',{echo:false});await l.serverSend(b,[{type:'text',value:'server-head'},{type:'binary',seed:117,n:8192},{type:'text',value:'server-tail'}],{code:1000,reason:'server-end'});
  await l.expect(b,['server-head',bytes(117,8192),'server-tail']);await l.cleanClose(b);same(b.close[0],{code:1000,reason:'server-end',wasClean:true},'server close metadata follows tail');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W011(l){
  const a=await l.held(),b=await l.open('app-close');l.send(b,'checkpoint');await l.expect(b,['checkpoint']);const s=await l.cleanClose(b,4001,'application done');
  same(s.peers.find(p=>p.id===b.id).close[0],{code:4001,reason:'application done',wasClean:true},'peer gets application close code');same(b.close[0],{code:4001,reason:'application done',wasClean:true},'normal reciprocal metadata');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W012(l){
  const a=await l.held(),b=await l.open('reason-boundary'),reason='雪'.repeat(41);check(new TextEncoder().encode(reason).length===123,'legal maximum reason');
  await l.serverSend(b,[{type:'text',value:'reason-ready'}],{code:4002,reason});await l.expect(b,['reason-ready']);await l.cleanClose(b);same(b.close[0],{code:4002,reason,wasClean:true},'123 UTF-8-byte legal reason is not truncated');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W013(l){
  const a=await l.held(),b=await l.open('cross-close');l.send(b,'both-ready');await l.expect(b,['both-ready']);await l.assertReceived(b,['both-ready']);
  const peerClose=l.control('close',{peer:b.id,code:4010,reason:'peer-close'});b.socket.close(4011,'caller-close');await peerClose;await l.cleanClose(b);
  check([4010,4011].includes(b.close[0].code),'received ordinary crossed close');l.note('crossed-close-observation',{client:b.close[0]});await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W014(l){
  const a=await l.held('cancel-held','witnessed-but-no-echo'),b=await l.open('survivor');await l.control('dropHeld',{peer:a.id});await l.cleanClose(a,4020,'drop-owned-work');
  l.send(b,'after-neighbor-close');await l.expect(b,['after-neighbor-close']);await l.assertReceived(b,['after-neighbor-close']);check(a.messages.length===0,'dropped application echo remains absent');await l.cleanClose(b);
}
export async function W015(l){
  const a=await l.held(),b=await l.open('repeat-close');l.send(b,'close-ready');await l.expect(b,['close-ready']);
  await l.control('close',{peer:b.id,code:4021,reason:'twice',repeat:true});await l.cleanClose(b);b.socket.close(4021,'twice');check(b.close.length===1,'duplicate public close does not dispatch second event');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W016(l){
  const a=await l.held(),b=await l.open('reentrant');let nested=0;const listener=e=>{if(e.data==='outer'){nested++;l.send(b,'inner');}};b.socket.addEventListener('message',listener);
  try{l.send(b,'outer');await l.expect(b,['outer','inner']);await l.assertReceived(b,['outer','inner']);check(nested===1,'message listener reentered send once');}finally{b.socket.removeEventListener('message',listener);}
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(b);await l.cleanClose(a);
}
export async function W017(l){
  const a=await l.held(),b=await l.open('message-closes',{closeOn:'last',code:4030,reason:'handler-finished'});l.send(b,'first');l.send(b,'last');
  await l.expect(b,['first','last']);await l.cleanClose(b);same(b.close[0],{code:4030,reason:'handler-finished',wasClean:true},'close from receiver message turn');
  await l.release(a);await l.expect(a,['held-prefix']);await l.cleanClose(a);
}
export async function W018(l){
  const a=await l.held('held-a','a'),b=await l.held('held-b','b');const c=await l.open('third-control');l.send(c,'control-during-holds');await l.expect(c,['control-during-holds']);
  const state=await l.control('state');check(state.peers.filter(p=>p.id==='held-a'||p.id==='held-b').every(p=>p.held===1),'two actual held receipts at control completion');await l.cleanClose(c);
  await l.release(b);await l.expect(b,['b']);await l.release(a);await l.expect(a,['a']);await l.cleanClose(a);await l.cleanClose(b);
}
export async function W019(l){
  const a=await l.held('ring-a','origin-a'),b=await l.open('ring-b'),c=await l.open('ring-c');
  await l.serverSend(a,[{type:'text',value:'a-to-b'}]);await l.expect(a,['a-to-b']);l.send(b,'from-a:'+a.messages[0].value.value);await l.expect(b,['from-a:a-to-b']);
  l.send(c,'from-b:'+b.messages[0].value.value);await l.expect(c,['from-b:from-a:a-to-b']);l.send(a,'from-c:'+c.messages[0].value.value);await l.assertReceived(a,['origin-a','from-c:from-b:from-a:a-to-b']);
  await l.release(a);await l.expect(a,['a-to-b','origin-a','from-c:from-b:from-a:a-to-b']);await l.cleanClose(c);await l.cleanClose(b);await l.cleanClose(a);
}
export async function W020(l){
  const a=await l.held('slow-ack','application-hold'),b=await l.open('fast-ack',{echo:false});
  await l.serverSend(a,[{type:'text',value:'slow-credit-1'}]);await l.serverSend(b,[{type:'text',value:'fast-credit-1'}]);await l.expect(b,['fast-credit-1']);l.send(b,'ack-fast-1');await l.assertReceived(b,['ack-fast-1']);
  const s=await l.control('state');same(s.peers.find(p=>p.id===a.id).received,[shape('application-hold')],'no slow credit issued yet');
  await l.serverSend(b,[{type:'text',value:'fast-credit-2'}]);await l.expect(b,['fast-credit-1','fast-credit-2']);await l.expect(a,['slow-credit-1']);l.send(a,'ack-slow-1');await l.assertReceived(a,['application-hold','ack-slow-1']);
  await l.release(a);await l.expect(a,['slow-credit-1','application-hold','ack-slow-1']);await l.cleanClose(b);await l.cleanClose(a);
}
export async function W021(l){
  const a=await l.held('anchored','anchor'),old=await l.open('old');l.send(old,'old-only');await l.expect(old,['old-only']);await l.cleanClose(old,4040,'completed-old');
  const fresh=await l.open('fresh');l.send(fresh,'new-only');await l.expect(fresh,['new-only']);await l.assertReceived(fresh,['new-only']);same(old.messages.map(x=>x.value),[shape('old-only')],'closed recipient gets no fresh delivery');
  await l.release(a);await l.expect(a,['anchor']);await l.cleanClose(fresh);await l.cleanClose(a);
}
export async function W022(l){
  const a=await l.open('upgrade-a',{upgrade:true,hold:true}),b=await l.open('upgrade-b',{upgrade:true,hold:true});l.send(a,'accepted-a');l.send(b,'accepted-b');
  await Promise.all([l.assertReceived(a,['accepted-a']),l.assertReceived(b,['accepted-b'])]);const held=await l.control('state');check(held.peers.filter(p=>p.id===a.id||p.id===b.id).every(p=>p.held===1),'both upgraded sockets witnessed held before release');l.note('upgrade-holds-witness',{peers:[a.id,b.id]});await l.release(b);await l.expect(b,['accepted-b']);await l.cleanClose(b);await l.release(a);await l.expect(a,['accepted-a']);await l.cleanClose(a);
}
export async function W023(l){
  const a=await l.open('unaccepted',{upgrade:true,delayAccept:true,echo:false}),b=await l.open('accepted-progress');
  await l.serverSend(a,[{type:'binary',seed:53,n:16384},{type:'text',value:'queued-tail'}]);l.send(b,'while-peer-unaccepted');await l.expect(b,['while-peer-unaccepted']);
  const s=await l.control('state');check(s.peers.find(p=>p.id===a.id).sent.length===2&&!a.accepted,'server send-call witness precedes client accept');l.note('buffering-characterization',{beforeAcceptMessages:a.messages.length,bufferedAmount:typeof a.socket.bufferedAmount==='number'?a.socket.bufferedAmount:null,claim:'finite delivery observation only; no queue cap or TCP pressure proof'});
  l.accept(a);await l.expect(a,[bytes(53,16384),'queued-tail']);await l.cleanClose(a);await l.cleanClose(b);
}
export async function W024(l){
  const a=await l.held('windowed','held-ack'),b=await l.open('independent');const burst=[{type:'binary',seed:67,n:16384},{type:'binary',seed:68,n:16384},{type:'binary',seed:69,n:16384}];
  await l.serverSend(a,burst);l.send(b,'independent-window');await l.expect(b,['independent-window']);const s=await l.control('state');check(s.peers.find(p=>p.id===a.id).held===1,'held application response overlaps finite server burst');
  l.note('backpressure-characterization',{serverSent:s.peers.find(p=>p.id===a.id).sent.length,clientDelivered:a.messages.length,bufferedAmount:typeof a.socket.bufferedAmount==='number'?a.socket.bufferedAmount:null,claim:'application credit is not native backpressure'});
  await l.expect(a,burst.map(x=>bytes(x.seed,x.n)));l.send(a,'credit-after-consumption');await l.assertReceived(a,['held-ack','credit-after-consumption']);await l.release(a);await l.expect(a,[...burst.map(x=>bytes(x.seed,x.n)),'held-ack','credit-after-consumption']);await l.cleanClose(a);await l.cleanClose(b);
}
const TABLE={W001,W002,W003,W004,W005,W006,W007,W008,W009,W010,W011,W012,W013,W014,W015,W016,W017,W018,W019,W020,W021,W022,W023,W024};
export async function runCase(id,lab){check(Object.hasOwn(TABLE,id),'known explicit case');return await TABLE[id](lab);}
