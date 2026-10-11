"""Twenty-eight individually authored real-event schedules. No parameter grid."""
def check(ok, detail):
    if not ok:raise AssertionError(detail)
def entries(state):return [(e['label'],e['retry'],e['terminal']) for e in state['entries']]
def effects(state):return {e['label']:e['value'] for e in state['effects']}
def markers(state):return {m['name']:m['value'] for m in state['markers']}
def exact(state, event_rows, effect_labels, marker_values=None):
    check(entries(state)==event_rows,{'unexpected_event_history':entries(state),'expected':event_rows})
    check(effects(state)=={label:1 for label in effect_labels},'unexpected durable handler effects')
    check(markers(state)==(marker_values or {}),'unexpected foreground or rollback residue')
def arm(d,r,label,delay=1800,**spec):return d.op(r,'arm',{'label':label,'delayMs':delay,**spec})
def tx(d,r,steps,abort='none'):return d.op(r,'transaction',{'steps':steps,'abort':abort})
def observe_done(d,r,labels,timeout=20):
    state=d.settled(r,labels,timeout);return d.after_due(r,state['now'],slack=2500)
def held(d,r,label,mode='normal'):
    plan=arm(d,r,label,mode=mode,gate='handler')
    row=d.alarm_entry(r,label,terminal='entered')
    state=d.snapshot(r)
    d.prerequisite(any(a['seq']==row['seq'] and a['label']==label for a in state['active']),'native handler did not remain in intended gate')
    return plan,row
def release(d,r):return d.finish(d.release(r,['handler']))
def ensure_old_clock(d,r,due):
    state=d.snapshot(r);d.prerequisite(state['now']+500<due,'mutation schedule missed original deadline');return state

def replacement_window(d,r,label,due):
    state=d.snapshot(r)
    d.event('replacement-pre-due-window',root=r,label=label,due=due,state=state)
    d.prerequisite(state['now']+250<due and not state['active'] and not any(e['label']==label for e in state['entries']),'replacement already due/entered or old handler not settled; intended ordering unavailable')
    check(state['alarm']==due,'old handler settlement changed the still-future replacement alarm')
    return state

def A001(d):
    r=d.root('hidden-handler');plan=arm(d,r,'native-after-probe',delay=6000)
    ensure_old_clock(d,r,plan['at']);probe=d.op(r,'probeAlarm')
    row=d.alarm_entry(r,'native-after-probe',terminal='success')
    state=observe_done(d,r,['native-after-probe'])
    check(probe['rejected'] is True and probe.get('name')=='TypeError' and probe.get('remote') is True and probe.get('error')=="TypeError: 'alarm' is a reserved method and cannot be called over RPC.",'ordinary class RPC exposed reserved alarm handler')
    check(row['scheduled']==plan['at'] and row['retry']==0,'native dispatcher changed scheduled metadata')
    exact(state,[('native-after-probe',0,'success')],['native-after-probe'])
    return {'ordinary_rpc':probe,'native_entry':row,'state':state}

def A002(d):
    r=d.root('postpone');old=arm(d,r,'superseded',delay=6000);ensure_old_clock(d,r,old['at'])
    new=arm(d,r,'later',delay=14000);check(new['at']>old['at'],'postpone fixture did not move later')
    interim=d.after_due(r,old['at']);d.prerequisite(interim['now']<new['at'],'replacement deadline elapsed before old-wake observation');check(interim['entries']==[] and interim['alarm']==new['at'],'old timer fired or replacement was lost')
    d.alarm_entry(r,'later',terminal='success');state=observe_done(d,r,['later'])
    exact(state,[('later',0,'success')],['later']);return {'old':old,'new':new,'state':state}

