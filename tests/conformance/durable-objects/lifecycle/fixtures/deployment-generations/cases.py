"""28 individually authored native deployment traces. No parameter-product cases."""
def check(ok,detail):
    if not ok:raise AssertionError(detail)
def initial(d,label='main',duplicate=False):
    root=d.root(label);d.op(root,'seed',{'items':[{'k':'a','value':7,'label':'alpha'},{'k':'b','value':11,'label':'alpha' if duplicate else 'beta'}]});expect(d.snapshot(root),labels=('alpha','alpha') if duplicate else ('alpha','beta'));return root
def writes(*specs,gate='go'):
    return [('apply',{'request':op,'op':op,'key':key,'delta':delta,'gate':gate}) for op,key,delta in specs]
def staged(d,root,operations):
    cohort=d.batch(root,operations);d.waiting(root,[args['request'] for _,args in operations]);return cohort
def open_jobs(d,root,operations):
    cohort=staged(d,root,operations);release=d.release(root,sorted({args.get('gate','') for _,args in operations}-{''}));rows=d.finish(cohort);d.finish(release);return rows
def receipt(rows,expected,writer):
    check([r['body']['op'] for r in rows]==list(expected),'receipt IDs differ')
    check(all(r['body']['changed'] and r['body']['writer']==writer for r in rows),'unexpected write receipt or serving version')
def expect(snapshot,ops=(),schema=1,migrations=0,labels=('alpha','beta'),notes=('legacy','legacy'),plans=(),alarms=()):
    field='units' if schema==3 else 'value';values={'a':7,'b':11}
    for _,key,delta,_ in ops:values[key]+=delta
    items=[dict(k=key,**{field:values[key]*(10 if schema==3 else 1)},label=labels[i]) for i,key in enumerate(('a','b'))]
    if schema==2:
        for i,row in enumerate(items):row['note']=notes[i]
    expected={'columns':['k',field,'label']+(['note'] if schema==2 else []),'items':items,'ops':[dict(id=op,k=key,delta=delta,writer=writer) for op,key,delta,writer in sorted(ops)],'meta':[{'k':'migrations','v':migrations},{'k':'schema','v':schema}],'indexes':[{'name':'unique_label'}] if schema==4 else [],'plans':list(plans),'alarms':list(alarms)}
    check(snapshot==expected,{'expected':expected,'actual':snapshot});return snapshot
def cold_exact(d,root,snapshot):
    restored=d.cold([root])[root];check(restored==snapshot,{'acknowledged':snapshot,'cold':restored});return restored
def migrate(d,root):
    answer=d.op(root,'migrate',{'request':'migrate'});check(answer['changed'],'migration should execute once');return answer
def alarm_window(d,root,due):
    state=d.op(root,'alarmState');d.event('alarm-window-observed',root=root,due=due,record=state);d.prerequisite(state['now']<due,'alarm timing prerequisite missed before cold deployment observation');return state
def cold_alarm(d,root,snapshot,due):
    alarm_window(d,root,due);restored=d.cold([root])[root]
    alarm_window(d,root,due)  # A legitimate alarm during a slow cold boot is BLOCKED for this pre-due schedule.
    check(restored==snapshot,{'pre_due_acknowledged':snapshot,'pre_due_cold':restored});return restored
def old_cohort(d,root):return staged(d,root,writes(('old-a','a',2),('old-b','b',3)))
def close_old(d,root,cohort):
    d.pending(cohort);release=d.release(root,['go']);rows=d.finish(cohort);d.finish(release);receipt(rows,['old-a','old-b'],'v1');return rows
OLD=[('old-a','a',2,'v1'),('old-b','b',3,'v1')]
def recover_publish(d,root):
    d.upgrade('v2-code',[root]);rows=open_jobs(d,root,writes(('recovery','a',4)));receipt(rows,['recovery'],'v2-code');return rows

