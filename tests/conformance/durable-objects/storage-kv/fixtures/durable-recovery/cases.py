"""22 manually chosen bounded concurrent recovery traces, not a parameter product."""
def check(ok,detail):
    if not ok:raise AssertionError(detail)

def operations(kind, count=6, gate='go', prefix='w', **extra):
    return [('apply',dict(request=f'{prefix}{i}',op=f'{prefix}{i}',kind=kind,gate=gate,**extra)) for i in range(count)]
def staged(d,root,ops):
    cohort=d.batch(root,ops);d.waiting(root,[args['request'] for _,args in ops]);return cohort
def opened(d,root,ops,gates=None):
    if gates is None:gates=sorted({args.get('gate','') for _,args in ops}-{''})
    cohort=staged(d,root,ops);release=d.release(root,list(gates));rows=d.finish(cohort);d.finish(release);return rows
def ledger(snapshot):return {r['op']:r for r in snapshot['ledger']}
def balance(snapshot,name):return next(r['balance'] for r in snapshot['accounts'] if r['name']==name)
def exact(snapshot,expected):check(set(ledger(snapshot))==set(expected),{'expected':sorted(expected),'actual':snapshot})
def consistent(snapshot):
    check(balance(snapshot,'a')+balance(snapshot,'b')==2000,'transfer conservation violated')
    for row in snapshot['pairs']:check(row['left_value']==-row['right_value'],'torn pair row')
    pair_ids={x['op'] for x in snapshot['pairs']};ledger_pairs={x['op'] for x in snapshot['ledger'] if x['kind']=='pair'}
    check(pair_ids==ledger_pairs,'pair/ledger atomicity violated')
def durable_same(d,root,snapshot,all_nodes=True):
    d.restart([root],all_nodes=all_nodes);after=d.snapshot(root);check(after==snapshot,{'pre_restart':snapshot,'post_restart':after});consistent(after);return after
def seed(d,root):
    d.op(root,'apply',{'request':'prefix','op':'prefix','kind':'append','value':7})
    return d.snapshot(root)
def recovery(d,root):
    value=d.op(root,'apply',{'request':'recovery','op':'recovery','kind':'append','value':9})
    check(value['op']=='recovery' and value['changed'],'same-root recovery write failed')
    return d.snapshot(root)
def rejected_or_pending(d,cohort):
    records=d.records(cohort);check(all(x.get('status')!=200 for x in records.values()),'store failure acknowledged unproven write');return records

def D001(d):
    root=d.root('append');rows=opened(d,root,operations('append'))
    snapshot=d.snapshot(root);exact(snapshot,[f'w{i}' for i in range(6)])
    check(all(r['body']['changed'] for r in rows),'missing acknowledged insert')
    return {'acknowledged':rows,'restored':durable_same(d,root,snapshot)}

def D002(d):
    root=d.root('counter');rows=opened(d,root,operations('increment',8))
    snapshot=d.snapshot(root);exact(snapshot,[f'w{i}' for i in range(8)]);check(balance(snapshot,'count')==8,'lost concurrent increment')
    return {'acknowledged':rows,'restored':durable_same(d,root,snapshot)}

def D003(d):
    root=d.root('transfer')
    writes=operations('transfer',6,value=7)
    reads=[('read',{'request':f'r{i}','gate':'go'}) for i in range(6)]
    rows=opened(d,root,writes+reads)
    for row in rows[6:]:
        read=row['body'];consistent(read);entries=ledger(read)
        check(set(entries).issubset({f'w{i}' for i in range(6)}),'reader transfer ledger scope')
        check(all(x['kind']=='transfer' and x['value']==7 for x in entries.values()),'reader transfer ledger values')
        check(balance(read,'a')==1000-7*len(entries) and balance(read,'b')==1000+7*len(entries),'reader transfer ledger/balance tear')
    snapshot=d.snapshot(root);exact(snapshot,[f'w{i}' for i in range(6)]);check(all(x['kind']=='transfer' and x['value']==7 for x in snapshot['ledger']),'transfer ledger values differ');check(balance(snapshot,'a')==958 and balance(snapshot,'b')==1042,'transfer total mismatch')
    return {'read_snapshots':rows[6:],'restored':durable_same(d,root,snapshot,False)}