def A003(d):
    r=d.root('advance');old=arm(d,r,'late-old',delay=12000);ensure_old_clock(d,r,old['at'])
    new=arm(d,r,'early-new',delay=1800);check(new['at']<old['at'],'advance fixture did not move earlier')
    row=d.alarm_entry(r,'early-new',terminal='success');check(row['scheduled']==new['at'],'earlier deadline not delivered')
    state=d.after_due(r,old['at']);exact(state,[('early-new',0,'success')],['early-new']);check(state['alarm'] is None,'old future wake survived early completion')
    return {'old':old,'new':new,'state':state}

def A004(d):
    r=d.root('delete-rearm');old=arm(d,r,'deleted',delay=5000);ensure_old_clock(d,r,old['at'])
    canceled=d.op(r,'cancel');check(canceled['alarm'] is None,'delete failed immediately')
    state=d.after_due(r,old['at']);exact(state,[],[])
    new=arm(d,r,'fresh-after-delete');d.alarm_entry(r,'fresh-after-delete',terminal='success');state=observe_done(d,r,['fresh-after-delete'])
    exact(state,[('fresh-after-delete',0,'success')],['fresh-after-delete']);return {'canceled':canceled,'new':new,'state':state}

def A005(d):
    r=d.root('tx-commit');result=tx(d,r,[{'op':'marker','name':'committed','value':7},{'op':'set','label':'transaction-armed','delayMs':2200}])
    check(not result['rolledBack'] and markers(result['state'])=={'committed':7},'atomic transaction did not commit')
    row=d.alarm_entry(r,'transaction-armed',terminal='success');check(row['scheduled']==result['state']['alarm'],'committed alarm deadline differs')
    state=observe_done(d,r,['transaction-armed']);exact(state,[('transaction-armed',0,'success')],['transaction-armed'],{'committed':7});return {'transaction':result,'state':state}

def A006(d):
    r=d.root('tx-set-rollback');at=d.snapshot(r)['now']+6500
    result=tx(d,r,[{'op':'marker','name':'rolled-back','value':9},{'op':'set','label':'never-committed','at':at}],abort='throw')
    check(result['rolledBack'] and result['state']['alarm'] is None,'rolled-back arm published')
    state=d.after_due(r,at);exact(state,[],[]);check(state['plans']==[],'rolled-back plan survived');return {'transaction':result,'state':state}

def A007(d):
    r=d.root('tx-overwrite-rollback');old=arm(d,r,'survivor',delay=10000);ensure_old_clock(d,r,old['at'])
    attempted=d.snapshot(r)['now']+2500
    result=tx(d,r,[{'op':'set','label':'rolled-replacement','at':attempted}],abort='throw')
    check(result['state']['alarm']==old['at'],'rollback lost original deadline')
    before=d.after_due(r,attempted);d.prerequisite(before['now']<old['at'],'original deadline elapsed before rollback exclusion observation');check(before['entries']==[],'rolled replacement fired before original')
    d.alarm_entry(r,'survivor',terminal='success');state=observe_done(d,r,['survivor']);exact(state,[('survivor',0,'success')],['survivor']);return {'old':old,'attempted':attempted,'state':state}

def A008(d):
    r=d.root('tx-delete-rollback');old=arm(d,r,'undeleted',delay=6500);ensure_old_clock(d,r,old['at'])
    result=tx(d,r,[{'op':'delete'},{'op':'marker','name':'discarded-delete','value':1}],abort='explicit')
    check(result['rolledBack'] and result['state']['alarm']==old['at'],'explicit rollback did not restore alarm')
    row=d.alarm_entry(r,'undeleted',terminal='success');check(row['scheduled']==old['at'],'restored alarm metadata changed')
    state=observe_done(d,r,['undeleted']);exact(state,[('undeleted',0,'success')],['undeleted']);return {'transaction':result,'state':state}

def A009(d):
    r=d.root('tx-delete-commit');old=arm(d,r,'canceled-atomically',delay=5000);ensure_old_clock(d,r,old['at'])
    result=tx(d,r,[{'op':'delete'},{'op':'marker','name':'deletion-committed','value':3}])
    check(not result['rolledBack'] and result['state']['alarm'] is None,'committed transaction kept alarm')
    state=d.after_due(r,old['at']);exact(state,[],[],{'deletion-committed':3});return {'transaction':result,'state':state}