def U001(d):
    root=initial(d);rows=open_jobs(d,root,writes(('before-a','a',2),('before-b','b',-1)));receipt(rows,['before-a','before-b'],'v1')
    publication=d.upgrade('v2-add',[root]);migrate(d,root);after=open_jobs(d,root,writes(('after-a','a',3),('after-b','b',1)));receipt(after,['after-a','after-b'],'v2-add')
    snapshot=expect(d.snapshot(root),[('before-a','a',2,'v1'),('before-b','b',-1,'v1'),('after-a','a',3,'v2-add'),('after-b','b',1,'v2-add')],2,1)
    return {'publication':publication,'cold':cold_exact(d,root,snapshot)}

def U002(d):
    root=initial(d);before=open_jobs(d,root,writes(('account-a','a',1),('account-b','b',2)));receipt(before,['account-a','account-b'],'v1')
    d.upgrade('v2-rebuild',[root]);migrate(d,root);after=open_jobs(d,root,writes(('units-a','a',3),('units-b','b',-2)));receipt(after,['units-a','units-b'],'v2-rebuild')
    snapshot=expect(d.snapshot(root),[('account-a','a',1,'v1'),('account-b','b',2,'v1'),('units-a','a',3,'v2-rebuild'),('units-b','b',-2,'v2-rebuild')],3,1)
    check(d.op(root,'business')==[{'k':'a','amount':110,'label':'alpha'},{'k':'b','amount':110,'label':'beta'}],'rebuild business units differ')
    return {'cold':cold_exact(d,root,snapshot)}

def U003(d):
    root=initial(d,duplicate=True);d.upgrade('v2-unique',[root]);failed=d.response(root,'migrate',{'request':'unique-fail'})
    check(failed['status']==500 and 'UNIQUE' in failed['body']['error'].upper(),'duplicate backfill must fail');expect(d.snapshot(root),labels=('alpha','alpha'))
    d.op(root,'relabel',{'key':'b','label':'beta'});migrate(d,root)
    rejected=d.response(root,'relabel',{'key':'b','label':'alpha'});check(rejected['status']==500 and 'UNIQUE' in rejected['body']['error'].upper(),'new uniqueness constraint inactive')
    snapshot=expect(d.snapshot(root),schema=4,migrations=1)
    return {'migration_error':failed,'constraint_error':rejected,'cold':cold_exact(d,root,snapshot)}

def U004(d):
    first=initial(d,'migrated');second=initial(d,'lazy');d.upgrade('v2-add',[first,second]);migrate(d,first)
    a=staged(d,first,writes(('migrated-write','a',2),gate='one'));b=staged(d,second,writes(('lazy-write','b',3),gate='two'))
    releases=[d.release(first,['one']),d.release(second,['two'])];receipt(d.finish(a),['migrated-write'],'v2-add');receipt(d.finish(b),['lazy-write'],'v2-add')
    for release in releases:d.finish(release)
    one=expect(d.snapshot(first),[('migrated-write','a',2,'v2-add')],2,1);two=expect(d.snapshot(second),[('lazy-write','b',3,'v2-add')]);restored=d.cold([first,second]);check(restored=={first:one,second:two},'per-object lazy schema state crossed')
    migrate(d,second);expect(d.snapshot(second),[('lazy-write','b',3,'v2-add')],2,1)
    return {'mixed_schema_cold':restored}

def U005(d):
    root=initial(d);d.upgrade('v2-add',[root]);ops=[('migrate',{'request':'migrate-one','gate':'schema'}),('migrate',{'request':'migrate-two','gate':'schema'}),('apply',{'request':'schema-neighbor','op':'schema-neighbor','key':'b','delta':2,'gate':'schema'})]
    rows=open_jobs(d,root,ops);check(sum(x['body']['changed'] for x in rows[:2])==1,'two concurrent migrations both applied or neither did');receipt(rows[2:],['schema-neighbor'],'v2-add')
    snapshot=expect(d.snapshot(root),[('schema-neighbor','b',2,'v2-add')],2,1)
    return {'concurrent_migrations':rows[:2],'cold':cold_exact(d,root,snapshot)}

