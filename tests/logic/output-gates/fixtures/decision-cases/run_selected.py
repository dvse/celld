#!/usr/bin/env python3
"""Execute ONLY the selected G021/G022 observational snapshot, bounded."""
import datetime, hashlib, json, os, pathlib, resource, signal, subprocess, sys, time
W=pathlib.Path(__file__).resolve().parent
T=pathlib.Path('/workspace/shared/celld-os-project/.toolchains/install/bin')
OUT=W/'evidence'/('lease-expiry-observation-v2-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')); OUT.mkdir(parents=True,exist_ok=False)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def interrupted(signum, frame):
    raise InterruptedError('Orchestrator received signal '+str(signum))
signal.signal(signal.SIGTERM,interrupted)
def bounded(name, command, wall, cpu, env):
    def limits():
        os.setsid();resource.setrlimit(resource.RLIMIT_AS,(1073741824,1073741824));resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu));resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    started=now();start=time.monotonic();p=None;output='';timed_out=False;forced=False;error=None;was_interrupted=False;group_cleanup=False
    try:
        p=subprocess.Popen(command,cwd=W,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,preexec_fn=limits)
        output,_=p.communicate(timeout=wall)
    except subprocess.TimeoutExpired:
        timed_out=True;error='outer wall deadline exceeded'
    except BaseException as exception:
        was_interrupted=isinstance(exception,(KeyboardInterrupt,InterruptedError,SystemExit))
        error=type(exception).__name__+': '+str(exception)
    finally:
        prior_term=signal.signal(signal.SIGTERM,signal.SIG_IGN)
        prior_int=signal.signal(signal.SIGINT,signal.SIG_IGN)
        try:
            if p is not None:
                # The session/process group was created exclusively for this
                # child. Never inspect or signal an unrelated host process.
                try: os.killpg(p.pid,0); group_alive=True
                except ProcessLookupError: group_alive=False
                if group_alive:
                    try: os.killpg(p.pid,signal.SIGTERM)
                    except ProcessLookupError: pass
                try: remainder,_=p.communicate(timeout=1)
                except subprocess.TimeoutExpired:
                    forced=True
                    try: os.killpg(p.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    remainder,_=p.communicate()
                if remainder: output=remainder
                try:
                    os.killpg(p.pid,0)
                    forced=True
                    os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                p.wait()
                group_cleanup=True
        finally:
            signal.signal(signal.SIGTERM,prior_term);signal.signal(signal.SIGINT,prior_int)
    log=OUT/(name+'.log');log.write_text(output)
    item={'command':command,'pid':p.pid if p else None,'started_utc':started,'finished_utc':now(),'elapsed_seconds':time.monotonic()-start,'rlimit_as_bytes':1073741824,'rlimit_cpu_seconds':cpu,'wall_seconds':wall,'returncode':p.returncode if p else None,'timed_out':timed_out,'forced_kill':forced,'interruption_or_error':error,'interrupted':was_interrupted,'owned_process_reaped':p is None or p.poll() is not None,'owned_group_cleanup_completed':group_cleanup,'log':str(log.relative_to(W)),'log_sha256':sha(log),'max_rss_kib_children_so_far':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss}
    return item,output
result={'started_utc':now(),'status':'BLOCKED','layer':'native-component','sublayer':'state-trace','case_ids':['G021','G022'],'case_runs':0,'case_passes':0,'policy_verdict':'UNRESOLVED','promotion':False,'steps':[]}
try:
    expected={'tests/output_gate.rs':'4111d744a514b64a36f285dbf4a8b51ca56ce3f3f128dbd5ea1cc188ebed88ba','Cargo.toml':'0c075c77c926d9e73573956e0460228034568bc8d2f9aae5045745a6b7896f64','source-pins.json':'2e06ae03480e8f4a36ea41fd7e0da83519b51a3334fbeea4c9ba6982596df2f1'}
    for name,digest in expected.items():
        if sha(W/name)!=digest: raise RuntimeError('Reviewed snapshot hash mismatch: '+name)
    pins=json.loads((W/'source-pins.json').read_text())
    for name,digest in pins['production_files'].items():
        if sha(pathlib.Path(pins['source_root'])/name)!=digest: raise RuntimeError('Frozen production source mismatch: '+name)
    result['implementation_hashes']=expected;result['runner_sha256']=sha(pathlib.Path(__file__));result['profile_sha256']=sha(W/'profile-v2.json')
    env=os.environ.copy();env.update(PATH=str(T)+os.pathsep+env.get('PATH',''),RUSTC=str(T/'rustc'),CARGO_HOME=str(W/'cargo-home'),CARGO_INCREMENTAL='0',CARGO_NET_OFFLINE='true')
    for key in ['RUSTFLAGS','CARGO_ENCODED_RUSTFLAGS','RUSTC_WRAPPER','RUSTC_WORKSPACE_WRAPPER']:
        env.pop(key,None)
    env['RUSTFLAGS']='-C link-arg=-Wl,--threads=1'
    result['environment_overrides']={k:env[k] for k in ['RUSTC','CARGO_HOME','CARGO_INCREMENTAL','CARGO_NET_OFFLINE','RUSTFLAGS']}
    result['toolchain_executable_hashes']={str(T/n):sha(T/n) for n in ['rustc','cargo']}
    item,output=bounded('rustc-version',[str(T/'rustc'),'--version','--verbose'],10,10,env);result['steps'].append(item)
    if item['interruption_or_error'] is not None:
        result['interrupted']=item['interrupted'];raise RuntimeError('Stopped after toolchain step: '+item['interruption_or_error'])
    if item['returncode']!=0: raise RuntimeError('Toolchain prerequisite failed')
    result['rustc_version']=output
    command=[str(T/'cargo'),'test','--offline','--manifest-path',str(W/'Cargo.toml'),'--target-dir',str(W/'target'),'--test','output_gate','--no-run','-j','1','--message-format=json']
    item,output=bounded('build',command,90,60,env);result['steps'].append(item)
    if item['interruption_or_error'] is not None:
        result['interrupted']=item['interrupted'];raise RuntimeError('Stopped after build step: '+item['interruption_or_error'])
    if item['returncode']!=0: raise RuntimeError('Bounded offline compilation failed; no test trace entered')
    bins=[]
    for line in output.splitlines():
        try: msg=json.loads(line)
        except ValueError: continue
        if msg.get('reason')=='compiler-artifact' and msg.get('target',{}).get('name')=='output_gate' and msg.get('executable'): bins.append(msg['executable'])
    if len(bins)!=1: raise RuntimeError('Cannot uniquely resolve compiled test executable')
    binary=pathlib.Path(bins[0]);result['test_binary']={'path':str(binary),'sha256':sha(binary)}
    result['cases']=[]
    for ident,test in [('G021','g021_fleet_proof_after_authority_expiry_records_settlement'),('G022','g022_bucket_verification_after_authority_expiry_records_settlement')]:
        item,output=bounded(ident,[str(binary),'--exact',test,'--nocapture','--test-threads=1'],10,10,env);result['steps'].append(item)
        entered='event 01:' in output
        stopped=item['interruption_or_error'] is not None
        passed=not stopped and not item['timed_out'] and item['returncode']==0 and '1 passed; 0 failed' in output and 'CHARACTERIZATION observed_settlement=' in output
        result['cases'].append({'id':ident,'test':test,'trace_entered':entered,'status':'BLOCKED' if stopped else 'PASS' if passed else 'FAIL' if entered else 'BLOCKED','interrupted':item['interrupted'],'stop_reason':item['interruption_or_error'],'qualification':'observational only','policy_verdict':'UNRESOLVED','promotion':False,'log':item['log']})
        result['case_runs']+=int(entered);result['case_passes']+=int(passed)
        if stopped:
            result['interrupted']=item['interrupted'];raise RuntimeError('Stopped after '+ident+': '+item['interruption_or_error'])
    result['status']='PASS' if result['case_passes']==2 else 'FAIL'
except BaseException as error:
    result['error']=str(error)
finally:
    result['finished_utc']=now();result['cleanup']={'all_owned_children_reaped':all(s['owned_process_reaped'] for s in result['steps']),'production_source_unchanged':all(sha(pathlib.Path(pins['source_root'])/n)==d for n,d in pins['production_files'].items()) if 'pins' in locals() else None,'native_state':'dropped on test return/unwind; no runtime/guest launched'}
    (OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
sys.exit(0 if result['status']=='PASS' else 2)
