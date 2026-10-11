import {GRAPHS} from './graphs.mjs';
export const ok=(condition,message)=>{if(!condition)throw new Error(message);};
export const eq=(actual,expected,label)=>ok(JSON.stringify(actual)===JSON.stringify(expected),label+': '+JSON.stringify({actual,expected}));
export async function reject(p,marker){try{await p;}catch(error){const text=String(error);ok(text.includes(marker),'unexpected rejection: '+text);return text;}throw new Error('expected rejection: '+marker);}
const events=(v)=>v.events;
function once(list,item){eq(list.filter(x=>x===item).length,1,item+' once');}
export const cases={
 async M001(s){
  const e=await s.ready(GRAPHS.M001);const a=s.start(e,'probe'),b=s.start(e,'probe');const rows=await Promise.all([a.promise,b.promise]);
  eq(rows.map(x=>x.left).sort((x,y)=>x-y),[41,42],'shared diamond state across two issued callers');for(const row of rows)eq(row.right,row.left+1,'branch shares leaf object');
  for(const row of rows)eq(row.state.events,['leaf','left','right','main'],'dependency-before-importer evaluation exactly once');return {rows,dispatch:[a.id,b.id]};
 },
 async M002(s){
  const e=await s.ready(GRAPHS.M002);const a=s.start(e,'write');const held=await s.held(e,['write'],[a.id]);eq(await s.call(e,'read'),[1,1],'both imported bindings before write');
  await e.release('write');eq(await a.promise,9,'writer publishes');eq(await s.call(e,'read'),[9,9],'reexport and independent observer remain live');return {held,final:await e.state()};
 },
 async M003(s){
  const e=await s.ready(GRAPHS.M003);eq(await s.call(e,'probe'),{original:1,current:1,seen:1,same:true},'initial default expression');
  eq(await s.call(e,'replace'),{original:1,current:2,seen:2,same:false},'named reassignment updates observer without rebinding default expression');
  const rows=await Promise.all([s.call(e,'probe'),s.call(e,'probe')]);for(const row of rows)eq(row,{original:1,current:2,seen:2,same:false},'post-reassignment readers');return {rows};
 },
 async M004(s){
  const e=await s.ready(GRAPHS.M004);eq(await s.call(e,'probe'),[1,10,1],'same basenames resolve from distinct static referrers');
  eq(await s.call(e,'add'),[2,10,2],'left import identity shared with direct path while right stays separate');eq(await s.call(e,'probe'),[2,10,2],'routing persists');return await e.state();
 },
 async M005(s){
  const e=await s.ready(GRAPHS.M005);eq(await s.call(e,'probe'),[3,2],'deferred cycle reads initialized bindings');eq(await s.call(e,'change'),[3,7],'cycle retains live edge after reassignment');
  const values=await Promise.all([s.call(e,'probe'),s.call(e,'probe')]);for(const value of values)eq(value,[3,7],'cycle after concurrent issuance');return {values};
 },
 async M006(s){
  const bad=s.open(GRAPHS.M006),good=await s.ready(GRAPHS.M005);const failure=s.start(bad,'probe');
  const error=await reject(failure.promise,'before initialization');eq(await s.call(good,'change'),[3,7],'failed eager cycle does not poison valid deferred cycle in another graph');return {error,recipientCount:2};
 },
 async M007(s){
  const e=await s.ready(GRAPHS.M007),a=s.start(e,'lazy'),b=s.start(e,'lazy');const held=await s.held(e,['lazy'],[a.id,b.id]);eq(held.events,['lazy-start','hold:lazy'],'same lazy module starts once while both actual invocations wait');
  await e.release('lazy');const rows=await Promise.all([a.promise,b.promise]);for(const row of rows)eq(row,{value:17,events:['lazy-start','hold:lazy','release:lazy','lazy-ready']},'both callers see terminal initialization');return {held,rows};
 },
 async M008(s){
  const e=await s.ready(GRAPHS.M008);eq(await s.call(e,'read'),0,'static import initial state');const rows=await Promise.all([s.call(e,'mutate'),s.call(e,'mutate')]);
  eq(rows.map(x=>x.n).sort((x,y)=>x-y),[1,2],'one state under concurrent dynamic imports');ok(rows.every(x=>x.same),'static and dynamic namespace identity diverged');eq(await s.call(e,'read'),2,'static reader sees both updates');return {rows};
 },
 async M009(s){
  const e=await s.ready(GRAPHS.M009);eq(await s.call(e,'read'),0,'leaf precondition');const a=s.start(e,'broken'),b=s.start(e,'good');const error=await reject(a.promise,'planned:M009:after-leaf');await b.promise;
  eq(await s.call(e,'good'),1,'successfully evaluated dependency survives dependent throw');await reject(s.call(e,'broken'),'planned:M009:after-leaf');eq(await s.call(e,'read'),1,'failed dependent is not reevaluated and effect is not repeated');return {error,state:await e.state()};
 },
 async M010(s){
  const e=await s.ready(GRAPHS.M010);let error;try{await s.call(e,'broken');throw new Error('missing planned link failure');}catch(caught){error=String(caught);ok(/conflicting star exports|ambiguous|does not provide an export named.*value/i.test(error),'wrong ambiguity failure: '+error);}
  eq(await s.call(e,'good'),4,'ambiguous consumer does not poison source module');eq((await e.state()).pending,[],'no initializer pending after link failure');return {error};
 },
 async M011(s){
  const e=await s.ready(GRAPHS.M011),a=s.start(e,'lazy'),b=s.start(e,'lazy');const held=await s.held(e,['failure'],[a.id,b.id]);eq(held.events,['failing-start','hold:failure'],'one suspended failing initializer');
  await e.release('failure');const errors=await Promise.all([reject(a.promise,'planned:M011:lazy'),reject(b.promise,'planned:M011:lazy')]);
  const final=await e.state();eq(final.events,['failing-start','hold:failure','release:failure','failing-throw'],'one throw transition delivered to both waiting invocations');eq(final.active,[],'both receivers settled');return {held,errors,final};
 },
 async M012(s){
  const e=await s.ready(GRAPHS.M012),left=s.start(e,'left'),right=s.start(e,'right');const held=await s.held(e,['shared'],[left.id,right.id]);eq(held.events,['shared-start','hold:shared'],'diamond children share one pending dependency');
  await e.release('shared');const values=await Promise.all([left.promise,right.promise]);eq(values.map(x=>x.side),['left','right'],'branch receipts');eq(values.map(x=>x.n).sort(),[1,2],'branches share leaf instance');
  const final=await e.state();for(const key of ['shared-start','shared-ready','left-ready','right-ready'])once(final.events,key);ok(final.events.indexOf('shared-ready')<final.events.indexOf('left-ready')&&final.events.indexOf('shared-ready')<final.events.indexOf('right-ready'),'parent evaluated before awaited leaf');return {held,values,final};
 },
 async M013(s){
  const e=await s.ready(GRAPHS.M013),left=s.start(e,'left'),right=s.start(e,'right');const held=await s.held(e,['left','right'],[left.id,right.id]);
  await e.release('right');eq(await right.promise,'right','right branch completes independently');const middle=await s.held(e,['left'],[left.id]);ok(!middle.active.includes(right.id),'settled right invocation still active');ok(!middle.events.includes('left-ready'),'held left branch published');
  await e.release('left');eq(await left.promise,'left','left branch resumes');return {held,middle,final:await e.state()};
 },
 async M014(s){
  const left=await s.ready(GRAPHS.M014left),right=await s.ready(GRAPHS.M014right);const a=s.start(left,'lazy'),b=s.start(right,'lazy');const before=[await s.held(left,['same'],[a.id]),await s.held(right,['same'],[b.id])];
  await right.release('same');eq(await b.promise,11,'right graph initialized its own state');const middle=await s.held(left,['same'],[a.id]);eq(await s.call(left,'read'),1,'left state unmodified by same-named right graph');
  await left.release('same');eq(await a.promise,2,'left graph resolves independently');eq(await s.call(right,'read'),11,'left release did not alter right');return {before,middle,recipientCount:2};
 },
 async M015(s){
  const bad=await s.ready(GRAPHS.M015bad),good=await s.ready(GRAPHS.M015good);const a=s.start(bad,'lazy'),b=s.start(good,'lazy');const before=[await s.held(bad,['same'],[a.id]),await s.held(good,['same'],[b.id])];
  await bad.release('same');const error=await reject(a.promise,'planned:M015:bad');const middle=await s.held(good,['same'],[b.id]);eq(middle.events,['hold:same'],'other graph untouched by rejection');
  await good.release('same');eq(await b.promise,77,'unaffected initializer completes');eq((await bad.state()).events,['hold:same','release:same','bad-throw'],'failed graph remains inspectable');return {before,middle,error,recipientCount:2};
 },
 async M016(s){
  const e=await s.ready(GRAPHS.M016);eq(await s.call(e,'probe'),{same:true,n:2},'nested dynamic referrer canonicalizes to root module');eq(await s.call(e,'add'),{same:true,n:3},'alias mutation reaches direct import');
  const rows=await Promise.all([s.call(e,'probe'),s.call(e,'probe')]);for(const row of rows)eq(row,{same:true,n:3},'dynamic alias remains cached identity');return {rows};
 },
 async M017(s){
  const e=await s.ready(GRAPHS.M017),a=s.start(e,'lazy'),b=s.start(e,'lazy');const held=await s.held(e,['recover'],[a.id,b.id]);await e.release('recover');
  eq(await Promise.all([a.promise,b.promise]),['fallback','fallback'],'caught nested import failure fulfills recoverer namespace to both callers');eq((await e.state()).events,['hold:recover','release:recover','bad-throw','caught'],'one failure and one recovery evaluation');return {held};
 },
 async M018(s){
  const e=await s.ready(GRAPHS.M018);eq(await s.call(e,'probe'),'main-live','main evaluation has completed before back-import');const rows=await Promise.all([s.call(e,'lazy'),s.call(e,'lazy')]);eq(rows,[true,true],'lazy graph back-import resolves already evaluated main class identity');eq(await s.call(e,'probe'),'main-live','main still callable');return {rows};
 },
 async M019(s){
  const e=await s.ready(GRAPHS.M019),a=s.start(e,'lazy');const held=await s.held(e,['read'],[a.id]);eq(await s.call(e,'set',9),9,'concurrent receiver changes imported live binding while initializer is suspended');
  await e.release('read');eq(await a.promise,9,'resumed initializer reads live value after suspension');eq(await s.call(e,'set',12),12,'post-initialization mutation');eq(await s.call(e,'lazy'),9,'completed module const snapshot is stable');eq((await e.state()).events,['hold:read','release:read','read:9'],'evaluation runs once');return {held};
 },
 async M020(s){
  const e=await s.ready(GRAPHS.M020);eq(await s.call(e,'probe'),8,'explicit reexport resolves conflicting star names');eq(await s.call(e,'change'),12,'explicit selected export remains live');
  const rows=await Promise.all([s.call(e,'probe'),s.call(e,'probe')]);eq(rows,[12,12],'consumer retains selected star override');return {rows};
 },
 async M021(s){
  const e=await s.ready(GRAPHS.M021);eq(await s.call(e,'probe'),{value:'selected',events:['selected']},'unreachable supplied module not eagerly evaluated');const a=s.start(e,'optional');const error=await reject(a.promise,'planned:M021:optional');
  eq(await s.call(e,'probe'),{value:'selected',events:['selected','optional']},'selected graph survives optional module failure');await reject(s.call(e,'optional'),'planned:M021:optional');eq((await e.state()).events,['selected','optional'],'optional failed module evaluated only on first import');return {error};
 }
};