def U006(d):
    root=initial(d);d.upgrade('v2-add',[root]);migrate(d,root);d.op(root,'note',{'key':'a','note':'keep-extension'});d.upgrade('v1',[root])
    rows=open_jobs(d,root,writes(('rollback-writer','a',2),('rollback-peer','b',-3)));receipt(rows,['rollback-writer','rollback-peer'],'v1')
    snapshot=expect(d.snapshot(root),[('rollback-writer','a',2,'v1'),('rollback-peer','b',-3,'v1')],2,1,notes=('keep-extension','legacy'))
    return {'cold_downlevel':cold_exact(d,root,snapshot)}

def U007(d):
    root=initial(d);d.upgrade('v2-rebuild',[root]);migrate(d,root);saved=expect(d.snapshot(root),schema=3,migrations=1);d.upgrade('v1',[root])
    failed=d.response(root,'business');check(failed['status']==500 and 'value' in failed['body']['error'],'downlevel access must reject incompatible field');check(d.snapshot(root)==saved,'downlevel read damaged acknowledged schema')
    d.upgrade('v2-rebuild',[root]);rows=open_jobs(d,root,writes(('repaired-a','a',1),('repaired-b','b',1)));receipt(rows,['repaired-a','repaired-b'],'v2-rebuild')
    snapshot=expect(d.snapshot(root),[('repaired-a','a',1,'v2-rebuild'),('repaired-b','b',1,'v2-rebuild')],3,1)
    return {'downlevel_rejection':failed,'cold_repaired':cold_exact(d,root,snapshot)}

def U008(d):
    root=initial(d);d.upgrade('v2-abort',[root]);failed=d.response(root,'migrate',{'request':'abort-copy-drop'})
    check(failed['status']==500 and 'planned migration abort after DROP' in failed['body']['error'],'specified DDL fault was not reached');expect(d.snapshot(root))
    d.upgrade('v2-rebuild',[root]);migrate(d,root);snapshot=expect(d.snapshot(root),schema=3,migrations=1)
    return {'transactional_ddl_abort':failed,'cold_corrective':cold_exact(d,root,snapshot)}

def U009(d):
    root=initial(d);plan=d.op(root,'arm',{'op':'new-handler','delayMs':90000});d.upgrade('v2-code',[root]);alarm_window(d,root,plan['due']);before=expect(d.snapshot(root),plans=[{'id':1,'op':plan['op'],'due':plan['due']}]);cold_alarm(d,root,before,plan['due'])
    effect=d.wait_alarm(root,'new-handler');check(effect=={'op':'new-handler','writer':'v2-code','schema_version':1,'total':18},'cold alarm did not use replacement handler')
    after=d.after_due(root,plan['due']);expect(after['snapshot'],plans=[{'id':1,'op':plan['op'],'due':plan['due']}],alarms=[effect]);check(after['alarm'] is None,'one-shot alarm still scheduled')
    return {'scheduled_by':'v1','effect':effect,'terminal':after}

def U010(d):
    root=initial(d);plan=d.op(root,'arm',{'op':'canceled','delayMs':90000});d.upgrade('v2-code',[root]);alarm_window(d,root,plan['due']);check(d.op(root,'cancelAlarm')=={'alarm':None},'replacement did not cancel alarm')
    cold_alarm(d,root,expect(d.snapshot(root)),plan['due']);after=d.after_due(root,plan['due']);expect(after['snapshot']);check(after['alarm'] is None,'canceled schedule reappeared after upgrade/cold restore')
    return {'original_schedule':plan,'past_due':after}