def A010(d):
    r=d.root('tx-final-move');clock=d.snapshot(r)['now'];early=clock+3000;final=clock+11000
    result=tx(d,r,[{'op':'set','label':'transient','at':early},{'op':'delete'},{'op':'set','label':'final','at':final}])
    check(result['state']['alarm']==final,'final transaction schedule not published')
    interim=d.after_due(r,early);d.prerequisite(interim['now']<final,'final deadline elapsed before intermediate-wake observation');check(interim['entries']==[],'intermediate transaction alarm escaped')
    row=d.alarm_entry(r,'final',terminal='success');check(row['scheduled']==final,'final deadline changed')
    state=observe_done(d,r,['final']);exact(state,[('final',0,'success')],['final']);return {'transaction':result,'state':state}

def A011(d):
    r=d.root('nested-child-rollback');clock=d.snapshot(r)['now'];outer=clock+11000;child=clock+3000
    result=tx(d,r,[{'op':'set','label':'parent','at':outer},{'op':'nested','abort':True,'steps':[{'op':'set','label':'child-rolled','at':child},{'op':'marker','name':'child','value':1}]},{'op':'marker','name':'parent','value':2}])
    check(result['state']['alarm']==outer,'nested rollback corrupted parent alarm')
    interim=d.after_due(r,child);d.prerequisite(interim['now']<outer,'parent deadline elapsed before child-wake observation');check(interim['entries']==[],'rolled child timer escaped savepoint')
    d.alarm_entry(r,'parent',terminal='success');state=observe_done(d,r,['parent']);exact(state,[('parent',0,'success')],['parent'],{'parent':2});return {'transaction':result,'state':state}

def A012(d):
    r=d.root('nested-parent-rollback');at=d.snapshot(r)['now']+6000
    result=tx(d,r,[{'op':'nested','abort':False,'steps':[{'op':'set','label':'child-committed','at':at},{'op':'marker','name':'child-committed','value':8}]}],abort='throw')
    check(result['rolledBack'] and result['state']['alarm'] is None,'child commit escaped outer rollback')
    state=d.after_due(r,at);exact(state,[],[]);check(state['plans']==[],'nested plan leaked');return {'transaction':result,'state':state}

def A013(d):
    r=d.root('handler-visible-rearm');first=arm(d,r,'parent-event',mode='inspect-rearm',nextLabel='child-event',nextDelay=4000)
    row=d.alarm_entry(r,'parent-event',terminal='success');check(row['initial_alarm'] is None and row['after_alarm'] is not None,'handler getAlarm hide/rearm visibility differs')
    child=d.alarm_entry(r,'child-event',terminal='success');check(child['scheduled']==row['after_alarm'] and child['retry']==0 and child['initial_alarm'] is None,'new handler generation metadata differs')
    state=observe_done(d,r,['parent-event','child-event']);exact(state,[('parent-event',0,'success'),('child-event',0,'success')],['parent-event','child-event']);return {'armed':first,'state':state}

def A014(d):
    r=d.root('retry-after-write');first=arm(d,r,'retry-persistence',mode='throw-once')
    failed=d.alarm_entry(r,'retry-persistence',retry=0,terminal='failed');retry=d.alarm_entry(r,'retry-persistence',retry=1,terminal='success')
    check(failed['scheduled']==first['at'] and retry['scheduled']>failed['scheduled'],'retry was not scheduled after failure')
    check(failed['initial_alarm'] is None and retry['initial_alarm'] is None,'executing generation was visible')
    state=observe_done(d,r,['retry-persistence']);exact(state,[('retry-persistence',0,'failed'),('retry-persistence',1,'success')],['retry-persistence']);return {'first':failed,'retry':retry,'state':state}

