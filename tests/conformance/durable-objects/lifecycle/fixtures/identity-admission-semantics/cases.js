// Five handwritten public-API cases; no generation or native routing hooks.
export const CASES = {
  async A201(c) {
    const name=c.run+':named', ns=c.env.RECORD;
    const named=ns.idFromName(name), again=ns.idFromName(name), parsed=ns.idFromString(named.toString());
    c.eq([named.equals(again),named.equals(parsed),parsed.equals(named)],[true,true,true],'valid named and parsed IDs compare equal');
    c.eq([named.name,parsed.name],[name,undefined],'parsed address omits optional client name metadata');
    const direct=c.own('RECORD',ns.get(named)), shortcut=c.own('RECORD',ns.getByName(name)), reopened=c.own('RECORD',ns.get(parsed));
    c.eq([direct.id.toString(),shortcut.id.toString(),reopened.id.toString()],[named.toString(),named.toString(),named.toString()],'three public helper paths identify one object');
    const first=await c.send(direct,'write',{value:'named-route'});
    const second=await c.send(shortcut,'read'), third=await c.send(reopened,'read');
    c.eq([first.value,second.value,third.value],['named-route','named-route','named-route'],'getByName and valid idFromString observe the named write');
    await c.send(reopened,'write',{value:'parsed-route'});
    c.eq((await c.send(direct,'read')).value,'parsed-route','write through parsed handle returns to original named address');
  },
  async A202(c) {
    const ns=c.env.RECORD, a=ns.newUniqueId(), b=ns.newUniqueId();
    c.eq(a.equals(b),false,'two ordinary random IDs name distinct fixture objects');
    const left=c.own('RECORD',ns.get(a)), right=c.own('RECORD',ns.get(b));
    const leftParsed=c.own('RECORD',ns.get(ns.idFromString(a.toString())));
    const rightParsed=c.own('RECORD',ns.get(ns.idFromString(b.toString())));
    c.eq([a.name,b.name,left.name,right.name],[undefined,undefined,undefined,undefined],'unique IDs and their stubs have no name metadata');
    await c.send(left,'write',{value:'unique-left'});
    c.eq((await c.send(rightParsed,'read')).value,null,'fresh independent random address has no left state');
    await c.send(right,'write',{value:'unique-right'});
    const values=await Promise.all([c.send(leftParsed,'read'),c.send(rightParsed,'read')]);
    c.eq(values.map(x=>[x.value,x.name]),[['unique-left',null],['unique-right',null]],'serialized unique addresses recover their own nameless states');
    c.eq(values.map(x=>x.objectId),[a.toString(),b.toString()],'reopened unique objects report exact minted IDs');
  },
  async A203(c) {
    const prefix=c.run+':', remaining=1024-new TextEncoder().encode(prefix).length;
    const boundary=prefix+'é'.repeat(Math.floor(remaining/2))+(remaining%2?'x':'');
    const names=[boundary,boundary+'a',boundary+'b'], ns=c.env.RECORD;
    c.eq(names.map(n=>new TextEncoder().encode(n).length),[1024,1025,1025],'one exact UTF-8 metadata boundary with two distinct full-name suffixes');
    const ids=names.map(n=>ns.idFromName(n)), stubs=ids.map(id=>c.own('RECORD',ns.get(id)));
    c.eq([ids[0].equals(ids[1]),ids[1].equals(ids[2])],[false,false],'suppressed display metadata never truncates the routing name');
    for(let i=0;i<stubs.length;i++) await c.send(stubs[i],'write',{value:['boundary','suffix-a','suffix-b'][i]});
    const rows=[];
    for(const name of names) rows.push(await c.send(c.own('RECORD',ns.getByName(name)),'read'));
    c.eq(rows.map(x=>x.name),[boundary,null,null],'object name metadata follows the byte boundary rather than JavaScript character count');
    c.eq(rows.map(x=>x.value),['boundary','suffix-a','suffix-b'],'both long names readdress independent state using their entire name');
    c.eq(rows.map(x=>x.objectId),ids.map(String),'all readdressed objects report exact original IDs');
    c.eq(stubs.map(s=>s.name),names,'client stub retains the complete supplied name despite server metadata cutoff');
  },
  async A204(c) {
    const control=c.control(), target=c.own('INIT',c.env.INIT.getByName(c.run));
    const first=c.start(target,'read',{request:'first'});
    const held=await c.held(control);
    c.eq(held.targetId,target.id.toString(),'constructor hold belongs to the requested live target');
    const second=c.start(target,'read',{request:'second'});
    const peer=c.own('RECORD',c.env.RECORD.getByName(c.run+':peer'));
    c.eq((await c.send(peer,'write',{value:'peer-before-release'})).value,'peer-before-release','an independent ordinary root completes while constructor admission is closed');
    const before=await c.send(control,'snapshot');c.requireSchedule(before);
    c.eq([before.phase,before.entries.length,first.settled,second.settled],['held',0,false,false],'both incoming reads remain unadmitted at the witnessed constructor hold');
    await c.send(control,'release');
    const results=await Promise.all([first.promise,second.promise]);c.requireResults(results);
    c.eq(results.map(x=>[x.value,x.ready,x.explicitRelease]),[['initialized',true,true],['initialized',true,true]],'first and queued requests see the fully completed successful initialization');
    const after=await c.send(control,'snapshot');
    c.eq(after.entries.map(x=>x.request).sort(),['first','second'],'two distinct request handlers actually entered');
    c.eq(after.entries.every(x=>x.afterRelease&&x.ready&&x.targetId===target.id.toString()),true,'every target admission follows explicit release and completed initialization');
    c.eq(after.fallbackUsed,false,'no fallback timer supplied constructor completion');
  },
  async A205(c) {
    const control=c.control(), target=c.own('EVENT',c.env.EVENT.getByName(c.run));
    c.eq((await c.send(target,'seed')).value,'seed','ordinary target is initialized before the request gate');
    const writer=c.start(target,'block');
    const held=await c.held(control);
    c.eq(held.targetId,target.id.toString(),'request hold belongs to the already live target');
    const reader=c.start(target,'read',{request:'reader'});
    const peer=c.own('EVENT',c.env.EVENT.getByName(c.run+':peer'));
    c.eq((await c.send(peer,'seed')).value,'seed','a second root of the same class remains serviceable during the live request block');
    const before=await c.send(control,'snapshot');c.requireSchedule(before);
    c.eq([before.phase,before.entries.length,writer.settled,reader.settled],['held',0,false,false],'reader does not enter while the successful critical section awaits control');
    await c.send(control,'release');
    const results=await Promise.all([writer.promise,reader.promise]);c.requireResults(results);
    c.eq(results.map(x=>[x.value,x.explicitRelease]),[['committed',true],['committed',true]],'reader observes the terminal write after ordinary gate release');
    const after=await c.send(control,'snapshot');
    c.eq(after.entries.map(x=>[x.request,x.afterRelease,x.ready,x.targetId]),[['reader',true,true,target.id.toString()]],'actual reader admission is recorded after release with terminal local state');
    c.eq(after.fallbackUsed,false,'no fallback timer supplied request completion');
  },
};