def U011(d):
    root=initial(d);d.op(root,'arm',{'op':'logical-once','delayMs':1000});effect=d.wait_alarm(root,'logical-once');check(effect=={'op':'logical-once','writer':'v1','schema_version':1,'total':18},'initial alarm receipt differs')
    d.upgrade('v2-code',[root]);plan=d.op(root,'arm',{'op':'logical-once','delayMs':90000});before=expect(d.snapshot(root),plans=[{'id':1,'op':plan['op'],'due':plan['due']}],alarms=[effect]);cold_alarm(d,root,before,plan['due'])
    after=d.after_due(root,plan['due']);d.alarm_completed(root,'logical-once','v2-code');expect(after['snapshot'],plans=[{'id':1,'op':plan['op'],'due':plan['due']}],alarms=[effect]);check(after['alarm'] is None,'replacement alarm never finished')
    return {'persisted_dedup_receipt':effect,'rearmed_terminal':after}

def U012(d):
    root=initial(d);plan=d.op(root,'arm',{'op':'schema-alarm','delayMs':90000});d.upgrade('v2-rebuild',[root]);migrate(d,root);alarm_window(d,root,plan['due'])
    before=expect(d.snapshot(root),schema=3,migrations=1,plans=[{'id':1,'op':plan['op'],'due':plan['due']}]);cold_alarm(d,root,before,plan['due'])
    effect=d.wait_alarm(root,'schema-alarm');check(effect=={'op':'schema-alarm','writer':'v2-rebuild','schema_version':3,'total':180},'replacement alarm used old schema or torn backfill')
    after=d.after_due(root,plan['due']);expect(after['snapshot'],schema=3,migrations=1,plans=[{'id':1,'op':plan['op'],'due':plan['due']}],alarms=[effect])
    return {'schema_aware_effect':effect,'terminal':after}

def U013(d):
    root=initial(d);pending=old_cohort(d,root);before=d.pointers();failed=d.finish_deploy(d.launch_deploy('bad-rename'),success=False)
    check('does not support these migration keys' in failed['stderr'] and 'renamed_classes' in failed['stderr'],'native unsupported-migration refusal missing');check(d.pointers()==before,'refused migration changed live deployment selector')
    rows=close_old(d,root,pending);snapshot=expect(d.snapshot(root),OLD)
    return {'native_refusal':failed,'inflight_v1_receipts':rows,'cold_original':cold_exact(d,root,snapshot)}

def U014(d):
    root=initial(d);identity=d.roots[root]['identity']['root'];d.upgrade('v2-sibling',[root]);sibling=d.root('main',namespace='sibling')
    # Same public object name; the driver uses distinct internal handles for the two class namespaces.
    check(d.roots[sibling]['identity']['root']!=identity,'new class aliased original class')
    d.op(sibling,'seed',{'items':[{'k':'a','value':7,'label':'alpha'},{'k':'b','value':11,'label':'beta'}]})
    first=staged(d,root,writes(('class-root','a',2),gate='root'));second=staged(d,sibling,writes(('class-sibling','a',5),gate='sibling'))
    releases=[d.release(root,['root']),d.release(sibling,['sibling'])];receipt(d.finish(first),['class-root'],'v2-sibling');receipt(d.finish(second),['class-sibling'],'v2-sibling')
    for release in releases:d.finish(release)
    a=expect(d.snapshot(root),[('class-root','a',2,'v2-sibling')]);b=expect(d.snapshot(sibling),[('class-sibling','a',5,'v2-sibling')]);restored=d.cold([root,sibling]);check(restored=={root:a,sibling:b},'class namespace state crossed after cold replacement')
    return {'distinct_root_ids':[identity,d.roots[sibling]['identity']['root']],'cold':restored}

def U015(d):
    root=initial(d);before=d.roots[root]['identity']['root'];d.upgrade('v2-binding',[root]);check(d.roots[root]['identity']['root']==before,'binding rename changed native namespace identity')
    rows=open_jobs(d,root,writes(('renamed-a','a',3),('renamed-b','b',-2)));receipt(rows,['renamed-a','renamed-b'],'v2-binding');snapshot=expect(d.snapshot(root),[('renamed-a','a',3,'v2-binding'),('renamed-b','b',-2,'v2-binding')])
    return {'cold':cold_exact(d,root,snapshot)}