def A015(d):
    r=d.root('retry-transaction-rollback');arm(d,r,'rolled-effect',mode='rollback-throw')
    d.alarm_entry(r,'rolled-effect',retry=0,terminal='failed');retry=d.alarm_entry(r,'rolled-effect',retry=1,terminal='success')
    state=observe_done(d,r,['rolled-effect']);exact(state,[('rolled-effect',0,'failed'),('rolled-effect',1,'success')],['rolled-effect'])
    check(retry['is_retry']==1,'failed transactional handler lost retry classification');return {'state':state}

def A016(d):
    r=d.root('failure-new-generation');arm(d,r,'failed-old',mode='rearm-throw',nextLabel='new-generation',nextDelay=7000)
    old=d.alarm_entry(r,'failed-old',terminal='failed');check(old['after_alarm'] is not None,'handler did not rearm before failure')
    replacement_window(d,r,'new-generation',old['after_alarm'])
    row=d.alarm_entry(r,'new-generation',terminal='success');check(row['scheduled']==old['after_alarm'] and row['retry']==0,'automatic retry replaced explicit rearm')
    state=observe_done(d,r,['new-generation']);exact(state,[('failed-old',0,'failed'),('new-generation',0,'success')],['new-generation']);return {'failed':old,'state':state}

def A017(d):
    r=d.root('failure-explicit-delete');arm(d,r,'delete-before-fail',mode='delete-throw')
    old=d.alarm_entry(r,'delete-before-fail',terminal='failed');check(old['after_alarm'] is None,'delete did not clear handler schedule')
    state=d.after_due(r,old['entered'],slack=6500)
    exact(state,[('delete-before-fail',0,'failed')],[]);check(state['alarm'] is None and not state['active'],'failed deleted generation retried');return {'failed':old,'state':state}

def A018(d):
    r=d.root('replace-during-success');old,entry=held(d,r,'entered-old')
    replacement=arm(d,r,'foreground-new',delay=7000);check(any(a['seq']==entry['seq'] for a in d.snapshot(r)['active']),'handler was not pending during replacement')
    release(d,r);d.alarm_entry(r,'entered-old',terminal='success');replacement_window(d,r,'foreground-new',replacement['at']);row=d.alarm_entry(r,'foreground-new',terminal='success')
    check(row['scheduled']==replacement['at'],'old completion erased newer foreground alarm')
    state=observe_done(d,r,['entered-old','foreground-new']);exact(state,[('entered-old',0,'success'),('foreground-new',0,'success')],['entered-old','foreground-new']);return {'old':old,'replacement':replacement,'state':state}

def A019(d):
    r=d.root('same-time-generation-aba');old,entry=held(d,r,'aba-old')
    replacement=d.op(r,'arm',{'label':'aba-new','at':old['at']})
    second=d.alarm_entry(r,'aba-new',terminal='success',timeout=12,optional=True)
    d.prerequisite(second is not None,'bounded re-entrant native alarm overlap unavailable; characterization cannot establish the schedule')
    state=d.snapshot(r);d.prerequisite(any(a['seq']==entry['seq'] for a in state['active']),'old invocation no longer pending when same-time replacement completed')
    release(d,r);state=observe_done(d,r,['aba-old','aba-new'])
    check(second['scheduled']==old['at'] and second['retry']==0,'same-time replacement reused old retry identity')
    exact(state,[('aba-old',0,'success'),('aba-new',0,'success')],['aba-old','aba-new']);return {'promotion':False,'same_time':replacement['at'],'state':state}

def A020(d):
    r=d.root('delete-entered-handler');old,entry=held(d,r,'already-running')
    canceled=d.op(r,'cancel');check(canceled['alarm'] is None,'concurrent delete failed')
    state=d.snapshot(r);check(any(a['seq']==entry['seq'] for a in state['active']),'delete unexpectedly canceled an entered handler')
    release(d,r);state=observe_done(d,r,['already-running'])
    exact(state,[('already-running',0,'success')],['already-running']);check(state['alarm'] is None,'old success resurrected deleted schedule');return {'old':old,'state':state}

