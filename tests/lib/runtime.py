"""Identical staged Wrangler source in celld and stock workerd."""
from pathlib import Path
import json, os, re, shutil, socket, time, urllib.request, urllib.error
from common import ROOT,TESTS,Process,command,clean_env,port_available,dump,sha
class Unavailable(Exception):pass

def executable(name):
    env={'celld':'CELLD_BIN','workerd':'WORKERD_BIN','esbuild':'CELLD_ESBUILD'}[name]
    paths=[os.environ.get(env),shutil.which(name),str(TESTS/'.tools/node_modules/.bin'/name),str(Path.home()/'celld-tests-20261010/tools/node_modules/.bin'/name)]
    if name=='celld':paths += [str(ROOT/'target/debug/celld'),str(Path.home()/'celld-tests-20261010/build-source/target/debug/celld')]
    for p in paths:
        if p and Path(p).is_file() and os.access(p,os.X_OK):return str(Path(p).resolve())
    raise Unavailable(f'{name} binary absent; set {env} or run tests/lib/provision.sh')
def load_config(path):
    # JSONC comments, while preserving // inside strings.
    text=Path(path).read_text();text=re.sub(r'("(?:\\.|[^"\\])*"|/\*[\s\S]*?\*/|//[^\n]*)',lambda m:m[0] if m[0].startswith('"') else '',text)
    return json.loads(re.sub(r',\s*([}\]])',r'\1',text))
def fetch(port,step):
    payload=step.get('json');data=json.dumps(payload).encode() if payload is not None else step.get('body',None)
    if isinstance(data,str):data=data.encode()
    req=urllib.request.Request(f'http://127.0.0.1:{port}'+step.get('path','/'),data=data,method=step.get('method','POST' if data is not None else 'GET'),headers={'Host':'suite.test','Content-Type':'application/json',**step.get('headers',{})})
    try:r=urllib.request.urlopen(req,timeout=step.get('timeout',12))
    except urllib.error.HTTPError as e:r=e
    with r:
        cap=step.get('max_response_bytes',8*1024*1024);raw=r.read(cap+1)
        if len(raw)>cap:raise RuntimeError('response exceeds source limit '+str(cap))
        body=raw.decode('utf-8','replace')
        try:body=json.loads(body)
        except ValueError:pass
        return {'status':r.status,'body':body}