def D004(d):
    root=d.root('dedup');ops=operations('dedup',8)
    for _,args in ops:args['op']='one-logical-operation';args['value']=3
    rows=opened(d,root,ops);check(sum(r['body']['changed'] for r in rows)==1,'duplicate application key applied more than once')
    snapshot=d.snapshot(root);exact(snapshot,['one-logical-operation']);check(balance(snapshot,'count')==3,'duplicate effect')
    return {'receipts':rows,'restored':durable_same(d,root,snapshot)}

def D005(d):
    root=d.root('compare-and-swap');rows=opened(d,root,operations('cas',8))
    winners=[r['body']['op'] for r in rows if r['body']['changed']];check(len(winners)==1,'CAS needs exactly one winner')
    snapshot=d.snapshot(root);exact(snapshot,[f'w{i}' for i in range(8)])
    check(snapshot['documents']==[{'name':'cas','version':1,'value':winners[0]}],'winner/value mismatch')
    return {'winner':winners[0],'restored':durable_same(d,root,snapshot)}

def D006(d):
    root=d.root('delete-insert')
    for i in range(3):d.op(root,'apply',{'request':f's{i}','op':f's{i}','kind':'document','key':f'old{i}'})
    ops=[('apply',{'request':f'd{i}','op':f'd{i}','kind':'delete','key':f'old{i}','gate':'go'}) for i in range(3)]
    ops += [('apply',{'request':f'n{i}','op':f'n{i}','kind':'document','key':f'new{i}','gate':'go'}) for i in range(3)]
    ops += [('read',{'request':f'r{i}','gate':'go'}) for i in range(4)]
    rows=opened(d,root,ops);snapshot=d.snapshot(root)
    expected_ops={f'{kind}{i}' for kind in ('s','d','n') for i in range(3)};exact(snapshot,expected_ops)
    check(snapshot['ledger']==[{'op':name,'kind':'delete' if name.startswith('d') else 'document','value':1} for name in sorted(expected_ops)],'exact final document ledger contents differ')
    expected_documents=[{'name':'cas','version':0,'value':'initial'}]+[{'name':f'new{i}','version':1,'value':f'n{i}'} for i in range(3)]
    check(snapshot['documents']==expected_documents,'exact delete/insert document contents differ')
    for receipt in rows[6:]:
        read=receipt['body'];entries=ledger(read);documents={x['name']:x for x in read['documents']}
        check({f's{i}' for i in range(3)}.issubset(entries) and set(entries).issubset(expected_ops),'reader ledger scope')
        check(set(documents).issubset({'cas',*[f'old{i}' for i in range(3)],*[f'new{i}' for i in range(3)]}),'reader saw phantom document')
        check(documents['cas']=={'name':'cas','version':0,'value':'initial'},'reader changed fixed document')
        for i in range(3):
            check((f'old{i}' not in documents)==(f'd{i}' in entries),'delete ledger/document tear')
            check((f'new{i}' in documents)==(f'n{i}' in entries),'insert ledger/document tear')
            if f'old{i}' in documents:check(documents[f'old{i}']=={'name':f'old{i}','version':1,'value':f's{i}'},'old document contents')
            if f'new{i}' in documents:check(documents[f'new{i}']=={'name':f'new{i}','version':1,'value':f'n{i}'},'new document contents')
        for name,entry in entries.items():check(entry=={'op':name,'kind':'delete' if name.startswith('d') else 'document','value':1},'reader exact ledger values')
    return {'overlapping_reads':rows[6:],'restored':durable_same(d,root,snapshot)}

def D007(d):
    root=d.root('rollback-neighbors');ops=operations('append',4,prefix='good')+operations('rollback',4,prefix='bad')
    rows=opened(d,root,ops);snapshot=d.snapshot(root);exact(snapshot,[f'good{i}' for i in range(4)])
    check(all(x['body']['rolledBack'] for x in rows[4:]) and balance(snapshot,'count')==0,'rollback escaped or receipt missing')
    return {'receipts':rows,'restored':durable_same(d,root,snapshot)}

