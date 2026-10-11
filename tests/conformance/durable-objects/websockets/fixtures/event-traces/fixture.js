import { DurableObject } from 'cloudflare:workers';
import { PROFILE,BINARY,LIMIT,check,need,ident,defer,bounded,shape,fromSpec,closeValid,failInfo } from './common.js';
import { Lab } from './lab.js';
import { CASE_IDS,runCase } from './cases.js';
const ISOLATE=crypto.randomUUID();
export class WebSocketRoot extends DurableObject {
  constructor(ctx,env){super(ctx,env);this.run=null;this.peers=new Map();this.waiters=new Set();this.events=[];this.wireBytes=0;this.frames=0;this.stopping=false;this.faults=[];}
  identity(){return {root:String(this.ctx.id),isolate:ISOLATE,profile:PROFILE};}
  note(peer,kind,extra={}){check(this.events.length<LIMIT.events,'peer event bound');this.events.push({seq:this.events.length+1,peer,kind,...extra});for(const w of [...this.waiters])w();}
  charge(data){const x=shape(data);this.wireBytes+=x.bytes;this.frames++;check(x.bytes<=LIMIT.frameBytes&&this.wireBytes<=LIMIT.wireBytes&&this.frames<=LIMIT.messages,'peer wire/message bound');return x;}
  record(p,data){check(p.received.length<LIMIT.peerMessages,'peer receive bound');const value=this.charge(data);p.received.push(value);this.note(p.id,'received',{ordinal:p.received.length});if(p.echo){if(p.hold){p.held.push(typeof data==='string'?data:data.slice(0));this.note(p.id,'echo-held',{ordinal:p.received.length});}else this.send(p,data);}if(p.closeOn&&typeof data==='string'&&data===p.closeOn){this.close(p,p.code,p.reason);}}
  send(p,data){check(!this.stopping&&!p.closeSent&&p.ws.readyState===WebSocket.OPEN,'send only on live normal socket');check(p.sent.length<LIMIT.peerMessages,'peer send bound');const v=this.charge(data);p.ws.send(data);p.sent.push(v);this.note(p.id,'sent',{ordinal:p.sent.length});}
  close(p,code=1000,reason='finished'){closeValid(code,reason);p.closeSent=true;p.ws.close(code,reason);this.note(p.id,'close-called',{code,reason});}
  snapshot(){return {...this.identity(),run:this.run,wireBytes:this.wireBytes,frames:this.frames,events:this.events,faults:this.faults,peers:[...this.peers.values()].map(p=>({id:p.id,opened:p.opened,received:p.received,sent:p.sent,held:p.held.length,closeSent:p.closeSent,close:p.closeEvents,errors:p.errors,readyState:p.ws?.readyState??null}))};}
  async waitFor(input){const matches=()=>{const p=this.peers.get(input.peer);return p&&p.received.length>=(input.received??0)&&p.sent.length>=(input.sent??0)&&p.closeEvents.length>=(input.closed??0);};if(matches())return this.snapshot();const d=defer();const notify=()=>{if(this.stopping)d.reject(new Error('recipient cleanup'));else if(matches())d.resolve();};this.waiters.add(notify);try{await bounded(d.promise,16000,'peer witnessed condition');return this.snapshot();}finally{this.waiters.delete(notify);}}
  async control(x){
    ident(x.run);if(x.action==='init'){need(this.run===null&&this.peers.size===0,'fresh recipient required');this.run=x.run;return this.snapshot();}
    check(this.run===x.run,'recipient run correlation');
    if(x.action==='state')return this.snapshot();
    if(x.action==='wait')return await this.waitFor(x);
    if(x.action==='configure'){ident(x.peer);check(!this.stopping&&!this.peers.has(x.peer)&&this.peers.size<LIMIT.peers,'fresh bounded peer');this.peers.set(x.peer,{id:x.peer,echo:x.echo!==false,hold:x.hold===true,closeOn:x.closeOn??null,code:x.code??1000,reason:x.reason??'message-close',received:[],sent:[],held:[],closeEvents:[],errors:[],ws:null,opened:false,closeSent:false});return this.snapshot();}
    if(x.action==='cleanup'){
      this.stopping=true;for(const notify of [...this.waiters])notify();for(const p of this.peers.values()){p.held=[];if(p.ws&&p.ws.readyState!==WebSocket.CLOSED&&!p.closeSent){try{this.close(p,1000,'cleanup');}catch(e){p.errors.push(failInfo(e));}}}
      const d=defer(),finished=()=>[...this.peers.values()].every(p=>!p.ws||p.closeEvents.length>0||p.ws.readyState===WebSocket.CLOSED);
      const notify=()=>{if(finished())d.resolve();};this.waiters.add(notify);notify();try{await bounded(d.promise,2500,'recipient cleanup close');}finally{this.waiters.delete(notify);}
      const state=this.snapshot();check(state.peers.every(p=>p.held===0&&(!p.opened||p.readyState===WebSocket.CLOSED)),'recipient resources drained');check(this.waiters.size===0,'recipient waiters drained');return {...state,cleanup:'ok',live:0,held:0,waiters:this.waiters.size};
    }
    const p=this.peers.get(x.peer);check(p?.opened,'known opened peer');
    if(x.action==='release'){p.hold=false;const pending=p.held.splice(0);for(const data of pending)this.send(p,data);this.note(p.id,'released',{count:pending.length});}
    else if(x.action==='dropHeld'){p.hold=false;const count=p.held.length;p.held=[];this.note(p.id,'held-dropped',{count});}
    else if(x.action==='send'){check(Array.isArray(x.messages)&&x.messages.length<=32,'bounded server burst');for(const s of x.messages)this.send(p,fromSpec(s));if(x.close)this.close(p,x.close.code,x.close.reason);}
    else if(x.action==='close'){this.close(p,x.code??1000,x.reason??'finished');if(x.repeat===true)this.close(p,x.code??1000,x.reason??'finished');}
    else check(false,'known control action');
    return this.snapshot();
  }
  async fetch(request){
    const url=new URL(request.url),parts=url.pathname.split('/').filter(Boolean),action=parts[2];
    if(action==='identity')return Response.json(this.identity());
    if(action==='control')return Response.json(await this.control(await request.json()));
    if(action==='socket'){
      check(request.headers.get('upgrade')?.toLowerCase()==='websocket','ordinary upgrade required');check(url.searchParams.get('run')===this.run&&!this.stopping,'active recipient run');
      const p=this.peers.get(ident(parts[3]));check(p&&!p.opened,'configured unique connection');check([...this.peers.values()].filter(v=>v.ws&&v.ws.readyState!==WebSocket.CLOSED).length<LIMIT.livePeers,'live peer bound');
      const pair=new WebSocketPair(),client=pair[0],server=pair[1];p.ws=server;p.opened=true;server.binaryType='arraybuffer';
      server.addEventListener('message',event=>{try{this.record(p,event.data);}catch(e){this.faults.push(failInfo(e));this.note(p.id,'handler-fault');try{this.close(p,4000,'fixture-fault');}catch{}}});
      server.addEventListener('error',event=>{p.errors.push({message:String(event.message||'WebSocket error')});this.note(p.id,'error');});
      server.addEventListener('close',event=>{p.closeEvents.push({code:event.code,reason:event.reason,wasClean:event.wasClean});this.note(p.id,'close-received',{code:event.code});if(!p.closeSent){try{this.close(p,event.code,event.reason);}catch(e){p.errors.push(failInfo(e));}}});
      server.accept();this.note(p.id,'accepted');return new Response(null,{status:101,webSocket:client,headers:{'x-ws-root':String(this.ctx.id),'x-ws-isolate':ISOLATE,'x-ws-run':this.run,'x-ws-peer':p.id}});
    }
    if(action==='run'){
      const input=await request.json();need(this.run===null,'fresh coordinator required');this.run=ident(input.run);const lab=new Lab(this.identity(),input);let status='BLOCKED',phase='precondition',error=null,traceEntered=false,cleanup=null;
      try{await bounded(lab.track(lab.init()),3000,'preflight');traceEntered=true;phase='trace';await bounded(lab.track((async()=>{await runCase(input.id,lab);await lab.recovery();})()),LIMIT.traceMs,'case trace');status='PASS';phase='complete';}
      catch(e){error=failInfo(e);status=traceEntered?'FAIL':'BLOCKED';}
      finally{try{cleanup=await bounded(lab.cleanup(),LIMIT.cleanupMs,'all cleanup');if(cleanup.status!=='ok'&&traceEntered)status='FAIL';}catch(e){cleanup={status:'incomplete',error:failInfo(e)};if(traceEntered)status='FAIL';}}
      return Response.json({id:input.id,run:this.run,profile:PROFILE,binary:BINARY,status,phase,traceEntered,error,caller:this.identity(),recipient:lab.recipient,evidence:lab.evidence(),cleanup,characterization:['W023','W024'].includes(input.id)});
    }
    return new Response('unknown fixture route',{status:404});
  }
}
export default {fetch(request,env){const path=new URL(request.url).pathname.split('/').filter(Boolean);if(path[0]==='health')return Response.json({profile:PROFILE,binary:BINARY,caseIds:CASE_IDS});check(path[0]==='root'&&path[1],'root path');return env.ROOT.get(env.ROOT.idFromName(ident(path[1]))).fetch(request);}};