class Runtime:
    def __init__(self,source,runtime,out,split=False,bounded=False,resource_guard=None,port=9810):
        self.out=out;out.mkdir(parents=True,exist_ok=True);self.runtime=runtime;self.port=port;self.process=None;self.store=None;self.guard=resource_guard
        self.binary=executable(runtime);self.esbuild=executable('esbuild');port_available(self.port)
        self.stage=out/'fixture'
        if source.parent.name=='waves' and (source.parent.parent/'fixture').exists():
            self.stage=out/'fixture/waves'/source.name
            shutil.copytree(source.parent.parent/'fixture',out/'fixture/fixture')
        shutil.copytree(source,self.stage,symlinks=False)
        config_files=[p for p in self.stage.glob('wrangler.*') if p.suffix in ('.json','.jsonc')]
        if not config_files:raise Unavailable('fixture has no JSON/JSONC Wrangler entry')
        cfg=load_config(config_files[0]);self.cfg=cfg
        self.projects=[]
        for other in sorted(self.stage.glob('*/wrangler.json')):self.projects.append((other,load_config(other)))
        if (self.stage/'owner.json').exists():self.projects.append((self.stage/'owner.json',load_config(self.stage/'owner.json')))
        self.projects.append((config_files[0],cfg))
        self.env=clean_env();self.env.update(CELLD_ESBUILD=self.esbuild,CELLD_INTERNAL_ADDR='127.0.0.1:9811')
        if self.guard:self.env=self.guard.environment(self.env)
        if runtime=='celld':
            from s3_store import Store
            self.store=Store(out/'s3-store');self.store.listen(9812)
            self.env.update(AWS_ACCESS_KEY_ID='suite-public-test-only',AWS_SECRET_ACCESS_KEY='suite-public-test-only',AWS_REGION='us-east-1',AWS_EC2_METADATA_DISABLED='true',CELLD_NODE='conformance-node',CELLD_TEST_DATA_DIR=str(out/'celld-storage'),CELLD_REBALANCE_INTERVAL_MS='0',CELLD_DURABILITY='bucket')
            for index,(config,_) in enumerate(self.projects):
                code,_=command([self.binary,'deploy',config,'--bucket','s3://test-bucket','--endpoint','http://127.0.0.1:9812'],out,out/f'deploy-{index}.log',30,self.env)
                if code:
                    self.stop();raise RuntimeError('fixture deployment failed; see deploy-'+str(index)+'.log')
            args=[self.binary,'--bucket','s3://test-bucket','--endpoint','http://127.0.0.1:9812','--listen','127.0.0.1:9810','--internal-listen','127.0.0.1:9811']
        else:
            args=[self.binary,'serve','--experimental',self.workerd_config(cfg,split)]
        dump(out/'runtime.json',{'runtime':runtime,'binary':self.binary,'binary_sha256':sha(self.binary),'command':[str(x) for x in args],'fixtures':{str(p.relative_to(out/'fixture')):sha(p) for p in (out/'fixture').rglob('*') if p.is_file()}})
        self.process=Process(args,out,out/'runtime.log',self.env)
        if self.guard:self.guard.register(runtime,self.process)
        if bounded and not self.guard:
            from phase2.guard import Guard
            self.guard=Guard(out);self.guard.register(runtime,self.process)
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            if self.process.p.poll() is not None:
                self.stop();raise RuntimeError('runtime exited during startup; see runtime.log')
            try:
                with socket.create_connection(('127.0.0.1',self.port),timeout=.2):return
            except OSError:time.sleep(.1)
        self.stop();raise RuntimeError('runtime did not listen within 30 seconds')
    def workerd_config(self,cfg,split):
        j=json.dumps;services=[];routing=[];main_name=cfg['name']
        names={c['name']:'main' if c['name']==main_name else c['name'] for _,c in self.projects}
        for config,project in self.projects:
            unsupported=set(project)&{'kv_namespaces','d1_databases','r2_buckets','queues','assets','containers','workflows','triggers'}
            if unsupported:raise Unavailable('stock workerd has no bundled scheduling/service backend for '+', '.join(sorted(unsupported)))
            bundle=self.out/(project['name']+'.mjs')
            code,_=command([self.esbuild,config.parent/project['main'],'--bundle','--format=esm','--platform=neutral','--target=esnext','--external:cloudflare:*','--external:node:*','--external:*.wasm','--outfile='+str(bundle)],config.parent,self.out/('bundle-'+project['name']+'.log'),30,self.env)
            if code:raise RuntimeError('esbuild failed; see bundle log')
            flags=list(project.get('compatibility_flags',[]))
            if 'sqlite_vec' in flags:raise Unavailable('sqlite_vec is a celld extension; official stock workerd rejects that compatibility flag')
            classes=list(dict.fromkeys([b['class_name'] for b in project.get('durable_objects',{}).get('bindings',[]) if not b.get('script_name')]+[c for m in project.get('migrations',[]) for c in m.get('new_sqlite_classes',[])]))
            extra_modules=''.join(', (name='+j(p.name)+',wasm=embed '+j(str(p.relative_to(self.out)))+')' for p in config.parent.rglob('*.wasm'))
            roles=['main','caller','owner'] if split and project['name']==main_name else [names[project['name']]]
            for role in roles:
                bindings=[]
                for b in project.get('durable_objects',{}).get('bindings',[]):
                    target=names[b['script_name']] if b.get('script_name') else 'caller' if role=='main' and split else 'owner' if split else role
                    if split and project['name'] in ['sqlite-concurrency-acceptance','native-transform-acceptance','bounded-resource-acceptance']:
                        target='caller' if b['name']=='ROOT' else 'owner'
                    routing.append({'worker':role,'binding':b['name'],'class':b['class_name'],'target_worker':target})
                    bindings.append(f'(name={j(b["name"])},durableObjectNamespace=(className={j(b["class_name"])},serviceName={j(target)}))')
                for b in project.get('worker_loaders',[]):bindings.append(f'(name={j(b["binding"])},workerLoader=())')
                for b in project.get('services',[]):
                    target=role if b['service']==project['name'] else names[b['service']]
                    bindings.append(f'(name={j(b["binding"])},service=(name={j(target)}'+(f',entrypoint={j(b["entrypoint"])}' if b.get('entrypoint') else '')+(f',props=(json={j(j(b["props"]))})' if 'props' in b else '')+'))')
                for name,value in project.get('vars',{}).items():bindings.append(f'(name={j(name)},'+('text='+j(value) if isinstance(value,str) else 'json='+j(j(value)))+')')
                ns=','.join(f'(className={j(c)},uniqueKey={j(role+"-"+c)},enableSql=true)' for c in classes)
                services.append(f'(name={j(role)},worker=(globalOutbound="internet",compatibilityDate={j(project.get("compatibility_date","2026-01-01"))},compatibilityFlags={j(flags)},modules=[(name="worker",esModule=embed {j(bundle.name)}){extra_modules}],bindings=[{",".join(bindings)}],durableObjectNamespaces=[{ns}],durableObjectStorage=(localDisk="disk")))')
        services.append('(name="internet",network=(allow=["private","local"]))')
        disk=self.out/'workerd-storage';disk.mkdir()
        services.append(f'(name="disk",disk=(path={j(str(disk))},writable=true))')
        sockets=[f'(name="http",address="127.0.0.1:{self.port}",http=(),service="main")']
        if split:
            sockets.append(f'(name="owner",address="127.0.0.1:{self.port+3}",http=(),service="owner")')
            sockets.append(f'(name="private-origin",address="127.0.0.1:{self.port+11}",http=(),service="owner")')
        v8_flags=['--max-heap-size=128'] if self.guard and self.guard.profile else []
        path=self.out/'workerd.capnp';path.write_text('using Workerd = import "/workerd/workerd.capnp";\nconst config :Workerd.Config = (v8Flags='+j(v8_flags)+',services=['+','.join(services)+'],sockets=['+','.join(sockets)+']);\n')
        dump(self.out/'oracle-routing.json',{'bindings':routing,'v8_flags':v8_flags,'configuration_sha256':sha(path),'policy':'ROOT/Cell coordinator graphs keep callbacks in the existing caller namespace; source assertions unchanged'})
        return path
    def stop(self):
        if self.process:self.process.stop();self.process=None
        if self.store:self.store.stop();self.store=None
        if self.guard:self.guard.finish()
