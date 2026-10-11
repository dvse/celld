import { PROBE, VERIFY_FAILURE, OBJECT_AND_NAMED, IMPORTER, facetSource } from './sources.mjs';
export const DATE='2026-09-04';
const ok=(condition,message)=>{if(!condition)throw new Error(message);};
const eq=(actual,expected,label)=>ok(JSON.stringify(actual)===JSON.stringify(expected),label+': '+JSON.stringify({actual,expected}));
const tick=()=>new Promise(resolve=>setTimeout(resolve,5));
export const code=(source=PROBE,extra={})=>({compatibilityDate:DATE,compatibilityFlags:['allow_irrevocable_stub_storage'],mainModule:'worker.js',modules:{'worker.js':source},globalOutbound:null,...extra});
export async function rejected(fn,contains) { try { await fn(); } catch(error) { const value={name:error?.name,error:String(error)}; if(contains)ok(value.error.includes(contains),'wrong rejection: '+JSON.stringify(value)); return value; } throw new Error('expected rejection'+(contains?': '+contains:'')); }
export function makeScope(root,tag) {
  const workers=[],entries=[],facets=root.activeFacets,released=new Set(),unblockers=[];
  return {
    root,tag,ctx:root.ctx,env:root.env,
    onCleanup(fn) {unblockers.push(fn);},
    load(config) { const w=root.env.LOADER.load(config);workers.push(w);return w; },
    get(name,cb) { const w=root.env.LOADER.get(tag+':'+name,cb);workers.push(w);return w; },
    ep(w,name,props) { const entry=w.getEntrypoint(name,{props});entries.push(entry);return entry; },
    facet(name,cb) { facets.add(name);return root.ctx.facets.get(name,cb); },
    abort(name,reason='case-abort') { root.ctx.facets.abort(name,new Error(reason)); },
    audit(label='explicit') { return root.ctx.exports.Audit({props:{root:tag,label}}); },
    drop(w) { w.dispose();released.add(w); },
    async cleanup() {
      const errors=[];
      const attempt=async(kind,fn)=>{try{await fn();}catch(error){errors.push({kind,error:String(error)});}};
      for(const unblock of unblockers)await attempt('code-gate',unblock);
      await attempt('cancellation-gate',()=>root.releaseHold());
      for(const name of facets)await attempt('facet:'+name,()=>root.ctx.facets.abort(name,new Error('fixture-cleanup')));
      for(const e of entries)await attempt('entrypoint',()=>e[Symbol.dispose]?.());
      for(const w of workers)if(!released.has(w))await attempt('worker',()=>w.dispose());
      for(const key of [...root.savedKeys])await attempt('row:'+key,async()=>{await root.ctx.storage.delete(key);root.savedKeys.delete(key);});
      root.restorePlans.clear();
      const report={facetAbortsAttempted:facets.size,workerHandles:workers.length,entrypointHandles:entries.length,ownedRowsCleared:root.savedKeys.size===0,storageReclamation:'disposable fleet teardown required',errors};
      if(errors.length){const error=new Error('aggregate fixture cleanup failure');error.cleanupReport=report;throw error;}
      return report;
    }
  };
}
// Every body below owns a distinct schedule/oracle. No generated case loops.
export const loaderCases={
  async L001(s) {
    let calls=0;const w=s.get('throwing-factory',()=>{calls++;throw new Error('factory-failed');});
    eq(calls,0,'factory must not run synchronously');const e=s.ep(w);
    const error=await rejected(()=>e.verify(),'factory-failed');eq(calls,1,'one failing factory');
    const control=await s.ep(s.get('recovery-v2',()=>code())).verify();eq(control.entry,'default','independent version recovers');
    return {calls,error,control};
  },
  async L002(s) {
    let resolve,markStarted;const gate=new Promise(r=>{resolve=r;});const started=new Promise(r=>{markStarted=r;});s.onCleanup(resolve);let first=0,second=0;
    const a=s.get('coalesced',async()=>{first++;markStarted();await gate;return code();});
    const b=s.get('coalesced',()=>{second++;return code();});
    const ea=s.ep(a),eb=s.ep(b);const pending=Promise.all([ea.verify(),eb.verify()]);
    try { await started;eq([first,second],[1,0],'held shared load factories'); } finally { resolve(); }
    const values=await pending;eq(values[0].token,values[1].token,'shared load token');eq([first,second],[1,0],'coalesced callback count');
    return {first,second,values};
  },
  async L003(s) {
    let calls=0;const factory=()=>{calls++;throw new Error('cached-failure');};
    const a=s.get('failure-cache',factory),b=s.get('failure-cache',factory);
    const results=await Promise.all([rejected(()=>s.ep(a).verify(),'cached-failure'),rejected(()=>s.ep(b).verify(),'cached-failure')]);
    eq(calls,1,'retained failure shared');s.drop(a);s.drop(b);
    const c=s.get('failure-cache',factory);await rejected(()=>s.ep(c).verify(),'cached-failure');eq(calls,2,'release permits retry of unchanged factory');
    eq((await s.ep(s.get('good-version',()=>code())).verify()).entry,'default','good version after failed retry');return {calls,results};
  },
  async L004(s) {
    const one=s.load(code()),two=s.load(code());const values=await Promise.all([s.ep(one).verify(),s.ep(two).verify()]);
    ok(values[0].token!==values[1].token,'anonymous loads unexpectedly share isolate');
    const broken=s.load(code('throw new Error("anonymous-evaluation");'));
    await rejected(()=>s.ep(broken).verify(),'anonymous-evaluation');
    eq((await s.ep(two).verify()).token,values[1].token,'other anonymous worker survives failure');return {values};
  },
  async L005(s) {
    const w=s.get('bad-evaluation-v1',()=>code('throw new Error("module-evaluation");\n'+PROBE));
    const e=s.ep(w);const failures=await Promise.all([rejected(()=>e.verify(),'module-evaluation'),rejected(()=>e.run('not-entered'),'module-evaluation')]);
    eq(s.root.events,[],'failed module must not call audit');
    const good=s.ep(s.get('good-evaluation-v2',()=>code(PROBE,{env:{AUDIT:s.audit()}})));
    await good.verify();await good.run('after-repair');eq(s.root.events.map(x=>x.value),['after-repair'],'exact recovery effect');return {failures};
  },
  async L006(s) {
    const broken=s.ep(s.get('missing-dependency-v1',()=>code(IMPORTER)));
    const failure=await rejected(()=>broken.verify(),'dependency.js');
    const repaired=s.ep(s.get('complete-dependency-v2',()=>code(IMPORTER,{modules:{'worker.js':IMPORTER,'dependency.js':'export const value="dependency-restored";'}})));
    eq(await repaired.verify(),'dependency-restored','dependency repair uses new code key');return {failure};
  },
  async L007(s) {
    const broken=s.ep(s.get('syntax-v1',()=>code('export default class { verify( {')));
    const failure=await rejected(()=>broken.verify());ok(/SyntaxError|Unexpected (end|token)|parse/i.test(failure.error),'wrong syntax failure: '+failure.error);
    const fixed=s.ep(s.get('syntax-v2',()=>code()));eq((await fixed.verify()).entry,'default','syntax repair control');
    const repeated=await rejected(()=>broken.verify());ok(/SyntaxError|Unexpected (end|token)|parse/i.test(repeated.error),'wrong repeat syntax failure');eq((await fixed.verify()).entry,'default','old invalid worker cannot poison replacement');return {failure};
  },
  async L008(s) {
    const e=s.ep(s.load(code(VERIFY_FAILURE,{env:{AUDIT:s.audit()}})));let ran=false;
    const failure=await rejected(async()=>{await e.verify();ran=true;await e.run();},'verification-failed');
    eq(ran,false,'run phase incorrectly entered');eq(s.root.events,[],'run audit effect');eq(await e.healthy(),'still-callable','method failure poisoned worker');
    return {failure,ran,events:s.root.events};
  },
  async L009(s) {
    const w=s.load(code());const d=s.ep(w),n=s.ep(w,'Named');
    const a=await d.verify(),b=await n.verify();eq([a.entry,b.entry],['default','named'],'export resolution');eq(a.token,b.token,'named exports must belong to same loaded module');
    eq((await d.verify()).entry,'default','named selection did not replace default');return {a,b};
  },
  async L010(s) {
    const w=s.load(code()),good=s.ep(w),missing=s.ep(w,'Missing');const first=await good.verify();
    const failure=await rejected(()=>missing.verify(),'Missing');eq((await good.verify()).token,first.token,'missing name damaged good export');return {failure,first};
  },
  async L011(s) {
    const w=s.load(code()),broken=s.ep(w,'Broken'),healthy=s.ep(w,'Named');
    const failure=await rejected(()=>broken.verify(),'constructor-failed');eq((await healthy.verify()).entry,'named','sibling export damaged');
    await rejected(()=>broken.verify(),'constructor-failed');eq((await healthy.verify()).entry,'named','second construction failure poisoned sibling');return {failure};
  },
  async L012(s) {
    const w=s.load(code(OBJECT_AND_NAMED));const d=s.ep(w,undefined,{lane:'object'}),n=s.ep(w,'Named');
    eq(await (await d.fetch('https://fixture.invalid/object')).json(),{entry:'object',props:{lane:'object'}},'object entrypoint context');
    eq(await n.verify(),'named-class','class selected beside object default');return {objectFetch:true,namedRpc:true};
  },
  async L013(s) {
    let release;const gate=new Promise(r=>{release=r;});s.onCleanup(release);
    const w=s.get('pending-code',async()=>{await gate;return code();});
    const config={value:'before'},props=Object.freeze({config});const e=s.ep(w,undefined,props);
    config.value='after-binding-before-load';const pending=e.inspect();release();
    const v=await pending;eq(v.props,{config:{value:'before'}},'eager capture must precede asynchronous loading');eq(config.value,'after-binding-before-load','caller mutation control');return v;
  },
  async L014(s) {
    const w=s.load(code()),props={config:{value:'first'}};const a=s.ep(w,undefined,props);
    props.config={value:'second'};const b=s.ep(w,'Named',props);props.config.value='third';
    const x=await a.inspect(),y=await b.inspect();eq([x.props.config.value,y.props.config.value],['first','second'],'two binding instants conflated');return {x,y};
  },
  async L015(s) {
    const e=s.ep(s.load(code()),undefined,{config:{value:'immutable-template'}});
    eq(await e.mutate(),'immutable-template','first recipient snapshot');eq(await e.mutate(),'immutable-template','recipient mutation leaked across invocations');
    eq((await e.inspect()).props.config.value,'immutable-template','binding template mutated');return {invocations:3};
  },
  async L016(s) {
    const frozen=Object.freeze({config:Object.freeze({value:'frozen'})});const e=s.ep(s.load(code()),undefined,frozen);
    eq(await e.mutate(),'frozen','cloned frozen input must permit recipient write');eq(frozen.config.value,'frozen','recipient wrote back into frozen caller');
    eq((await e.inspect()).props.config.value,'frozen','fresh call template');return {callerFrozen:Object.isFrozen(frozen.config)};
  },
  async L017(s) {
    const e=s.ep(s.load(code()));const a=await e.verify(),b=await e.verify();
    eq([a.turns,b.turns],[1,1],'stateless entrypoint instance reused');eq(a.token,b.token,'module unexpectedly replaced during receiver-lifetime test');return {a,b};
  },
  async L018(s) {
    const e=s.ep(s.load(code(PROBE,{env:{PUBLIC_LABEL:'owned-fixture'}})),undefined,{lane:'props'});
    const v=await e.inspect();eq(v.keys,['PUBLIC_LABEL'],'parent ROOT/LOADER/AMBIENT_TEST leaked into child env');eq(v.props,{lane:'props'},'props separate from env');return v;
  },
  async L019(s) {
    const child=s.ep(s.load(code(PROBE,{env:{AUDIT:s.audit('granted-route')}})));
    const reply=await child.run('authorized-effect');eq([reply.root,reply.label,reply.value],[s.tag,'granted-route','authorized-effect'],'explicit loopback authority/props');
    eq(s.root.events,[reply],'exact one bound side effect');return reply;
  },
  async L020(s) {
    const env={PUBLIC_LABEL:'captured'};const e=s.ep(s.load(code(PROBE,{env})));
    await e.verify();delete env.PUBLIC_LABEL;env.NEW_AUTHORITY='not-sent';
    const v=await e.inspect();eq(v.keys,['PUBLIC_LABEL'],'caller env mutation changed loaded bindings');return v;
  },
  async L021(s) {
    const granted=s.ep(s.load(code(PROBE,{env:{AUDIT:s.audit('only-first')}})));
    const empty=s.ep(s.load(code(PROBE,{env:{}})));eq((await empty.verify()).entry,'default','empty-env worker positive control');await granted.run('before');
    const failure=await rejected(()=>empty.run('denied'));eq(failure.name,'TypeError','absent binding error kind');eq((await empty.verify()).entry,'default','empty-env worker post-failure liveness');eq(s.root.events.map(x=>x.value),['before'],'absent binding gained first child authority');
    await granted.run('after');eq(s.root.events.map(x=>x.value),['before','after'],'granted binding survives absent binding failure');return {failure};
  },
  async L022(s) {
    const w=s.load(code(facetSource('loaded-root')));const facet=s.facet('same-class-name',()=>({class:w.getDurableObjectClass('Root')}));
    const v=await facet.inspect();eq(v.module,'loaded-root','parent Root selected for loaded Root class');eq(v.count,0,'new facet storage');
    eq(s.root.parentIdentity(),'fixture-supervisor','parent class unaffected');await facet.bump();eq(await s.root.ctx.storage.get('count'),undefined,'facet write leaked into supervisor storage');return v;
  },
  async L023(s) {
    const a=s.load(code(facetSource('alpha'))),b=s.load(code(facetSource('beta')));
    const fa=s.facet('alpha',()=>({class:a.getDurableObjectClass('Gadget')})),fb=s.facet('beta',()=>({class:b.getDurableObjectClass('Gadget')}));
    eq(await fa.bump(),1,'alpha write');const x=await fa.inspect(),y=await fb.inspect();
    eq([x.module,y.module,x.count,y.count],['alpha','beta',1,0],'loaded Gadget class namespace collision');return {x,y};
  },
  async L024(s) {
    const w=s.load(code(facetSource('same-code'))),cls=w.getDurableObjectClass('Gadget');
    const a=s.facet('one',()=>({class:cls,id:'same-display-id'})),b=s.facet('two',()=>({class:cls,id:'same-display-id'}));
    eq(await a.bump(),1,'first facet write');const x=await a.inspect(),y=await b.inspect();
    eq([x.id,y.id],['same-display-id','same-display-id'],'explicit ID control');eq([x.count,y.count],[1,0],'facet names must partition storage despite identical visible IDs');return {x,y};
  },
  async L025(s) {
    let first=0,replacement=0;const w=s.load(code(facetSource('cached-facet')));
    const a=s.facet('cached',()=>{first++;return {class:w.getDurableObjectClass('Gadget')};});await a.bump();
    const b=s.facet('cached',()=>{replacement++;throw new Error('unused-replacement');});
    eq((await b.inspect()).count,1,'same-name running facet replaced');eq([first,replacement],[1,0],'cached facet startup callback');return {first,replacement};
  },
  async L026(s) {
    const old=s.load(code(facetSource('v1'))),next=s.load(code(facetSource('v2')));
    const a=s.facet('upgrade',()=>({class:old.getDurableObjectClass('Gadget')}));await a.bump();s.abort('upgrade','upgrade-switch');
    const b=s.facet('upgrade',()=>({class:next.getDurableObjectClass('Other')}));const v=await b.inspect();
    eq([v.module,v.count],['other:v2',1],'replacement class lost facet storage');const failure=await rejected(()=>a.bump(),'upgrade-switch');eq((await b.inspect()).count,1,'stale stub ran into replacement');return {v,failure};
  },
  async L027(s) {
    let oldStarts=0,newStarts=0;const w=s.load(code(facetSource('after-cancel')));
    const old=s.facet('unstarted',()=>{oldStarts++;return {class:w.getDurableObjectClass('Gadget')};});s.abort('unstarted','cancel-before-start');
    await rejected(()=>old.inspect(),'cancel-before-start');eq(oldStarts,0,'cancelled lazy callback executed');
    const next=s.facet('unstarted',()=>{newStarts++;return {class:w.getDurableObjectClass('Gadget')};});eq((await next.inspect()).module,'after-cancel','lazy replacement');eq(newStarts,1,'replacement starts once');return {oldStarts,newStarts};
  },
  async L028(s) {
    let failedStarts=0;const broken=s.facet('factory-recovery',()=>{failedStarts++;throw new Error('facet-startup-failed');});
    await rejected(()=>broken.inspect(),'facet-startup-failed');await rejected(()=>broken.inspect(),'facet-startup-failed');eq(failedStarts,1,'failed startup repeated without abort');
    s.abort('factory-recovery');const w=s.load(code(facetSource('recovered')));const recovered=s.facet('factory-recovery',()=>({class:w.getDurableObjectClass('Gadget')}));
    eq((await recovered.inspect()).module,'recovered','abort did not clear startup rejection');return {failedStarts};
  },
  async L029(s) {
    const w=s.load(code(facetSource('constructor-recovery')));const bad=s.facet('constructor',()=>({class:w.getDurableObjectClass('Broken')}));
    const failure=await rejected(()=>bad.inspect(),'facet-constructor-failed');s.abort('constructor');
    const good=s.facet('constructor',()=>({class:w.getDurableObjectClass('Gadget')}));eq((await good.inspect()).count,0,'failed construction dirtied storage');eq(await good.bump(),1,'replacement constructor unusable');return {failure};
  },
  async L030(s) {
    const bad=s.get('facet-code-v1',()=>{throw new Error('facet-code-unavailable');});const f=s.facet('load-recovery',()=>({class:bad.getDurableObjectClass('Gadget')}));
    const failure=await rejected(()=>f.inspect(),'facet-code-unavailable');s.abort('load-recovery');
    const good=s.get('facet-code-v2',()=>code(facetSource('new-version')));const g=s.facet('load-recovery',()=>({class:good.getDurableObjectClass('Gadget')}));
    eq((await g.inspect()).module,'new-version','loader failure stuck in facet startup state');return {failure};
  },
  async L031(s) {
    const e=s.ep(s.load(code(PROBE,{env:{AUDIT:s.audit()}})));await e.verify();const controller=new AbortController();controller.abort(new Error('caller-pre-aborted'));
    const failure=await rejected(()=>e.fetch('https://fixture.invalid/cancel',{signal:controller.signal}),'caller-pre-aborted');eq(s.root.events,[],'pre-aborted request entered worker');
    eq((await (await e.fetch('https://fixture.invalid/live')).json()).path,'/live','post-cancel fetch');eq(s.root.events.map(x=>x.value),['fetch:/live'],'cancel effects');return {failure};
  },
  async L032(s) {
    const e=s.ep(s.load(code(PROBE,{env:{AUDIT:s.audit()}})));const controller=new AbortController();
    let settled=false;const pending=e.fetch('https://fixture.invalid/hold',{signal:controller.signal}).then(async r=>{settled=true;return {resolved:true,body:await r.text()};},err=>{settled=true;return {resolved:false,error:String(err)};});
    for(let n=0;n<40 && !s.root.holdActive && !settled;n++)await tick();
    try { if(!s.root.holdActive || settled){const e=new Error('precondition: no pending held fetch witnessed within 200ms observation bound');e.blocked=true;throw e;}controller.abort(new Error('caller-during-fetch'));const result=await pending;ok(!result.resolved && result.error.includes('caller-during-fetch'),'in-flight caller abort did not reject');s.root.releaseHold();
      eq((await (await e.fetch('https://fixture.invalid/reuse')).json()).path,'/reuse','worker reuse after caller abort');return {result,events:s.root.events};
    } finally {controller.abort();s.root.releaseHold();await pending;await new Promise(r=>setTimeout(r,150));}
  },
  async L033(s) {
    const factory=()=>code();const a=s.get('released-name',factory),before=await s.ep(a).verify();s.drop(a);
    const b=s.get('released-name',factory),after=await s.ep(b).verify();ok(before.token!==after.token,'explicit worker release did not free name');return {before,after};
  },
  async L034(s) {
    const w=s.load(code());await s.ep(w).verify();s.drop(w);s.drop(w);
    const live=s.ep(s.load(code()));eq((await live.verify()).entry,'default','double release damaged subsequent anonymous load');return {doubleReleaseCompleted:true};
  },
  async L035(s) {
    const a=s.get('release-a',()=>code()),b=s.get('survivor-b',()=>code());const ea=s.ep(a),eb=s.ep(b);await ea.verify();const before=await eb.verify();s.drop(a);
    const after=await eb.verify();eq(after.token,before.token,'releasing one named worker evicted sibling');eq(after.turns,1,'sibling receiver lifetime');return {before,after};
  },
  async L036(s) {
    const w=s.load(code(facetSource('class-props'))),props={scope:'first'};const first=w.getDurableObjectClass('Gadget',{props});props.scope='second';
    const second=w.getDurableObjectClass('Gadget',{props});props.scope='third';
    const a=s.facet('class-first',()=>({class:first})),b=s.facet('class-second',()=>({class:second}));const x=await a.inspect(),y=await b.inspect();
    eq([x.props.scope,y.props.scope],['first','second'],'class handles lost binding-time props snapshots');return {x,y};
  },
  async L037(s) {
    const w=s.load(code(facetSource('owner-a')));s.root.restorePlans.set('owner-a',{worker:w,className:'Gadget',props:{owner:'a'}});s.root.restorePlans.set('owner-b',{worker:w,className:'Gadget',props:{owner:'b'}});
    const a=await s.root.ctx.restore({kind:'facet',name:'owner-a'}),b=await s.root.ctx.restore({kind:'facet',name:'owner-b'});let ca,cb;
    try {ca=await a.mint({kind:'callback',label:'same-caller-label'});cb=await b.mint({kind:'callback',label:'same-caller-label'});await a.bump();
      const x=await ca.ping('x'),y=await cb.ping('y');eq([x.owner.props.owner,y.owner.props.owner,x.owner.count,y.owner.count],['a','b',1,0],'nested restore provenance collapsed into caller labels');return {x,y};
    } finally {ca?.[Symbol.dispose]?.();cb?.[Symbol.dispose]?.();a[Symbol.dispose]?.();b[Symbol.dispose]?.();}
  },
  async L038(s) {
    const w=s.load(code(facetSource('restore-recovery')));s.root.restorePlans.set('persisted',{worker:w,className:'Gadget',props:{owner:'persisted'}});
    const facet=await s.root.ctx.restore({kind:'facet',name:'persisted'});let callback,loaded;
    try {callback=await facet.mint({kind:'callback',label:'saved'});await s.root.save('callback',callback);await facet.bump();s.abort('persisted','normal-restart');
      loaded=await s.root.ctx.storage.get('callback');const value=await loaded.ping('after-abort');eq([value.params.label,value.owner.props.owner,value.owner.count],['saved','persisted',1],'persisted nested callback did not reconstruct correct facet');return value;
    } finally {loaded?.[Symbol.dispose]?.();callback?.[Symbol.dispose]?.();facet[Symbol.dispose]?.();}
  },
  async L039(s) {
    const w=s.load(code(facetSource('callback-error')));s.root.restorePlans.set('no-replay',{worker:w,className:'Gadget',props:{owner:'no-replay'}});
    const facet=await s.root.ctx.restore({kind:'facet',name:'no-replay'});let callback;
    try {callback=await facet.mint({kind:'callback',label:'once'});const failure=await rejected(()=>callback.effectThenThrow(),'callback-after-effect');
      const state=await facet.inspect();eq(state.count,1,'persistent callback retried after executing side effect');eq((await callback.ping('healthy')).owner.count,1,'callback cannot recover after application failure');return {failure,state};
    } finally {callback?.[Symbol.dispose]?.();facet[Symbol.dispose]?.();}
  },
  async L040(s) {
    const w=s.load(code(facetSource('restore-params')));s.root.restorePlans.set('params',{worker:w,className:'Gadget',props:{owner:'params'}});
    const facet=await s.root.ctx.restore({kind:'facet',name:'params'});let callback,loaded;
    try {const params={kind:'callback',nested:{label:'captured'}};callback=await facet.mintThenMutate(params);params.nested.label='changed';await s.root.save('params-callback',callback);s.abort('params');
      loaded=await s.root.ctx.storage.get('params-callback');const value=await loaded.ping('restored');eq(value.params,{kind:'callback',nested:{label:'captured'}},'restore parameter snapshot changed during reconstruction');return value;
    } finally {loaded?.[Symbol.dispose]?.();callback?.[Symbol.dispose]?.();facet[Symbol.dispose]?.();}
  }
};