def D008(d):
    root=d.root('nested-savepoint');ops=operations('nested',6,value=2)+[('read',{'request':'reader','gate':'go'})]
    rows=opened(d,root,ops);snapshot=d.snapshot(root)
    exact(snapshot,[f'w{i}:{suffix}' for i in range(6) for suffix in ('outer','after')]);check(balance(snapshot,'count')==12,'inner rollback corrupted outer state')
    check(all(not x['op'].endswith(':inner') for x in rows[-1]['body']['ledger']),'reader saw rolled-back inner rows')
    return {'reader':rows[-1],'restored':durable_same(d,root,snapshot)}

def D009(d):
    root=d.root('constraint-error');ops=operations('constraint',4,prefix='bad')+operations('transfer',4,prefix='good',value=5)
    rows=opened(d,root,ops);snapshot=d.snapshot(root);exact(snapshot,[f'good{i}' for i in range(4)])
    check(all(x['body']['rolledBack'] for x in rows[:4]),'constraint cohort not rolled back')
    check(balance(snapshot,'count')==0 and balance(snapshot,'a')==980 and balance(snapshot,'b')==1020,'constraint error contaminated sibling transactions')
    return {'receipts':rows,'restored':durable_same(d,root,snapshot,False)}

def D010(d):
    root=d.root('atomic-readers');writers=staged(d,root,operations('pair',6,value=11))
    since=len(d.store()['events']);d.control('hold_write');release=d.release(root,['go']);d.store_event('write_held',since)
    readers=d.batch(root,[('read',{'request':f'r{i}'}) for i in range(6)])
    d.logged(root,'READ',[f'r{i}' for i in range(6)]);d.pending(writers,readers);d.control('release');write_rows=d.finish(writers);read_rows=d.finish(readers);d.finish(release)
    for row in read_rows:consistent(row['body'])
    snapshot=d.snapshot(root);exact(snapshot,[f'w{i}' for i in range(6)]);consistent(snapshot)
    return {'writers':write_rows,'readers':read_rows,'restored':durable_same(d,root,snapshot)}

def D011(d):
    root=d.root('persisted-ack-held');writers=staged(d,root,operations('increment',6))
    since=len(d.store()['events']);d.control('hold_ack');release=d.release(root,['go']);state=d.store_event('ack_held',since)
    readers=d.batch(root,[('read',{'request':f'r{i}'}) for i in range(4)])
    d.logged(root,'READ',[f'r{i}' for i in range(4)]);d.pending(writers,readers)
    check(any(e['kind']=='put_persisted' and e['index']>=since for e in state['events']),'ack hold lacks persisted-write witness')
    d.control('release');rows=d.finish(writers);reads=d.finish(readers);d.finish(release)
    snapshot=d.snapshot(root);check(balance(snapshot,'count')==6,'released writes missing')
    return {'receipts':rows,'readers':reads,'restored':durable_same(d,root,snapshot)}

def D012(d):
    root=d.root('store-failure');prefix=seed(d,root);writers=staged(d,root,operations('pair',6,value=3))
    since=len(d.store()['events']);d.control('fail');release=d.release(root,['go']);d.store_event('put_failed',since)
    before_release=rejected_or_pending(d,writers);d.control('release');rows=d.finish(writers,False);d.finish(release,False)
    snapshot=recovery(d,root);consistent(snapshot)
    acknowledged={r['body']['op'] for r in rows if r.get('status')==200}
    check(acknowledged.issubset(ledger(snapshot)) and {'prefix','recovery'}.issubset(ledger(snapshot)),'acknowledged data missing after storage recovery')
    check(set(ledger(snapshot)).issubset({'prefix','recovery',*[f'w{i}' for i in range(6)]}),'unexpected writes')
    return {'pre_failure':prefix,'before_release':before_release,'ambiguous_receipts':rows,'restored':durable_same(d,root,snapshot)}

def D013(d):
    dirty=d.root('dirty',1);clean=d.root('clean',2);clean_snapshot=seed(d,clean)
    writers=staged(d,dirty,operations('append',6));since=len(d.store()['events']);d.control('fail');release=d.release(dirty,['go']);d.store_event('put_failed',since)
    independent=d.batch(clean,[('read',{'request':f'clean{i}'}) for i in range(4)])
    reads=d.finish(independent);check(all(r['body']==clean_snapshot for r in reads),'unrelated clean root blocked or changed under failing writer')
    rejected_or_pending(d,writers);d.control('release');d.finish(writers,False);d.finish(release,False)
    dirty_snapshot=recovery(d,dirty);d.restart([dirty,clean]);check(d.snapshot(clean)==clean_snapshot,'unrelated persisted root changed on recovery')
    check(d.snapshot(dirty)==dirty_snapshot,'dirty root acknowledged recovery lost')
    return {'clean_reads_during_fault':reads,'clean_restored':d.snapshot(clean),'dirty_restored':d.snapshot(dirty)}