def U016(d):
    root=initial(d);before=d.roots[root]['identity']['root'];d.deploy('v2-omitted');d.reload();failed=d.response(root,'snapshot')
    check(failed['status']==500 and 'class namespace absent' in failed['body']['error'],'omitted class remained publicly bound')
    d.upgrade('v2-code',[root]);check(d.roots[root]['identity']['root']==before,'reintroduced class changed namespace');snapshot=expect(d.snapshot(root));cold_exact(d,root,snapshot)
    rows=open_jobs(d,root,writes(('reintroduced','b',2)));receipt(rows,['reintroduced'],'v2-code');expect(d.snapshot(root),[('reintroduced','b',2,'v2-code')])
    return {'omitted_binding_error':failed,'restored_identity':d.roots[root]['identity']}

def U017(d):
    root=initial(d);before=d.roots[root].copy();old_snapshot=expect(d.snapshot(root));d.deploy('v2-script');d.reload()
    fresh=d.op(root,'prepare');ident=d.op(root,'identity');check(ident['root']!=before['identity']['root'] and fresh['items']==[] and fresh['ops']==[],'script rename reused acknowledged original namespace')
    d.op(root,'seed',{'items':[{'k':'a','value':7,'label':'alpha'},{'k':'b','value':11,'label':'beta'}]});changed=d.op(root,'apply',{'request':'new-script','op':'new-script','key':'a','delta':5});check(changed['writer']=='v2-script','new script not serving')
    d.upgrade('v2-code',[root]);check(d.snapshot(root)==old_snapshot,'temporary script namespace writes leaked back');return {'other_script_identity':ident,'cold_original':cold_exact(d,root,old_snapshot)}

def U018(d):
    root=initial(d);pending=old_cohort(d,root);before=d.pointers();since=len(d.store()['events']);d.store_control('hold_write','/index.js');job=d.launch_deploy('v2-code')
    held=d.wait(lambda:[x for x in d.store()['events'] if x['index']>=since and x['kind']=='write_held' and x.get('key','').endswith('/index.js')],'module prewrite barrier',20)
    d.kill_deploy(job);check(d.pointers()==before,'module-only interrupted deploy advanced selector');d.store_control('release','/index.js');d.wait(lambda:any(x['kind']=='put_persisted' and x['index']>=since and x.get('key','').endswith('/index.js') for x in d.store()['events']),'orphan module PUT completed',15);rows=close_old(d,root,pending);recover_publish(d,root)
    snapshot=expect(d.snapshot(root),OLD+[('recovery','a',4,'v2-code')]);return {'held_module':held,'v1_receipts':rows,'cold_retry':cold_exact(d,root,snapshot)}

def U019(d):
    root=initial(d);before=d.pointers();since=len(d.store()['events']);d.store_control('fail','/manifest.json');job=d.launch_deploy('v2-code')
    failed_event=d.wait(lambda:[x for x in d.store()['events'] if x['index']>=since and x['kind']=='put_failed' and x.get('key','').endswith('/manifest.json')],'manifest failure',20)
    # Terminate the finite retrying operator after a real store refusal; failed upload is not a migration success.
    d.kill_deploy(job);check(d.pointers()==before,'failed manifest publication advanced selector');expect(d.snapshot(root));d.store_control('release','/manifest.json');recover_publish(d,root)
    snapshot=expect(d.snapshot(root),[('recovery','a',4,'v2-code')]);return {'manifest_refusal':failed_event,'cold_recovery':cold_exact(d,root,snapshot)}

def U020(d):
    root=initial(d);before=d.pointers();since=len(d.store()['events']);d.store_control('hold_write','deploy/upgrade-test/current.json');job=d.launch_deploy('v2-code')
    held=d.store_key_event('write_held','deploy/upgrade-test/current.json',since);d.kill_deploy(job);check(d.pointers()==before,'pre-named-pointer interruption published a version')
    d.store_control('release','deploy/upgrade-test/current.json');d.store_key_event('put_persisted','deploy/upgrade-test/current.json',since);recover_publish(d,root);snapshot=expect(d.snapshot(root),[('recovery','a',4,'v2-code')]);return {'named_pointer_barrier':held,'cold':cold_exact(d,root,snapshot)}

