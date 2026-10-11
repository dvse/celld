"""Five bounded local fleet scenarios, with cross-node ledger verification sweeps."""
import concurrent.futures,json,os,signal,socket,time,traceback,urllib.request
from pathlib import Path
from common import TESTS,ROOT,Process,clean_env,command,dump,result,sha,port_available
from runtime import executable,Unavailable,fetch
from s3_store import Store
class Fleet:
    def __init__(self,out):
        self.out=out;out.mkdir(parents=True);self.nodes={};self.store=Store(out/'store');self.binary=executable('celld');self.esbuild=executable('esbuild');self.generation={0:0,1:0}
        for p in [9800,9801,9802]:self.store.listen(p)
        self.env=clean_env();self.env.update(AWS_ACCESS_KEY_ID='suite-public-test-only',AWS_SECRET_ACCESS_KEY='suite-public-test-only',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',CELLD_ESBUILD=self.esbuild,CELLD_TTL_MS='3000',CELLD_REBALANCE_INTERVAL_MS='0',CELLD_OPERATION_DEADLINE_MS='5000',CELLD_DURABILITY='bucket',CELLD_RECOVERY_RETRY_MS='100',CELLD_WAKER_TICK_MS='500',CELLD_MAX_RESIDENT_CELLS='16')
        code,_=command([self.binary,'deploy',TESTS/'faults/process-failure/fixtures/ledger','--bucket','s3://test-bucket','--endpoint','http://127.0.0.1:9800'],ROOT,out/'deploy.log',45,self.env)
        if code:raise RuntimeError('fault fixture deployment failed; see deploy.log')
        self.start(0);self.start(1)
        dump(out/'configuration.json',{'celld_sha256':sha(self.binary),'store':'local append-only S3 subset, linearizable conditional writes','ttl_ms':3000,'durability':'bucket','ports':[9800,9801,9802,9804,9805,9806,9807],'cells':4,'pre_fault_writes_per_cell':3,'post_fault_writes_per_cell':2,'recovery_bound_seconds':45})
    def start(self,n):
        self.generation[n]+=1;g=self.generation[n];data=self.out/f'node-{n}-generation-{g}';data.mkdir()
        env={**self.env,'CELLD_NODE':f'suite-node-{n}','CELLD_TEST_DATA_DIR':str(data)}
        for port in [9804+n,9806+n]:port_available(port)
        proc=Process([self.binary,'--bucket','s3://test-bucket','--endpoint',f'http://127.0.0.1:{9801+n}','--listen',f'127.0.0.1:{9804+n}','--internal-listen',f'127.0.0.1:{9806+n}'],ROOT,self.out/f'node-{n}-{g}.log',env);self.nodes[n]=proc
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if proc.p.poll() is not None:raise RuntimeError(f'node {n} exited during startup')
            try:
                r=fetch(9804+n,{'path':'/.well-known/celld/health','timeout':1})
                if r['status']==200:return
            except Exception:pass
            time.sleep(.15)
        raise RuntimeError(f'node {n} never became healthy')
    def stop_node(self,n,kill=False):
        p=self.nodes.get(n)
        if p:
            if kill:
                try:os.killpg(p.p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
            p.stop();self.nodes.pop(n,None)
    def req(self,n,step,deadline=45):
        end=time.monotonic()+deadline;last=None
        while time.monotonic()<end:
            try:
                last=fetch(9804+n,{**step,'timeout':min(5,max(.2,end-time.monotonic()))})
                if last['status']==200:return last['body']
            except Exception as e:last=str(e)
            time.sleep(.3)
        raise AssertionError(f'node {n} failed to recover: {last}')
    def sweep(self,expected,nodes,label):
        observed={}
        for n in nodes:
            for cell,ledger in expected.items():
                value=self.req(n,{'path':'/'+cell});observed[f'{n}/{cell}']=value
                assert value==[list(x) for x in sorted(ledger.items())],f'ledger lost/duplicated/corrupted for {n}/{cell}: {value} != {ledger}'
        dump(self.out/(label+'.json'),observed)
    def close(self):
        for n in list(self.nodes):self.stop_node(n)
        self.store.stop()
def run_fleet(cases,runtimes,out):
    rows=[]
    for case in cases:
        for runtime in runtimes:
            if runtime!='celld':rows.append(result(case,runtime,'not-applicable','stock workerd does not implement celld fleet ownership or bucket recovery'));continue
            directory=out/case['id'].split('/')[-1];fleet=None;start=time.monotonic();events=[];stream=None
            try:
                if os.uname().sysname!='Linux':raise Unavailable('live fleet profile runs on a Linux fleet host')
                fleet=Fleet.__new__(Fleet);fleet.__init__(directory);expected={f'cell{i}':{} for i in range(4)}
                for cell,ledger in expected.items():
                    for i in range(3):
                        entry={'id':str(i),'value':f'{cell}-value-{i}'};response=fleet.req(0,{'path':'/'+cell,'json':entry});assert response==entry;ledger['entry/'+str(i)]=entry['value']
                fleet.sweep(expected,[0,1],'before-sweep')
                name=case['selector']
                if name=='sigkill-mid-write':
                    # Send one chunk and hold the tail: kill during a genuinely
                    # open streamed request. The write has no HTTP ack.
                    stream=socket.create_connection(('127.0.0.1',9804),timeout=2)
                    stream.sendall(b'POST /cell0/stream HTTP/1.1\r\nHost: suite.test\r\nTransfer-Encoding: chunked\r\n\r\n1000\r\n'+b'x'*4096+b'\r\n');time.sleep(.3)
                    end=time.monotonic()+5
                    while True:
                        witness=fleet.req(0,{'path':'/cell0/stream-status'},deadline=3)
                        if witness['bytes']==4096:break
                        assert time.monotonic()<end,'stream never reached storage write barrier'
                        time.sleep(.1)
                    dump(directory/'mid-stream-witness.json',witness)
                    events.append({'fault':'SIGKILL','pid':fleet.nodes[0].p.pid,'open_stream_bytes':4096});fleet.stop_node(0,True);stream.close();stream=None
                    # Recovery has no access to old local DB; retain it as
                    # evidence rather than unlinking the database files.
                    old=directory/'node-0-generation-1';old.rename(directory/'killed-node-local-db-moved-aside')
                    fleet.sweep(expected,[1],'bucket-only-recovery-sweep')
                elif name=='freeze-owner':
                    pid=fleet.nodes[0].p.pid;os.killpg(pid,signal.SIGSTOP);events.append({'fault':'SIGSTOP','pid':pid});time.sleep(4)
                    fleet.sweep(expected,[1],'frozen-owner-takeover-sweep')
                elif name=='store-partition':
                    fleet.store.faults[9801]='cut';events.append({'fault':'S3-unavailable','node':0});time.sleep(5)
                    # Once the lease expires, the isolated node cannot ack a
                    # fresh write. Record the observed failure/status.
                    try:probe=fetch(9804,{'path':'/cell0','json':{'id':'must-not-ack','value':'partition'},'timeout':3})
                    except Exception as e:probe={'unavailable':str(e)}
                    dump(directory/'fence-probe.json',probe);assert probe.get('status')!=200,'isolated expired owner acknowledged a write'
                    fleet.sweep(expected,[1],'partition-recovery-sweep')
                elif name=='store-throttle-429':
                    baseline=sum(fleet.store.counts.values());fleet.store.faults.update({9801:'throttle',9802:'throttle'});events.append({'fault':'429','all_nodes':True})
                    t=time.monotonic()
                    try:probe=fetch(9804,{'path':'/unacknowledged-throttle','json':{'id':'probe','value':'unacknowledged'},'timeout':2})
                    except Exception as e:probe={'unavailable':str(e)}
                    dump(directory/'throttle-write-probe.json',probe);assert probe.get('status')!=200,'429-only store acknowledged an unproven write'
                    time.sleep(max(0,4-(time.monotonic()-t)))
                    attempts=sum(fleet.store.counts.values())-baseline;dump(directory/'throttle-window.json',{'seconds':4,'requests':attempts,'bound':200});assert attempts<=200,'store retry amplification exceeds finite 200-request/4s budget'
                    fleet.store.faults.clear()
                    for n in [0,1]:
                        if fleet.nodes[n].p.poll() is not None:
                            fleet.stop_node(n);fleet.start(n)
                elif name=='node-stop':
                    events.append({'fault':'SIGTERM','pid':fleet.nodes[0].p.pid});fleet.stop_node(0)
                    fleet.sweep(expected,[1],'stopped-node-recovery-sweep')
                # Successful writes through surviving node must occur once.
                for cell,ledger in expected.items():
                    for i in range(3,5):
                        entry={'id':str(i),'value':f'{cell}-value-{i}'};assert fleet.req(1,{'path':'/'+cell,'json':entry})==entry;ledger['entry/'+str(i)]=entry['value']
                if name=='freeze-owner':
                    os.killpg(fleet.nodes[0].p.pid,signal.SIGCONT);events.append({'fault':'SIGCONT'})
                    # Process fencing is asynchronous after SIGCONT. Wait for
                    # the required rejection/exit before restarting its session.
                    end=time.monotonic()+8
                    while fleet.nodes[0].p.poll() is None and time.monotonic()<end:time.sleep(.1)
                    assert fleet.nodes[0].p.poll() is not None,'resumed stale owner did not fence itself within 8 seconds'
                    events.append({'fence_exit':fleet.nodes[0].p.returncode})
                fleet.store.faults.clear()
                for n in [0,1]:
                    if n not in fleet.nodes or fleet.nodes[n].p.poll() is not None:
                        fleet.stop_node(n);fleet.start(n)
                fleet.sweep(expected,[0,1],'after-sweep');dump(directory/'expected-ledger.json',expected)
                rows.append(result(case,runtime,'pass','pre/post cross-node sweeps matched all acknowledged ledger entries exactly',round((time.monotonic()-start)*1000),[directory]))
            except Exception as e:
                directory.mkdir(parents=True,exist_ok=True);(directory/'failure.log').write_text(traceback.format_exc());rows.append(result(case,runtime,'not-applicable' if isinstance(e,Unavailable) else 'fail',f'{type(e).__name__}: {e}',round((time.monotonic()-start)*1000),[directory]))
            finally:
                if stream:stream.close()
                if fleet:fleet.close()
                dump(directory/'fault-events.json',events)
    return rows