def D014(d):
    root=d.root('earlier-proof');first=opened(d,root,operations('increment',4,gate='older',prefix='old'))
    baseline=d.snapshot(root);check(balance(baseline,'count')==4,'older cohort not acknowledged')
    later=staged(d,root,operations('increment',4,gate='newer',prefix='new'))
    since=len(d.store()['events']);d.control('hold_write');release=d.release(root,['newer']);d.store_event('write_held',since)
    followers=d.batch(root,[('read',{'request':f'after{i}'}) for i in range(4)])
    d.logged(root,'READ',[f'after{i}' for i in range(4)]);d.pending(later,followers);d.control('release');second=d.finish(later);reads=d.finish(followers);d.finish(release)
    snapshot=d.snapshot(root);check(balance(snapshot,'count')==8,'old proof released or lost the newer cohort')
    check(all(balance(r['body'],'count')>=4 for r in reads),'reader regressed below acknowledged prefix')
    return {'older_acknowledged':first,'newer_acknowledged':second,'restored':durable_same(d,root,snapshot)}

def D015(d):
    root=d.root('ambiguous-dedup');seed(d,root);writers=staged(d,root,operations('dedup',6))
    since=len(d.store()['events']);d.control('hold_ack');release=d.release(root,['go']);d.store_event('ack_held',since);d.pending(writers)
    d.restart([root],all_nodes=False,release_store_after_stop=True)
    original=d.finish(writers,False);d.finish(release,False)
    # An explicit application retry using stable operation IDs, never raw transport replay.
    retried=opened(d,root,operations('dedup',6,gate='retry'))
    snapshot=d.snapshot(root);exact(snapshot,['prefix',*[f'w{i}' for i in range(6)]]);check(balance(snapshot,'count')==6,'ambiguous acknowledgement duplicated application effect')
    return {'original_receipts':original,'retry_receipts':retried,'final':snapshot}

def D016(d):
    root=d.root('prepersist-crash');prefix=seed(d,root);writers=staged(d,root,operations('pair',6,value=4))
    since=len(d.store()['events']);d.control('hold_write');release=d.release(root,['go']);state=d.store_event('write_held',since);d.pending(writers)
    held={x['key'] for x in state['events'] if x['kind']=='write_held' and x['index']>=since}
    check(not any(x['kind']=='put_persisted' and x['key'] in held and x['index']>=since for x in state['events']),'write was already persisted before pre-persist crash')
    d.restart([root],all_nodes=True,release_store_after_stop=True)
    receipts=d.finish(writers,False);d.finish(release,False);snapshot=recovery(d,root);consistent(snapshot)
    check(ledger(snapshot)['prefix']==ledger(prefix)['prefix'],'previous acknowledged prefix lost')
    for row in receipts:
        if row.get('status')==200:check(row['body']['op'] in ledger(snapshot),'acknowledged raced write lost')
    check(set(ledger(snapshot)).issubset({'prefix','recovery',*[f'w{i}' for i in range(6)]}),'phantom recovered rows')
    return {'ambiguous_original_receipts':receipts,'final':snapshot}

def D017(d):
    root=d.root('egress-proof');writers=staged(d,root,operations('append',6,egress=True));state=d.store();effects=len(state['effects']);since=len(state['events'])
    d.control('hold_write');release=d.release(root,['go']);d.store_event('write_held',since);d.logged(root,'SQL',[f'w{i}' for i in range(6)]);d.pending(writers)
    check(len(d.store()['effects'])==effects,'outbound HTTP side effect escaped unproven SQL')
    d.control('release');rows=d.finish(writers);d.finish(release);state=d.store();import json
    actual=[json.loads(x) for x in state['effects'][effects:]];check(sorted(x['op'] for x in actual)==[f'w{i}' for i in range(6)],'egress missing or duplicated')
    snapshot=d.snapshot(root);exact(snapshot,[f'w{i}' for i in range(6)])
    return {'effects':actual,'receipts':rows,'restored':durable_same(d,root,snapshot)}

