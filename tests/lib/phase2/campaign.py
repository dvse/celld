"""Source-authored campaign assertions inside bounded owned execution domains."""
import json,time,traceback
from pathlib import Path
from common import ROOT,dump,result,safe_id
from runtime import Runtime,Unavailable,fetch
from .topology import stage,classify
from .fleet import Fleet
from .guard import Guard

def profile(wave):
 # Limits transcribed from the immutable schedule.json / README source contracts.
 limits={
 'd1-semantics':(30,30,700,2048,256,128,1048576),
 'kv-semantics':(30,30,700,2048,256,128,1048576),
 'r2-semantics':(15,20,450,1024,256,128,65536),
 'facet-root-semantics':(12,20,420,1024,256,128,65536),
 'identity-admission-semantics':(12,20,120,1024,256,128,65536),
 'os-typed-storage-semantics':(10,15,120,1024,128,32,65536),
 'atomic-accounting-semantics':(12,15,240,1024,256,128,65536),
 'os-action-file-store-semantics':(10,15,120,1024,128,32,32768),
 'storage-sql-semantics':(10,15,360,1024,256,128,65536),
 'body-form-semantics':(5,5,300,1024,256,128,65536),
 'headers-semantics':(5,10,180,1024,256,128,65536),
 'pipe-cleanup-semantics':(5,5,180,512,256,128,65536),
 'response-clone-chunk-semantics':(5,5,300,1024,256,128,65536),
 'stream-backpressure-semantics':(5,5,180,512,256,128,65536),
 'url-semantics':(5,5,300,1024,256,128,65536),
 'os-git-codec-semantics':(10,15,150,512,128,32,16384)}
 http,case,wave_s,rss,disk,pids,response=limits[wave]
 return {'source_wave':wave,'http_seconds':http,'case_seconds':case,'wave_seconds':wave_s,'rss_bytes':rss*1024**2,'disk_bytes':disk*1024**2,'pids':pids,'response_bytes':response,'cpu_seconds':300 if wave in ('d1-semantics','kv-semantics') else wave_s,'startup_seconds':90 if wave in ('pipe-cleanup-semantics','stream-backpressure-semantics') else 120,'cleanup_seconds':5 if wave=='os-git-codec-semantics' else 20,'fresh_process_per_case':wave=='os-git-codec-semantics','source_cleanup_override':'operator requires retaining state/evidence; all bytes are archived and verified before releasing disposable quota mount'}

def run_group(cases,runtimes,out):
 out.mkdir(parents=True,exist_ok=True);wave=cases[0]['corpus_wave'];limits=profile(wave);rows=[];observations={};dump(out/'source-resource-profile.json',limits)
 for runtime in runtimes:
  wave_start=time.monotonic();batches=[[c] for c in cases] if limits['fresh_process_per_case'] else [cases]
  for batch in batches:
   directory=out/runtime/(safe_id(batch[0]['id']) if limits['fresh_process_per_case'] else 'wave');rt=None;fleet=None;guard=None;batch_rows=[];source=None;workspace=None
   try:
    guard=Guard(directory,limits);workspace=guard.workspace
    guard.begin('startup',limits['case_seconds'] if limits['fresh_process_per_case'] else limits['startup_seconds'])
    source=stage(ROOT/batch[0]['fixture'],workspace,wave)
    if runtime=='celld':
     fleet=Fleet.__new__(Fleet);fleet.__init__(source,workspace/'runtime',width=1,resource_guard=guard);port=9820
    else:
     rt=Runtime.__new__(Runtime);rt.__init__(source,runtime,workspace/'runtime',False,True,resource_guard=guard);port=rt.port
    if not limits['fresh_process_per_case']:guard.end()
    for case in batch:
     if not limits['fresh_process_per_case']:guard.begin(case['id'],limits['case_seconds'])
     art=workspace/'runtime'/(safe_id(case['id'])+'.json');t=time.monotonic()
     try:
      if time.monotonic()-wave_start>limits['wave_seconds']:raise RuntimeError('whole-wave deadline exceeded before entry')
      if guard.violations:raise RuntimeError('resource guard rejected preconditions before entry')
      value=fetch(port,{'path':'/case/'+case['selector'],'timeout':limits['http_seconds'],'max_response_bytes':limits['response_bytes']});dump(art,value);observations[(case['id'],runtime)]=value;body=value['body'];assertion_body=body.get('finished',body) if isinstance(body,dict) else {}
      status,reason=classify({'response':value})
      if status=='pass' and (not isinstance(assertion_body.get('assertions'),list) or not assertion_body['assertions']):status='fail';reason='missing nonempty source-authored assertion trace'
      if status=='pass' and (body.get('traceSettled') is False or (isinstance(assertion_body.get('cleanup'),dict) and assertion_body['cleanup'].get('verified') is False)):status='fail';reason='trace or cleanup not verified'
      if status=='pass':reason='source-authored assertions and fixture cleanup passed; kernel-bounded owned domain reaped'
     except Exception as e:status='fail';reason=str(e);dump(art.with_suffix('.error.json') if art.exists() else art,{'error':str(e),'traceback':traceback.format_exc()})
     if not limits['fresh_process_per_case']:guard.end()
     batch_rows.append(result(case,runtime,status,reason,int((time.monotonic()-t)*1000),[art,workspace/'runtime/fleet.json',workspace/'runtime/runtime.json',workspace/'runtime/oracle-routing.json',workspace/'staging.json',workspace/'pako-build.json',out/'source-resource-profile.json']))
   except Exception as e:
    art=directory/'setup-error.json';dump(art,{'error':str(e),'traceback':traceback.format_exc()});why=str(e)
    if isinstance(e,Unavailable):why='Official stock workerd does not supply a local service implementation for this KV/D1/R2 binding; candidate executes its built-in backend'
    batch_rows.extend(result(c,runtime,'not-applicable' if isinstance(e,Unavailable) else 'fail',why,artifacts=[art,out/'source-resource-profile.json']) for c in batch if not any(r['id']==c['id'] for r in batch_rows))
   finally:
    cleanup=time.monotonic()
    if rt:rt.stop()
    if fleet:fleet.close()
    if guard:
     receipt=guard.finish()
     # finish copies every working file before releasing the private namespace.
     for row in batch_rows:
      row['artifacts']=[p.replace(str(workspace),str(directory/'retained')) for p in row['artifacts']]
      row['artifacts'].append(str(directory/'resource-guard.json'))
      if receipt['violations']:row.update(status='fail',reason='independent resource/deadline guard rejected qualification; see resource-guard.json')
      if time.monotonic()-cleanup>limits['cleanup_seconds'] or time.monotonic()-wave_start>limits['wave_seconds']:
       row.update(status='fail',reason='external cleanup/whole-wave deadline exceeded; evidence retained')
    rows.extend(batch_rows)
 for case in cases:
  a=observations.get((case['id'],'celld'));b=observations.get((case['id'],'workerd'))
  if a is not None and b is not None:
   def view(v):
    body=v['body'];return {'http_status':v['status'],'status':body.get('status',body.get('fixtureStatus')),'assertions':body.get('assertions',body.get('finished',{}).get('assertions'))} if isinstance(body,dict) else v
   av,bv=view(a),view(b)
   if av!=bv:
    artifact=out/(safe_id(case['id'])+'.comparison.json');dump(artifact,{'celld':av,'workerd':bv,'verdict':'different source-authored assertion observations'})
    for row in rows:
     if row['id']==case['id']:row['artifacts'].append(str(artifact));row['reason']+='; stock/candidate observations differ'
 return rows