def U021(d):
    root=initial(d);before=d.pointers();since=len(d.store()['events']);d.store_control('hold_write','deploy/current.json');job=d.launch_deploy('v2-code')
    held=d.store_key_event('write_held','deploy/current.json',since);split=d.pointers();check(split['deploy/current.json']==before['deploy/current.json'] and split['deploy/upgrade-test/current.json']!=before['deploy/upgrade-test/current.json'],'named/global split window not reached')
    d.reload();d.observe(root,'v1');expect(d.snapshot(root));d.kill_deploy(job);d.store_control('release','deploy/current.json')
    # The held HTTP handler may persist after release despite CLI death. Do not infer rollback from killed CLI.
    d.wait(lambda:any(x['kind']=='put_persisted' and x['index']>=since and x.get('key')==d.bucket+'/deploy/current.json' for x in d.store()['events']),'late global PUT persistence',15)
    d.deploy('v1');d.reload();d.observe(root,'v1');expect(d.snapshot(root));recover_publish(d,root)
    snapshot=expect(d.snapshot(root),[('recovery','a',4,'v2-code')]);return {'split':split,'barrier':held,'cold_repaired':cold_exact(d,root,snapshot)}

def U022(d):
    root=initial(d);since=len(d.store()['events']);d.store_control('hold_ack','deploy/current.json');job=d.launch_deploy('v2-code')
    held=d.store_key_event('ack_held','deploy/current.json',since);published=d.verify_publication('v2-code');d.kill_deploy(job);d.store_control('release','deploy/current.json');d.reload();d.observe(root,'v2-code')
    retried=d.deploy('v2-code');check(retried['pointer']['version']==published['version'],'same exact redeploy changed deployment identity');d.reload();d.observe(root,'v2-code')
    rows=open_jobs(d,root,writes(('ack-lost-a','a',1),('ack-lost-b','b',2)));receipt(rows,['ack-lost-a','ack-lost-b'],'v2-code');snapshot=expect(d.snapshot(root),[('ack-lost-a','a',1,'v2-code'),('ack-lost-b','b',2,'v2-code')])
    return {'publication_without_cli_ack':held,'cold':cold_exact(d,root,snapshot)}

def U023(d):
    root=initial(d);rows=open_jobs(d,root,writes(('ack-before-deploy','b',4)));receipt(rows,['ack-before-deploy'],'v1');saved=expect(d.snapshot(root),[('ack-before-deploy','b',4,'v1')])
    publication=d.deploy('v2-code');serving=d.op(root,'identity');d.event('manual-adoption-window',identity=serving);d.prerequisite(serving['build']=='v1','manual pre-adoption window absent')
    restored=d.cold([root])[root];check(restored==saved and d.op(root,'identity')['build']=='v2-code','cold startup failed to select complete published replacement')
    return {'published_before_owner_loss':publication,'cold_new_code':restored}

def U024(d):
    root=initial(d);pending=staged(d,root,writes(('old-a','a',2),('old-b','b',3),gate='external:move'));old_isolate=d.roots[root]['identity']['isolate'];publication=d.deploy('v2-code');d.reload()
    d.pending(pending);d.signal_external(root,'external:move');rows=d.finish(pending);receipt(rows,['old-a','old-b'],'v1');check(all(r['body']['identity']['isolate']==old_isolate for r in rows),'already-entered call migrated halfway')
    d.observe(root,'v2-code');new=open_jobs(d,root,writes(('new-admission','a',4)));receipt(new,['new-admission'],'v2-code');snapshot=expect(d.snapshot(root),OLD+[('new-admission','a',4,'v2-code')])
    return {'publication':publication,'entered_old_receipts':rows,'cold':cold_exact(d,root,snapshot)}

