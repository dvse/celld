import {PROFILE,BINARY,ORIGIN,LIMIT,check,need,ident,defer,bounded,shape,same,failInfo} from './common.js';
export class Lab {
  constructor(caller,input){this.caller=caller;this.input=input;this.run=ident(input.run);this.name=ident(input.recipient);this.recipient=null;this.peers=new Map();this.events=[];this.requests=new Set();this.controls=0;this.frames=0;this.wireBytes=0;this.started=Date.now();this.remoteInitialized=false;this.remoteFinal=null;this.stopping=false;this.tasks=new Set();}
  track(promise){const p=Promise.resolve(promise);this.tasks.add(p);p.finally(()=>this.tasks.delete(p)).catch(()=>{});return p;}
  note(kind,x={}){check(this.events.length<LIMIT.events,'client event bound');this.events.push({seq:this.events.length+1,kind,...x});}
  async control(action,extra={}){
    check(!this.stopping||action==='cleanup','no trace control after cleanup starts');check(++this.controls<=LIMIT.controls,'control request bound');const abort=new AbortController();this.requests.add(abort);check(this.requests.size<=8,'active control request bound');
    try{const r=await fetch(ORIGIN+'/root/'+this.name+'/control',{method:'POST',redirect:'error',headers:{'content-type':'application/json'},body:JSON.stringify({action,run:this.run,...extra}),signal:abort.signal});check(r.status===200,'private control HTTP success');const state=await r.json();check(!this.stopping||action==='cleanup','control settled during cleanup');same({root:state.root,isolate:state.isolate,profile:state.profile},this.recipient,'actual recipient identity');check(state.run===this.run,'recipient run');check(state.faults.length===0,'recipient handler faults: '+JSON.stringify(state.faults));return state;}finally{this.requests.delete(abort);}
  }
  async init(){
    need(CASE.test(this.input.id),'known case range');need(typeof WebSocket==='function'&&typeof WebSocketPair==='function','public WebSocket APIs required');same(this.caller,this.input.expectedCaller,'coordinator identity');this.recipient=this.input.expectedRecipient;need(this.recipient?.profile===PROFILE&&this.recipient.root!==this.caller.root&&this.recipient.isolate!==this.caller.isolate,'independently witnessed peer identity required');
    await this.control('init');this.remoteInitialized=true;this.note('identities',{caller:this.caller,recipient:this.recipient,binary:BINARY});
    const p=await this.open('preflight');this.send(p,'clean-control');await this.expect(p,['clean-control']);await this.assertReceived(p,['clean-control']);await this.cleanClose(p,1000,'control');this.note('clean-close-control');
  }
  async open(id,options={}){
    ident(id);check(!this.stopping&&!this.peers.has(id)&&this.peers.size<LIMIT.peers,'fresh bounded client');check([...this.peers.values()].filter(p=>p.socket?.readyState!==WebSocket.CLOSED).length<LIMIT.livePeers,'client live bound');
    await this.control('configure',{peer:id,...options});check(!this.stopping,'configure resumed during cleanup');const p={id,socket:null,messages:[],sent:[],close:[],errors:[],waiters:new Set(),normalizers:new Set(),opened:false,accepted:true,listener:null};this.peers.set(id,p);
    const url=ORIGIN+'/root/'+this.name+'/socket/'+id+'?run='+this.run;
    let upgradeResponse=null;
    if(options.upgrade){const abort=new AbortController();this.requests.add(abort);check(this.requests.size<=8,'active upgrade request bound');try{upgradeResponse=await fetch(url,{redirect:'error',headers:{Upgrade:'websocket'},signal:abort.signal});p.socket=upgradeResponse.webSocket;p.accepted=false;}finally{this.requests.delete(abort);}}
    else p.socket=new WebSocket(url.replace(/^http:/,'ws:'));
    check(p.socket,'ordinary upgrade exposes socket');const ws=p.socket;ws.binaryType=options.binaryType||'arraybuffer';const notify=()=>{for(const f of [...p.waiters])f();};p.notify=notify;
    p.listener=event=>{const index=p.messages.length,entry={ready:false,eventType:typeof event.data==='string'?'text':event.data instanceof ArrayBuffer?'arraybuffer':event.data instanceof Blob?'blob':'unknown'};p.messages.push(entry);check(p.messages.length<=LIMIT.peerMessages,'client receive bound');
      const process=async()=>{const data=event.data instanceof Blob?await event.data.arrayBuffer():event.data;entry.value=shape(data);this.wireBytes+=entry.value.bytes;this.frames++;check(this.wireBytes<=LIMIT.wireBytes&&this.frames<=LIMIT.messages,'client message budget');entry.ready=true;this.note('client-received',{peer:id,ordinal:index+1,eventType:entry.eventType});notify();};
      const task=process().catch(e=>{p.errors.push(failInfo(e));notify();});p.normalizers.add(task);task.finally(()=>p.normalizers.delete(task));
    };
    ws.addEventListener('message',p.listener);ws.addEventListener('error',e=>{p.errors.push({message:String(e.message||'WebSocket error')});notify();});ws.addEventListener('close',e=>{p.close.push({code:e.code,reason:e.reason,wasClean:e.wasClean});this.note('client-close',{peer:id,code:e.code});notify();});ws.addEventListener('open',()=>{p.opened=true;notify();});
    check(!this.stopping,'socket acquisition resumed during cleanup');
    if(options.upgrade){check(upgradeResponse.status===101,'ordinary fetch upgrade');if(!options.delayAccept)this.accept(p);}else await this.wait(p,()=>p.opened,'constructor open');
    check(!this.stopping,'socket open resumed during cleanup');const state=await this.control('state'),r=state.peers.find(v=>v.id===id);check(r?.opened,'actual recipient accepted socket');this.note('socket-established',{peer:id,accepted:p.accepted,recipient:this.recipient});return p;
  }
  accept(p){check(!p.accepted,'one accept');p.socket.accept();p.accepted=true;p.opened=true;p.notify();this.note('client-accepted',{peer:p.id});}
  send(p,data){check(!this.stopping&&p.accepted&&p.socket.readyState===WebSocket.OPEN,'valid active client send');const v=shape(data);check(v.bytes<=LIMIT.frameBytes&&p.sent.length<LIMIT.peerMessages,'send bound');this.frames++;this.wireBytes+=v.bytes;check(this.frames<=LIMIT.messages&&this.wireBytes<=LIMIT.wireBytes,'client aggregate budget');p.socket.send(data);p.sent.push(v);this.note('client-sent',{peer:p.id,ordinal:p.sent.length});}
  async wait(p,predicate,label,allowCleanup=false){check(p.errors.length===0,'client socket error');if(predicate())return;const d=defer(),notify=()=>{if(this.stopping&&!allowCleanup)d.reject(new Error('fixture stopping'));else if(p.errors.length)d.reject(new Error('client socket error '+JSON.stringify(p.errors)));else if(predicate())d.resolve();};p.waiters.add(notify);try{await bounded(d.promise,16000,label);}finally{p.waiters.delete(notify);}}
  async expect(p,values){const wanted=values.map(shape);await this.wait(p,()=>p.messages.length>=wanted.length&&p.messages.slice(0,wanted.length).every(x=>x.ready),'expected messages '+p.id);same(p.messages.slice(0,wanted.length).map(x=>x.value),wanted,'complete ordered message prefix '+p.id);return p;}
  async assertReceived(p,values){const s=await this.control('wait',{peer:p.id,received:values.length});same(s.peers.find(x=>x.id===p.id).received,values.map(shape),'exact recipient messages '+p.id);return s;}
  async held(id='held',text='held-prefix'){const p=await this.open(id,{hold:true});this.send(p,text);const s=await this.assertReceived(p,[text]);check(s.peers.find(x=>x.id===id).held===1,'recipient echo held');this.note('hold-witness',{peer:id});return p;}
  async release(p){return await this.control('release',{peer:p.id});}
  async serverSend(p,messages,close){return await this.control('send',{peer:p.id,messages,...(close?{close}:{})});}
  async cleanClose(p,code=1000,reason='finished'){
    if(p.socket.readyState===WebSocket.OPEN)p.socket.close(code,reason);
    await this.wait(p,()=>p.close.length>0,'normal close '+p.id);const s=await this.control('wait',{peer:p.id,closed:1});this.assertClosed(p,s);return s;
  }
  assertClosed(p,s){const r=s.peers.find(v=>v.id===p.id);check(p.close.length===1&&p.close[0].wasClean===true&&r.close.length===1&&r.close[0].wasClean===true,'exactly one clean close at both endpoints');check(p.socket.readyState===WebSocket.CLOSED&&r.readyState===WebSocket.CLOSED,'both sockets closed');check(p.errors.length===0&&r.errors.length===0,'no normal-close error event');same(p.messages.filter(v=>v.ready).map(v=>v.value),r.sent,'all server frames delivered exactly once');same(p.sent,r.received,'all client frames delivered exactly once');}
  async recovery(){const p=await this.open('recovery');this.send(p,'after-trace');await this.expect(p,['after-trace']);await this.cleanClose(p);this.note('recovery');}
  evidence(){return {events:this.events,controls:this.controls,frames:this.frames,wireBytes:this.wireBytes,wallMs:Date.now()-this.started,clients:[...this.peers.values()].map(p=>({id:p.id,messages:p.messages,sent:p.sent,close:p.close,errors:p.errors})),recipient:this.remoteFinal};}
  async cleanup(){
    this.stopping=true;const errors=[];for(const p of this.peers.values())p.notify?.();for(const a of this.requests)a.abort('fixture cleanup');
    for(const p of this.peers.values()){try{if(!p.accepted&&p.socket)this.accept(p);if(p.socket&&p.socket.readyState===WebSocket.OPEN)p.socket.close(1000,'cleanup');}catch(e){errors.push(failInfo(e));}}
    const local=async()=>{
      try{await bounded(Promise.allSettled([...this.tasks]),2000,'drain interrupted fixture tasks');}catch(e){errors.push(failInfo(e));}
      for(const p of this.peers.values()){
        try{if(p.socket&&!p.accepted)this.accept(p);if(p.socket?.readyState===WebSocket.OPEN)p.socket.close(1000,'cleanup');}catch(e){errors.push(failInfo(e));}
      }
      const closed=await Promise.allSettled([...this.peers.values()].map(async p=>{if(p.socket&&p.socket.readyState!==WebSocket.CLOSED)await bounded(this.wait(p,()=>p.socket.readyState===WebSocket.CLOSED,'cleanup close',true),2000,'local cleanup close');await Promise.allSettled([...p.normalizers]);}));
      for(const r of closed)if(r.status==='rejected')errors.push(failInfo(r.reason));
      for(const p of this.peers.values())if(p.socket&&p.listener)p.socket.removeEventListener('message',p.listener);
      return {live:[...this.peers.values()].filter(p=>p.socket&&p.socket.readyState!==WebSocket.CLOSED).length,pending:[...this.peers.values()].reduce((n,p)=>n+p.normalizers.size,0),tasks:this.tasks.size};
    };
    const remote=async()=>{if(!this.remoteInitialized)return {cleanup:'not-initialized',live:0,held:0,waiters:0};const r=await this.control('cleanup');this.remoteFinal=r;return r;};
    const results=await Promise.allSettled([local(),remote()]);for(const r of results)if(r.status==='rejected')errors.push(failInfo(r.reason));const a=results[0].value,b=results[1].value;
    const ok=errors.length===0&&a?.live===0&&a.pending===0&&a.tasks===0&&b?.live===0&&b.held===0&&b.waiters===0&&this.requests.size===0;return {status:ok?'ok':'incomplete',local:a??null,remote:b??null,errors};
  }
}
const CASE=/^W0(?:0[1-9]|1[0-9]|2[0-4])$/;