def A021(d):
    r=d.root('replace-during-failure');old,entry=held(d,r,'failed-entered',mode='hold-throw')
    new=arm(d,r,'surviving-replacement',delay=7000);check(any(a['seq']==entry['seq'] for a in d.snapshot(r)['active']),'failure overlap gate disappeared')
    release(d,r);d.alarm_entry(r,'failed-entered',terminal='failed');replacement_window(d,r,'surviving-replacement',new['at']);row=d.alarm_entry(r,'surviving-replacement',terminal='success')
    check(row['scheduled']==new['at'] and row['retry']==0,'old failure backed off replacement generation')
    state=observe_done(d,r,['surviving-replacement']);exact(state,[('failed-entered',0,'failed'),('surviving-replacement',0,'success')],['surviving-replacement']);return {'old':old,'new':new,'state':state}

def A022(d):
    r=d.root('retry-ceiling');arm(d,r,'always-fails',mode='always-throw')
    d.alarm_entry(r,'always-fails',terminal='failed')
    def abandoned():
        state=d.snapshot(r)
        return state if len(state['entries'])>=7 and not state['active'] and state['alarm'] is None else None
    terminal=d.wait(abandoned,'six retries then alarm abandonment',timeout=170)
    state=d.after_due(r,terminal['now'],slack=5000)
    exact(state,[('always-fails',0,'failed'),('always-fails',1,'failed'),('always-fails',2,'failed'),('always-fails',3,'failed'),('always-fails',4,'failed'),('always-fails',5,'failed'),('always-fails',6,'failed')],[])
    check([e['is_retry'] for e in state['entries']]==[0,1,1,1,1,1,1],'retry flag sequence differs')
    check(all(b['scheduled']>a['scheduled'] for a,b in zip(state['entries'],state['entries'][1:])),'retry deadlines did not advance');return {'state':state}

def A023(d):
    r=d.root('failed-rolled-rearm');arm(d,r,'original-retry',mode='rollback-rearm-throw')
    first=d.alarm_entry(r,'original-retry',terminal='failed');second=d.alarm_entry(r,'original-retry',retry=1,terminal='success')
    check(first['after_alarm'] is None and second['entered']-first['entered']<30000,'rolled-back future rearm replaced automatic retry')
    state=observe_done(d,r,['original-retry']);exact(state,[('original-retry',0,'failed'),('original-retry',1,'success')],['original-retry']);return {'first':first,'retry':second,'state':state}

def A024(d):
    blocked=d.root('held-root');sibling=d.root('sibling-root',node=2);old,entry=held(d,blocked,'held-event')
    cohort=d.batch(sibling,[('foreground',{'request':'sibling-one','name':'one','value':2}),('foreground',{'request':'sibling-two','name':'two','value':3}),('foreground',{'request':'sibling-three','name':'three','value':5})])
    outcomes=d.finish(cohort);state=d.snapshot(blocked)
    d.prerequisite(any(a['seq']==entry['seq'] for a in state['active']),'held handler ended before sibling progress was established')
    check(markers(d.snapshot(sibling))=={'one':2,'three':5,'two':3},'sibling operations lost or misrouted')
    release(d,blocked);state=observe_done(d,blocked,['held-event']);exact(state,[('held-event',0,'success')],['held-event'])
    other=d.snapshot(sibling);exact(other,[],[],{'one':2,'three':5,'two':3});return {'sibling_receipts':outcomes,'held_state':state,'sibling_state':other}