def U025(d):
    root=initial(d);pending=old_cohort(d,root);since=len(d.store()['events']);d.store_control('hold_ack','.ltx');release=d.release(root,['go']);d.store_event('ack_held',since);d.logged(root,'SQL',['old-a','old-b']);d.pending(pending)
    d.deploy('v2-code');d.reload();d.pending(pending);d.store_control('release','.ltx');rows=d.finish(pending);d.finish(release);receipt(rows,['old-a','old-b'],'v1');d.observe(root,'v2-code')
    snapshot=expect(d.snapshot(root),OLD);return {'held_old_output_receipts':rows,'cold_replacement':cold_exact(d,root,snapshot)}

def U026(d):
    root=initial(d);pending=old_cohort(d,root);d.deploy('bad-syntax');failed=d.reload(success=False)
    check(all(r['body']['error'] for r in failed),'native parser refusal lacks evidence');rows=close_old(d,root,pending);d.observe(root,'v1');expect(d.snapshot(root),OLD)
    recover_publish(d,root);snapshot=expect(d.snapshot(root),OLD+[('recovery','a',4,'v2-code')]);return {'failed_adoptions':failed,'v1_receipts':rows,'cold_repaired':cold_exact(d,root,snapshot)}

def U027(d):
    root=initial(d);identity=d.roots[root]['identity']['root'];d.deploy('front-old');d.reload();old=d.response(root,'snapshot');check(old['status']==200 and old['body']['entry']=='OldAPI','old static entrypoint not selected');expect(old['body']['value'])
    d.deploy('front-new');d.reload();new=d.response(root,'apply',{'request':'entrypoint-new','op':'entrypoint-new','key':'a','delta':3});check(new['status']==200 and new['body']['entry']=='NewAPI' and new['body']['value']['writer']=='v1','new binding entrypoint or backend code identity differs')
    ident=d.response(root,'identity');check(ident['body']['value']['root']==identity,'entrypoint binding changed backend namespace')
    # Publish backend as primary again, then the same front, proving the old static call had durable effect.
    d.deploy('v2-code');d.reload();d.observe(root,'v2-code');saved=expect(d.snapshot(root),[('entrypoint-new','a',3,'v1')]);cold_exact(d,root,saved)
    d.deploy('front-new');d.reload();after=d.response(root,'snapshot');check(after['body']['entry']=='NewAPI' and after['body']['value']==saved,'rebuilt static graph lost backend state')
    return {'old_entry':old,'new_entry_receipt':new,'rebuilt_graph':after}

def U028(d):
    root=initial(d);d.deploy('front-old');d.reload();before=d.response(root,'snapshot');check(before['status']==200 and before['body']['entry']=='OldAPI','initial static graph not serving');expect(before['body']['value'])
    d.deploy('front-missing');failed=d.reload(success=False);check(all('upgrade-missing' in r['body']['error'] for r in failed),'missing static dependency not diagnosed')
    surviving=d.response(root,'apply',{'request':'old-graph','op':'old-graph','key':'b','delta':2});check(surviving['status']==200 and surviving['body']['entry']=='OldAPI' and surviving['body']['value']['changed'],'failed graph adoption disrupted prior graph')
    d.deploy('front-new');d.reload();repaired=d.response(root,'snapshot');check(repaired['body']['entry']=='NewAPI','corrective static entrypoint absent');expect(repaired['body']['value'],[('old-graph','b',2,'v1')])
    d.deploy('v2-code');d.reload();d.observe(root,'v2-code');saved=expect(d.snapshot(root),[('old-graph','b',2,'v1')]);return {'failed_graph':failed,'old_graph_ack':surviving,'cold_backend':cold_exact(d,root,saved)}

CASES={name:globals()[name] for name in ('U001','U002','U003','U004','U005','U006','U007','U008','U009','U010','U011','U012','U013','U014','U015','U016','U017','U018','U019','U020','U021','U022','U023','U024','U025','U026','U027','U028')}