def D018(d):
    root=d.root('rollback-egress');baseline=d.snapshot(root);writers=staged(d,root,operations('rollback',6,egress=True));effects=len(d.store()['effects'])
    d.control('hold_write');release=d.release(root,['go']);rows=d.finish(writers);d.finish(release)
    check(all(r['body']['rolledBack'] for r in rows),'rollback output missing');check(len(d.store()['effects'])==effects+6,'clean rollback egress falsely gated')
    d.control('release');check(d.snapshot(root)==baseline,'rolled-back SQL escaped')
    return {'receipts':rows,'restored':durable_same(d,root,baseline)}

def D019(d):
    root=d.root('alarm-foreground');armed=d.op(root,'arm',{'op':'alarm','gate':'alarm-gate','delayMs':300})
    d.wait(lambda:d.op(root,'status')['alarmStage']=='waiting','real scheduled alarm entry')
    writers=staged(d,root,operations('increment',6));since=len(d.store()['events']);d.control('hold_ack');release=d.release(root,['go','alarm-gate']);d.store_event('ack_held',since);d.pending(writers)
    d.control('release');rows=d.finish(writers);d.finish(release)
    d.wait(lambda:'alarm' in ledger(d.snapshot(root)),'alarm committed alongside foreground cohort')
    snapshot=d.snapshot(root);exact(snapshot,['alarm',*[f'w{i}' for i in range(6)]]);check(balance(snapshot,'count')==6,'alarm lost foreground updates')
    return {'scheduled':armed,'foreground_receipts':rows,'restored':durable_same(d,root,snapshot)}

def D020(d):
    root=d.root('cold-alarm');armed=d.op(root,'arm',{'op':'cold-alarm','delayMs':90000})
    rows=opened(d,root,operations('increment',6));before=d.snapshot(root);d.prerequisite('cold-alarm' not in ledger(before),'alarm precondition elapsed before crash')
    d.restart([root]);d.wait(lambda:'cold-alarm' in ledger(d.snapshot(root)),'scheduled alarm recovered through cold heap',timeout=135)
    snapshot=d.snapshot(root);exact(snapshot,['cold-alarm',*[f'w{i}' for i in range(6)]]);check(balance(snapshot,'count')==6,'cold alarm recovery changed foreground data')
    return {'scheduled':armed,'acknowledged':rows,'restored_after_alarm':snapshot}

def D021(d):
    root=d.root('prewrite-owner-loss');prefix=seed(d,root);writers=staged(d,root,operations('increment',6,gate='never-released'))
    d.restart([root],all_nodes=False);rows=d.finish(writers,False)
    check(all(r.get('status')!=200 for r in rows),'prewrite queued call acknowledged after owner loss')
    check(d.snapshot(root)==prefix,'never-released cohort mutated restored state')
    after=recovery(d,root);exact(after,['prefix','recovery'])
    return {'interrupted_receipts':rows,'new_owner_snapshot':after}

def D022(d):
    first=d.root('namespace-rollback',1);second=d.root('namespace-commit',2)
    a=staged(d,first,operations('rollback',6));b=staged(d,second,operations('increment',6))
    ra=d.release(first,['go']);rb=d.release(second,['go']);arows=d.finish(a);brows=d.finish(b);d.finish(ra);d.finish(rb)
    before_a=d.snapshot(first);before_b=d.snapshot(second);exact(before_a,[]);exact(before_b,[f'w{i}' for i in range(6)])
    check(balance(before_a,'count')==0 and balance(before_b,'count')==6,'same operation IDs crossed DO namespace')
    d.restart([first,second]);check(d.snapshot(first)==before_a and d.snapshot(second)==before_b,'cold restore confused same-key rollback and commit roots')
    return {'rollback_receipts':arows,'committed_receipts':brows,'restored_a':d.snapshot(first),'restored_b':d.snapshot(second)}

CASES = {'D001':D001,'D002':D002,'D003':D003,'D004':D004,'D005':D005,'D006':D006,'D007':D007,'D008':D008,'D009':D009,'D010':D010,'D011':D011,'D012':D012,'D013':D013,'D014':D014,'D015':D015,'D016':D016,'D017':D017,'D018':D018,'D019':D019,'D020':D020,'D021':D021,'D022':D022}
