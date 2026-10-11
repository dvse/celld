"""No-network adapter acceptance falsification, never an SUT run."""
import copy,importlib.util,pathlib
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('graph_adapter',HERE/'run.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
origin={'root':'synthetic-owned-root','name':'synthetic','isolate':'synthetic-isolate'}
value={'requestId':'synthetic-request','id':'M007','profile':mod.PROFILE,'compatibilityDate':'2026-09-04','origin':origin,'status':'PASS','traceEntered':True,'phase':'complete','evidence':{},'cleanup':{'status':'ok','drained':True,'pending':[],'unsettledRpcCount':0,'errors':[],'workers':1,'startupStates':['fulfilled'],'unsettledStartupCount':0,'outerTasks':[{'label':'setup','settled':True},{'label':'trace','settled':True}],'unsettledTaskCount':0}}
mod.validate_terminal(value,'synthetic-request','M007',origin)
checks=[('requestId','wrong'),('traceEntered',False),('phase','trace'),('compatibilityDate','2026-01-01'),('evidence',None),('cleanup',{'status':'ok','drained':False,'pending':['unresolved'],'unsettledRpcCount':1,'errors':[]})]
for key,replacement in checks:
 candidate=copy.deepcopy(value);candidate[key]=replacement
 try:mod.validate_terminal(candidate,'synthetic-request','M007',origin)
 except ValueError:continue
 raise AssertionError('unsafe receipt accepted:'+key)
for key,replacement in [('unsettledTaskCount',1),('outerTasks',[{'label':'setup','settled':True}]),('unsettledStartupCount',1),('startupStates',['pending'])]:
 candidate=copy.deepcopy(value);candidate['cleanup'][key]=replacement
 try:mod.validate_terminal(candidate,'synthetic-request','M007',origin)
 except ValueError:continue
 raise AssertionError('unsafe ownership receipt accepted:'+key)
print('No-network adapter receipt checks: 1 valid synthetic receipt and 10 invalid receipts; actual SUT runs=0.')
