import { DurableObject } from 'cloudflare:workers';
import { WORKER } from './workers.js';
export const PROFILE='bounded-resource-frozen-v1';
export const eq=(a,b,label)=>{if(JSON.stringify(a)!==JSON.stringify(b))throw new Error(label+': '+JSON.stringify({actual:a,expected:b}));};
export const ok=(v,label)=>{if(!v)throw new Error(label);};
export async function rejection(fn,marker){try{await fn();}catch(e){const value=String(e);ok(value.includes(marker),'wrong error: '+value);return value;}throw new Error('expected rejection: '+marker);}
export function errors(rows,n){eq(rows.filter(x=>x.ok).length,n,'successful subrequest count');for(const row of rows.filter(x=>!x.ok))ok(row.error.includes('Worker exceeded subrequest limit of '+n),'wrong subrequest error');}
export class RootBase extends DurableObject {
 constructor(ctx,env){super(ctx,env);this.ctx=ctx;this.env=env;this.books=new Map();this.closed=new Set();this.instance=crypto.randomUUID();}
 inspect(){return {root:String(this.ctx.id),isolate:this.instance};}
 book(tag){ok(!this.closed.has(tag),'closed tag');ok(this.books.has(tag),'unopened tag');return this.books.get(tag);}
 note(tag,label,fail=false){const b=this.book(tag);ok(b.notes.length<32,'note bound');b.notes.push(label);if(fail)throw new Error('recipient-planned-failure');return {label,recipient:b.recipient};}
 async hold(tag,label){const b=this.book(tag);ok(!b.holds.has(label),'duplicate hold');this.note(tag,'held:'+label);b.pending++;let release;const promise=new Promise(r=>release=r);b.holds.set(label,{release,settled:false});for(const waiter of b.waiters)if(waiter.labels.every(x=>b.holds.has(x)))waiter.resolve();try{await promise;return label;}finally{b.pending--;b.holds.get(label).settled=true;}}
 release(tag,label){const b=this.book(tag);ok(b.holds.has(label),'missing release target');b.holds.get(label).release();}
}
export class Scope {
 constructor(root,tag){this.root=root;this.tag=tag;this.workers=[];this.entries=[];this.pending=[];this.closed=false;root.books.set(tag,{notes:[],holds:new Map(),pending:0,waiters:[],recipient:tag+':audit'});}
 config(limits={},source=WORKER,extra={}){return {compatibilityDate:'2026-09-04',mainModule:'worker.js',modules:{'worker.js':source},globalOutbound:null,limits,env:{AUDIT:this.root.ctx.exports.Audit({props:{root:this.root.name,tag:this.tag}})},...extra};}
 load(limits={},source=WORKER,extra={}){const w=this.root.env.LOADER.load(this.config(limits,source,extra));this.workers.push(w);ok(typeof w.dispose==='function','Worker disposal API unavailable');return w;}
 entry(worker,limits,props){const e=worker.getEntrypoint(undefined,{...(limits?{limits}:{}),...(props?{props}:{})});this.entries.push(e);ok(typeof Symbol.dispose==='symbol'&&typeof e[Symbol.dispose]==='function','Entrypoint disposal API unavailable');return e;}
 keep(p){const observed=Promise.resolve(p);observed.catch(()=>{});this.pending.push(observed);return observed;}
 notes(){return [...this.root.book(this.tag).notes];}
 exactNotes(expected){eq(this.notes(),expected,'exact recipient effects');}
 async waitHeld(labels){const b=this.root.book(this.tag);if(!labels.every(x=>b.holds.has(x)))await new Promise(resolve=>b.waiters.push({labels,resolve}));eq(b.pending,labels.length,'held cohort count');}
 release(label){this.root.release(this.tag,label);}
 async positiveControl(){const e=this.entry(this.load({subRequests:1}));const p=await e.probe();eq(p.kind,'bounded-resource','Loader precondition');const rows=await e.sequence(['setup']);eq(rows,[{ok:true,value:{label:'setup',recipient:this.tag+':audit'}}],'native Audit service positive control');this.exactNotes(['setup']);return p;}
 async healthy(){const e=this.entry(this.load());const p=await e.probe();eq(p.kind,'bounded-resource','fresh worker recovery');return p;}
 async cleanup(){const problems=[];const attempt=async(label,fn)=>{try{await fn();}catch(e){problems.push({label,error:String(e)});}};const b=this.root.book(this.tag);for(const h of b.holds.values())h.release();await Promise.allSettled(this.pending);for(const e of this.entries)await attempt('entry',()=>e[Symbol.dispose]());for(const w of this.workers)await attempt('worker',()=>w.dispose());const pending=b.pending;const unsettled=[...b.holds.values()].filter(h=>!h.settled).length;if(pending||unsettled)problems.push({label:'unfinished foreground work',pending,unsettled});this.root.books.delete(this.tag);this.root.closed.add(this.tag);this.closed=true;return {status:problems.length?'FAIL':'ok',pending,unsettled,workersDisposed:this.workers.length,entriesDisposed:this.entries.length,problems,externalTeardown:'required'};}
}