def A025(d):
    r=d.root('cold-overwritten-wake');old=arm(d,r,'stale-before-crash',delay=90000);ensure_old_clock(d,r,old['at'])
    new=arm(d,r,'restored-replacement',delay=112000);d.before_due(r,old['at']);d.restart([r]);d.before_due(r,old['at'])
    interim=d.after_due(r,old['at']);d.prerequisite(interim['now']<new['at'],'replacement deadline elapsed before old-wake observation');check(interim['entries']==[] and interim['alarm']==new['at'],'cold restore resurrected overwritten wake record')
    row=d.alarm_entry(r,'restored-replacement',terminal='success',timeout=40);check(row['scheduled']==new['at'],'cold restore changed replacement deadline')
    state=observe_done(d,r,['restored-replacement']);exact(state,[('restored-replacement',0,'success')],['restored-replacement']);return {'old':old,'replacement':new,'state':state}

def A026(d):
    r=d.root('cold-rolled-delete');old=arm(d,r,'rollback-survivor',delay=90000)
    transaction=tx(d,r,[{'op':'delete'},{'op':'marker','name':'uncommitted-delete','value':4}],abort='throw')
    check(transaction['state']['alarm']==old['at'],'delete rollback changed immediate state');d.before_due(r,old['at']);d.restart([r]);restored=d.before_due(r,old['at'])
    check(restored['alarm']==old['at'] and markers(restored)=={},'cold restore used rolled-back deletion')
    d.alarm_entry(r,'rollback-survivor',terminal='success',timeout=105);state=observe_done(d,r,['rollback-survivor']);exact(state,[('rollback-survivor',0,'success')],['rollback-survivor']);return {'transaction':transaction,'restored':restored,'state':state}

def A027(d):
    r=d.root('cold-failed-replacement');arm(d,r,'failed-before-cold',mode='rearm-throw',nextLabel='cold-new-generation',nextDelay=90000)
    failed=d.alarm_entry(r,'failed-before-cold',terminal='failed');due=failed['after_alarm'];check(isinstance(due,int),'failed handler did not durably rearm')
    pre=d.snapshot(r);d.prerequisite(pre['now']+10000<due and pre['alarm']==due and not pre['active'],'failed handler replacement not settled before cold recovery')
    d.restart([r]);restored=d.snapshot(r);d.prerequisite(restored['now']<due,'replacement deadline elapsed during cold startup')
    check(restored['alarm']==due and entries(restored)==[('failed-before-cold',0,'failed')],'old failure/retry overwrote durable replacement during restore')
    row=d.alarm_entry(r,'cold-new-generation',terminal='success',timeout=105);check(row['scheduled']==due and row['retry']==0,'restored replacement inherited old retry counter')
    state=observe_done(d,r,['cold-new-generation']);exact(state,[('failed-before-cold',0,'failed'),('cold-new-generation',0,'success')],['cold-new-generation']);return {'failed':failed,'restored':restored,'state':state}

def A028(d):
    r=d.root('cold-consumed-wake');arm(d,r,'completed-before-cold');d.alarm_entry(r,'completed-before-cold',terminal='success');before=observe_done(d,r,['completed-before-cold'])
    exact(before,[('completed-before-cold',0,'success')],['completed-before-cold']);d.restart([r])
    restored=d.snapshot(r);state=d.after_due(r,restored['now'],slack=6500)
    check(state['isolate']!=before['isolate'],'cold recovery did not replace heap');check(state['alarm'] is None and not state['active'],'consumed alarm resurrected after restore')
    exact(state,[('completed-before-cold',0,'success')],['completed-before-cold']);return {'before':before,'restored':state}

CASES={'A001':A001,'A002':A002,'A003':A003,'A004':A004,'A005':A005,'A006':A006,'A007':A007,'A008':A008,'A009':A009,'A010':A010,'A011':A011,'A012':A012,'A013':A013,'A014':A014,'A015':A015,'A016':A016,'A017':A017,'A018':A018,'A019':A019,'A020':A020,'A021':A021,'A022':A022,'A023':A023,'A024':A024,'A025':A025,'A026':A026,'A027':A027,'A028':A028}
