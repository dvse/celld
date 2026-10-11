    def response(self,root,method,args=None,node=None):
        node=node or self.roots[root]['node']
        payload={'root':self.roots[root]['name'],'method':method,'args':args or {},'namespace':self.roots[root].get('namespace','root')}
        return self.http_response(2,f'http://192.168.77.{node}:18080/op',payload)
    def http_response(self,node,url,body,timeout=20):
        need(url in [f'http://192.168.77.{n}:{p}/{path}' for n in (1,2) for p,path in ((18080,'op'),(18081,'reload'))],'operator URL outside owned private allowlist')
        source=f'''import json,urllib.request,urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect prohibited')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({{}}),NoRedirect())
request=urllib.request.Request({url!r},data={json.dumps(body).encode()!r},headers={{'Content-Type':'application/json'}})
try:reply=opener.open(request,timeout={timeout})
except urllib.error.HTTPError as error:reply=error
with reply:
 raw=reply.read(1048577)
 if len(raw)>1048576:raise RuntimeError('bounded operator evidence exceeded')
 result={{'status':reply.status,'body':json.loads(raw)}}
'''
        return self.py(node,source,timeout+3)
    def store_control(self,mode,match):
        need(mode in ('release','hold_write','hold_ack','fail'),'unsupported publication fault')
        need(match in ('.ltx','/index.js','/manifest.json','deploy/upgrade-test/current.json','deploy/current.json'),'publication match outside owned keys')
        value=self.http(1,'http://192.168.77.2:19000/__control',{'mode':mode,'match':match});self.event('publication-control',mode=mode,match=match);return value
    def store_key_event(self,kind,match,since):
        def ready():
            events=self.store()['events'];found=[e for e in events if e['index']>=since and e['kind']==kind and self.bucket+'/'+match in e.get('key','')]
            return found or None
        result=self.wait(ready,'publication '+kind+' '+match,20);self.event('publication-barrier',records=result);return result
    def object(self,key):
        need(key.startswith('deploy/') and '..' not in key,'not an owned deployment object')
        return self.py(2,f'''import hashlib,json,pathlib,base64
key={self.bucket+'/'+key!r};p=pathlib.Path({self.prefix+'-bucket'!r})/(hashlib.sha256(key.encode()).hexdigest()+'.json')
if not p.exists():result=None
else:
 meta=json.loads(p.read_text())
 if meta['key']!=key:raise RuntimeError('store key identity mismatch')
 raw=p.with_suffix('.data').read_bytes()
 if len(raw)>262144:raise RuntimeError('deployment object bound')
 result={{'sha256':hashlib.sha256(raw).hexdigest(),'body':raw.decode(),'metadata':meta}}
''')
    def pointers(self):
        result={}
        for key in ('deploy/current.json','deploy/upgrade-test/current.json','deploy/upgrade-front/current.json','deploy/upgrade-renamed/current.json'):
            value=self.object(key);result[key]=json.loads(value['body']) if value else None
        return result
    def verify_publication(self,version):
        config=json.loads((HERE/'versions'/version/'wrangler.jsonc').read_text());script=config['name'];pointers=self.pointers();current=pointers['deploy/current.json']
        need(current is not None,'native deployment pointer missing')
        check(current['script_name']==script and current['prefix']==f"deploy/{script}/{current['version']}",'native deployment pointer identity')
        named=self.object(f'deploy/{script}/current.json');check(named is not None and json.loads(named['body'])==current,'named/global publication differs')
        manifest=json.loads(self.object(current['prefix']+'/manifest.json')['body']);module=self.object(current['prefix']+'/index.js')
        check(module['sha256']==digest(HERE/'versions'/version/'fixture.js'),'uploaded module bytes differ from exact version')
        check(manifest['version']==current['version'] and manifest['script_name']==script and manifest['modules']==[{'name':'index.js','bytes':len((HERE/'versions'/version/'fixture.js').read_bytes()),'sha256':module['sha256']}],'published manifest/module identity differs')
        self.event('native-publication-verified',fixture_version=version,pointer=current,module_sha256=module['sha256']);return current
    def launch_deploy(self,version):
        need(self.stage_verified,'preflight incomplete');need((HERE/'versions'/version/'wrangler.jsonc').is_file() and '/' not in version,'unknown fixture version')
        need(len(self.deployments)<8 and all(x.get('terminal') for x in self.deployments),'at most8 sequential deploy processes per case')
        directory=self.prefix+'-deploy-'+str(len(self.deployments)+1)
        identity=self.py(2,f'''import pathlib,subprocess,os
log=open({directory+'.log'!r},'wb')
p=subprocess.Popen(['/stage/native-durability/python/bin/python3.13',{STAGE+'/deploy_job.py'!r},{version!r},{self.bucket!r},{directory!r}],stdout=log,stderr=log)
fields=pathlib.Path('/proc',str(p.pid),'stat').read_text().rsplit(')',1)[1].split()
result={{'pid':p.pid,'exe':str(pathlib.Path('/proc',str(p.pid),'exe').resolve()),'start_ticks':fields[19]}}
''')
        job={'version':version,'directory':directory,'wrapper':identity};self.deployments.append(job)
        def start_record():
            return self.py(2,f"import pathlib,json;p=pathlib.Path({directory!r});child=p/'child.json';terminal=p/'result.json';result={{'child':json.loads(child.read_text()) if child.exists() else None,'terminal':json.loads(terminal.read_text()) if terminal.exists() else None}}")
        observed=self.wait(lambda:(r if (r:=start_record())['child'] is not None or r['terminal'] is not None else None),'native CLI child or terminal operator evidence',20)
        if observed['terminal'] is not None:
            self.event('native-operator-early-terminal',result=observed['terminal'])
            need(observed['terminal'].get('operator_error') is None,'native operator metadata or child cleanup failed before child witness')
        capture=observed['child'];need(capture is not None,'native operator has no child launch record')
        need(capture['launch_binary_sha256']==BINARY,'native deploy binary pin mismatch');job['child']=capture['identity'];job['capture']=capture['capture'];self.event('native-deploy-started',job=job);return job
    def deploy_records(self,job):
        return self.py(2,f"import pathlib,json;p=pathlib.Path({job['directory']+'/result.json'!r});result=json.loads(p.read_text()) if p.exists() else None")
    def finish_deploy(self,job,success=True):
        result=self.wait(lambda:self.deploy_records(job),'native deployment terminal receipt',40);job['terminal']=True
        self.event('native-deploy-terminal-receipt',result=result)
        need(result.get('operator_error') is None,'native operator metadata/child-cleanup failure: '+str(result.get('operator_error')))
        self.trace_entered=True
        self.event('case-trace-entered',witness='verified-native-deploy-terminal-outcome',fixture_version=job['version'])
        check(not result['timed_out'] and not result['output_truncated'],'native deployment did not finish within bounded operator contract')
        check((result['exit_code']==0)==success,{'unexpected_deploy_result':result})
        if success:result['pointer']=self.verify_publication(job['version'])
        self.event('native-deploy-finished',result=result);return result
    def deploy(self,version):return self.finish_deploy(self.launch_deploy(version))
    def kill_deploy(self,job):
        existing=self.deploy_records(job)
        if existing is not None:return self.finish_deploy(job,success=False)
        expected=job['child'];need(expected is not None,'no live native CLI identity available for interruption');need(self.process(2,expected['pid'],BINARY)==expected,'native CLI identity changed before interruption')
        result=self.py(2,f'''import os,pathlib,signal,hashlib
expected={expected!r};fd=os.pidfd_open(expected['pid']);p=pathlib.Path('/proc',str(expected['pid']));fields=(p/'stat').read_text().rsplit(')',1)[1].split()
if fields[19]!=expected['start_ticks'] or hashlib.sha256((p/'exe').read_bytes()).hexdigest()!=expected['sha256']:raise RuntimeError('native CLI changed before fault')
signal.pidfd_send_signal(fd,signal.SIGKILL);os.close(fd);result={{'killed':expected}}
''');self.event('native-deploy-interrupted',record=result)
        return self.finish_deploy(job,success=False)
    def reload(self,success=True):
        results=[self.http_response(2,f'http://192.168.77.{node}:18081/reload',{},timeout=25) for node in (1,2)]
        for result in results:
            check(result['status']==(200 if success else 422),'unexpected native reload status: '+str(result))
            check(result['body'].get('outcome')==('adopted' if success else 'failed'),'unexpected native reload outcome')
        self.event('native-reload',results=results);return results
    def observe(self,root,build=None):
        before=self.roots[root]['identity'];node=self.roots[root]['node']
        ident=self.wait(lambda:(v if (build is None or (v:=self.op(root,'identity'))['build']==build) else None),'root code '+str(build),20) if build is not None else self.op(root,'identity')
        check(ident['root']==before['root'],'stable script/class/name changed root identity');owner=self.owner(ident['root'])
        check(owner['epoch']>=self.roots[root]['owner']['epoch'],'owner epoch regressed')
        need(owner['node']==self.runtime[node]['node'],'owner placement drift')
        self.roots[root].update(identity=ident,owner=owner);self.event('current-root-observed',root=root,identity=ident,owner=owner);return ident
    def upgrade(self,version,roots=()):
        receipt=self.deploy(version);self.reload()
        for root in roots:self.observe(root,version)
        return receipt
    def cold(self,roots):
        for root in roots:self.observe(root)
        self.restart(list(roots));return {root:self.snapshot(root) for root in roots}
    def signal_external(self,root,gate):
        need(gate.startswith('external:') and re.fullmatch(r'[A-Za-z0-9:_-]{1,100}',gate),'invalid external fixture gate')
        token='UPG_RELEASE '+self.roots[root]['identity']['root']+' '+gate
        result=self.py(2,f'''import urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('redirect prohibited')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({{}}),NoRedirect())
request=urllib.request.Request('http://192.168.77.2:19000/__effect',data={token.encode()!r},method='POST')
with opener.open(request,timeout=5) as reply:
 raw=reply.read(32)
 result={{'status':reply.status,'body':raw.decode()}}
''')
        check(result=={'status':200,'body':'OK'},'owned external fixture release failed');self.event('external-gate-released',token=token);return result
    def alarm_completed(self,root,op,build):
        token='UPG_ALARM '+self.roots[root]['identity']['root']+' '+op+' '+build;node=self.roots[root]['node']
        self.wait(lambda:self.py(node,f"import pathlib;result={token!r} in pathlib.Path({self.prefix+'-'+str(node)+'.log'!r}).read_text(errors='replace')[-262144:]"),'replacement alarm completion log',20,poll=1)
        self.event('alarm-completed-log',root=root,token=token)
    def wait_alarm(self,root,op):
        result=self.wait(lambda:next((row for row in self.snapshot(root)['alarms'] if row['op']==op),None),'alarm effect '+op,100,poll=1)
        self.event('alarm-effect',root=root,row=result);return result
    def after_due(self,root,due):
        result=self.wait(lambda:(v if (v:=self.op(root,'alarmState'))['now']>=due+5000 else None),'alarm deadline plus5s',120,poll=1)
        self.event('past-alarm-deadline',root=root,record=result);return result

