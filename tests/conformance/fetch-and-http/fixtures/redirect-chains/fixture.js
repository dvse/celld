import {DurableObject} from 'cloudflare:workers';
import {PROFILE,LIMITS,check,ident,privateOrigin,routeName,configuredLocation,bytes,join,equal,hash,gate,bounded} from './common.js';
import {runCase,CASE_IDS} from './cases.js';
const ISOLATE=crypto.randomUUID();
// One request-scoped coordinator, plus ordinary separately entered recipient HTTP requests.
export class RedirectRoot extends DurableObject {
  constructor(ctx,env){super(ctx,env);this.ops=new Map();this.routes=new Map();this.gates=new Map();this.events=[];this.run=null;this.rootName=null;this.closing=false;this.total=0;this.requests=0;this.pulls=new Set();this.faults=[];}
  identity(){return {root:String(this.ctx.id),isolate:ISOLATE,profile:PROFILE};}
  note(name,kind,extra={}){check(this.events.length<LIMITS.events,'recipient journal cap');this.events.push({seq:this.events.length+1,name,kind,...extra});}
  barrier(name){ident(name);if(!this.gates.has(name)){check(this.gates.size<48,'gate cap');this.gates.set(name,gate());}return this.gates.get(name);}
  async wait(name){if(name)await bounded(this.barrier(name).promise,16000,'recipient gate '+name);}
  release(names){check(Array.isArray(names)&&names.length<=48,'release cap');for(const name of names){const g=this.barrier(name);if(!g.open){this.note(name,'gate-release');g.open=true;g.resolve();}}}
  state(){return {...this.identity(),run:this.run,requests:this.requests,ops:[...this.ops].map(([name,o])=>({name,...o.r})),events:this.events,active:[...this.ops.values()].filter(o=>o.r.active).length,pulls:this.pulls.size,faults:this.faults};}
  configure(c){
    check(!this.closing&&this.ops.size<LIMITS.operations,'recipient operation cap');ident(c.name);check(!this.ops.has(c.name),'fresh endpoint');
    routeName(c.route);check(!this.routes.has(c.route),'fresh endpoint path');
    check(['GET','POST','PUT','HEAD'].includes(c.method),'ordinary bounded method');check(Number.isInteger(c.status)&&[200,302,303,307,422].includes(c.status),'finite status set');
    bytes(c.inputLabel,c.inputN);bytes(c.outputLabel,c.outputN);this.total+=c.inputN+c.outputN;check(this.total<=LIMITS.payloadBytes,'recipient byte cap');
    check(typeof c.query==='string'&&/^\??[A-Za-z0-9_=&-]*$/.test(c.query),'bounded query');
    for(const k of ['headGate','tailGate','commitGate'])if(c[k])ident(c[k]);
    check(!c.prefix||Number.isInteger(c.prefix)&&c.prefix>0&&c.prefix<c.outputN,'stream prefix bound');
    if(c.location!==null){
      check([302,303,307].includes(c.status)&&typeof c.location==='string'&&c.location.length<256,'ordinary redirect location');
      const base=privateOrigin(this.env.PRIVATE_ORIGIN)+'/root/'+this.rootName+'/op/'+c.route+c.query;
      const {target}=configuredLocation(c.location,base,this.env.PRIVATE_ORIGIN,this.rootName,this.routes);
      c.depth=1+(target.depth||0);check(c.depth<=3,'finite acyclic redirect graph at most three edges');
    }
    const r={entered:0,active:false,inputBytes:0,inputTerminal:'unopened',effect:0,outputBytes:0,outputTerminal:'unopened',stopped:false};
    this.ops.set(c.name,{c,r,reader:null,controller:null,done:gate()});this.routes.set(c.route,c);return {configured:c.name};
  }
  finish(o,terminal){o.r.outputTerminal=terminal;o.r.active=false;o.controller=null;o.done.resolve();this.note(o.c.name,'output-'+terminal);}
  async stop(name){const o=this.ops.get(name);check(o,'known stop');o.r.stopped=true;this.note(name,'application-stop');for(const k of ['headGate','tailGate','commitGate'])if(o.c[k])this.release([o.c[k]]);if(o.reader)await o.reader.cancel('fixture stops owned input');if(o.controller){o.controller.error(new Error('fixture application stopped'));this.finish(o,'stopped');}}
  async cleanup(){
    this.closing=true;for(const o of this.ops.values())o.r.stopped=true;
    for(const [name] of this.gates)this.release([name]);
    const stops=await Promise.allSettled([...this.ops.keys()].map(n=>this.stop(n)));
    check(stops.every(x=>x.status==='fulfilled'),'recipient stop did not settle successfully');
    await bounded(Promise.all([...this.ops.values()].filter(o=>o.r.entered).map(o=>o.done.promise)),1800,'recipient handlers');
    await bounded(Promise.all([...this.pulls]),600,'recipient pull tasks');
    check(this.faults.length===0,'recipient assertion/producer fault: '+this.faults.join(';'));
    check([...this.ops.values()].every(o=>!o.r.active&&!o.reader&&!o.controller)&&this.pulls.size===0,'recipient resources remain');
    return {...this.identity(),run:this.run,status:'ok',active:0,readers:0,controllers:0,pulls:0,journal:this.state()};
  }
  async operation(request,name){
    check(!this.closing,'recipient closed');const o=this.ops.get(name);check(o,'configured endpoint');const {c,r}=o;
    check(r.entered===0,'finite endpoint entered more than once');r.entered=1;r.active=true;
    r.method=request.method;r.path=new URL(request.url).pathname;r.query=new URL(request.url).search;r.contentType=request.headers.get('content-type');
    this.note(name,'entered',{method:r.method,query:r.query});
    try{
      check(r.method===c.method&&r.query===c.query&&r.path==='/root/'+this.rootName+'/op/'+c.route,'recipient method/path/query mismatch');
      const parts=[];r.inputTerminal='reading';o.reader=request.body?.getReader()||null;
      if(o.reader){try{for(let count=0;count<LIMITS.readOperations;count++){const v=await o.reader.read();if(v.done){r.inputTerminal='eof';break;}const part=new Uint8Array(v.value);parts.push(part);r.inputBytes+=part.length;check(r.inputBytes<=LIMITS.operationBytes,'recipient input cap');check(count<LIMITS.readOperations-1,'recipient read cap');}}finally{o.reader.releaseLock();o.reader=null;}}
      else r.inputTerminal='eof';
      const value=join(parts);equal(value,bytes(c.inputLabel,c.inputN),'recipient '+name);r.inputHash=await hash(value);this.note(name,'input-eof',{bytes:r.inputBytes,hash:r.inputHash});
      await this.wait(c.commitGate);if(c.commit&&!r.stopped){r.effect=1;this.note(name,'effect',{value:1});}
      await this.wait(c.headGate);if(r.stopped){this.finish(o,'stopped');return new Response('stopped',{status:422});}
      const headers={'content-type':'application/octet-stream','x-fetch-op':name,'x-fetch-run':this.run,'x-fetch-root':String(this.ctx.id),'x-fetch-isolate':ISOLATE};
      if(c.location!==null)headers.location=c.location;
      if(c.method==='HEAD'){headers['content-length']=String(c.outputN);this.finish(o,'head');return new Response(null,{status:c.status,headers});}
      const data=bytes(c.outputLabel,c.outputN);
      if(!c.tailGate){r.outputBytes=data.length;this.finish(o,'eof');return new Response(data,{status:c.status,headers});}
      let pos=0;const self=this;
      const stream=new ReadableStream({
        start(controller){o.controller=controller;},
        pull(controller){
          const work=(async()=>{
            if(pos>0)await self.wait(c.tailGate);
            if(r.stopped||!r.active)return;
            if(pos===data.length){controller.close();self.finish(o,'eof');return;}
            const end=pos===0?c.prefix:data.length;const part=data.subarray(pos,end);pos=end;r.outputBytes+=part.length;self.note(name,'produced',{bytes:r.outputBytes});controller.enqueue(part);
          })();
          const observed=work.then(()=>({ok:true}),error=>{self.faults.push(name+': '+String(error));if(o.controller)controller.error(error);self.finish(o,'error');return {ok:false,error:String(error)};});
          self.pulls.add(observed);observed.then(()=>self.pulls.delete(observed));return observed.then(result=>{if(!result.ok)throw new Error(result.error);});
        },
        cancel(){r.stopped=true;if(c.tailGate)self.release([c.tailGate]);self.finish(o,'cancelled');}
      },{highWaterMark:0});
      return new Response(stream,{status:c.status,headers});
    }catch(error){this.faults.push(name+': '+String(error));this.finish(o,'error');throw error;}
  }
  async fetch(request){
    check(++this.requests<=184,'recipient total HTTP request cap including internal redirect hops');
    const path=new URL(request.url).pathname.split('/').filter(Boolean);const action=path[2];this.rootName=ident(path[1]);
    if(action==='identity')return Response.json(this.identity());
    if(action==='run'){check(this.run===null,'fresh coordinator');const input=await request.json();this.run=ident(input.run);check(CASE_IDS.includes(input.id),'known case');return Response.json(await runCase(input,this.identity(),privateOrigin(this.env.PRIVATE_ORIGIN)));}
    if(action==='control'){const x=await request.json();check(x.run===this.run||this.run===null,'recipient run correlation');if(this.run===null)this.run=ident(x.run);switch(x.action){case 'configure':return Response.json(this.configure(x.config));case 'snapshot':return Response.json(this.state());case 'release':this.release(x.names);return Response.json({released:x.names});case 'stop':await this.stop(x.name);return Response.json({stopped:x.name});case 'cleanup':return Response.json(await this.cleanup());default:throw new Error('unknown control');}}
    if(action==='op'){const config=this.routes.get(routeName(path.slice(3).join('/')));check(config,'configured fixture path');return this.operation(request,config.name);}return new Response('unknown route',{status:404});
  }
}
export default {async fetch(request,env){const path=new URL(request.url).pathname.split('/').filter(Boolean);if(path[0]==='health')return Response.json({profile:PROFILE,caseIds:CASE_IDS,limits:LIMITS});check(path[0]==='root'&&path.length>=3,'fixture route');return env.ROOT.getByName(ident(path[1])).fetch(request);}};
