"""Tiny synthetic guard/receipt regressions, not observed runtime evidence."""
import copy,importlib.util,json,pathlib,unittest
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('native_driver',HERE/'private_driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
class GuardTests(unittest.TestCase):
 def test_missing_guard_blocks_before_any_network(self):
  class NoNetwork:
   def __init__(self,*args,**kwargs):raise AssertionError('network must not be reached')
  prior=driver.PrivateClient;driver.PrivateClient=NoNetwork
  try:
   result=driver.run_case('X001',{})
   self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result.get('dispatch_attempted',False))
  finally:driver.PrivateClient=prior
 def test_public_destination_is_rejected(self):
  with self.assertRaises(driver.Blocked):driver.origin('http://8.8.8.8:18080')
 def test_credentials_are_rejected(self):
  with self.assertRaises(driver.Blocked):driver.origin('http://user:pass@127.0.0.1:18080')
 def test_missing_trace_cannot_be_pass(self):
  guard={'run_id':'0123456789abcdef','roots':{'caller':{'identity':{'root':'caller'}}}}
  with self.assertRaises(driver.Blocked):driver.validate_terminal({'id':'X001','run':guard['run_id'],'profile':driver.PROFILE,'caller':{'root':'caller'},'status':'PASS','traceEntered':False},'X001',guard)
 def test_no_semantic_receipt_cannot_finalize(self):
  with self.assertRaises(driver.Blocked):driver.finalize({'status':'BLOCKED'}, {})
class ReceiptTests(unittest.TestCase):
 def fixture(self):
  run='0123456789abcdef';identities={role:{'root':role,'instance':'synthetic-'+role,'profile':driver.PROFILE} for role in ['caller','primary','secondary']}
  guard={'run_id':run,'roots':{role:{'identity':identity} for role,identity in identities.items()}}
  events=[]
  rows=[('main-enter','X001','primary'),('held','prefix-encoder','primary'),('peer-enter','raw','secondary'),('peer-done','raw','secondary'),('released','prefix-encoder','primary'),('main-done','X001','primary')]
  for i,(kind,label,role) in enumerate(rows):events.append({'run':run,'kind':kind,'label':label,'recipient':identities[role],'requestId':run+(':'+role+':1' if role=='primary' else ':'+role+':2'),'sequence':i})
  receipts=[];remote=[]
  for kind,role,operation,number in [('main','primary','X001',1),('peer','secondary','raw',2)]:
   request=run+':'+role+':'+str(number)
   cleanup={'status':'ok','run':run,'requestId':request,'recipient':identities[role],'pending':0,'bodyPending':False,'bodyStarted':True,'unreleasedHandles':0,'disposed':True,'jsDisposed':True,'nativeUnresolved':0,'failures':[],'actions':[],'unhandledRejections':[],'openOperations':0,'fixtureHandlesReleased':2,'maxOpenOperations':1,'totalBytes':8192}
   receipts.append({'run':run,'kind':kind,'id':operation,'requestId':request,'recipient':identities[role],'traceEntered':True,'status':'PASS','errors':[],'value':{'synthetic':'not runtime evidence'},'cleanup':cleanup})
   remote.append({'run':run,'recipient':identities[role],'status':'ok','active':0,'contexts':1,'allContextsDisposed':True,'residual':[{'disposed':True,'jsDisposed':True,'nativeUnresolved':0,'pending':0,'bodyPending':False,'bodyStarted':True,'unreleasedHandles':0,'openOperations':0}]})
  value={'id':'X001','run':run,'profile':driver.PROFILE,'caller':identities['caller'],'recipients':{k:identities[k] for k in ['primary','secondary']},'status':'PASS','phase':'complete','traceEntered':True,'traceEntryUnknown':False,'bodyReceiptMissing':False,'errors':[],'evidence':{'events':events,'receipts':receipts,'wallMs':100},'cleanup':{'run':run,'status':'ok','pending':0,'held':0,'failures':[],'remote':remote},'qualification':'PENDING_EXTERNAL_SUPERVISOR_REVIEW'}
  return value,guard
 def rejects_mutation(self,mutate):
  value,guard=self.fixture();driver.validate_terminal(value,'X001',guard);mutate(value)
  with self.assertRaises(driver.Blocked):driver.validate_terminal(value,'X001',guard)
 def test_sequential_peer_cannot_pass(self):
  self.rejects_mutation(lambda v:v['evidence']['events'].reverse())
 def test_missing_overlap_cannot_pass(self):
  self.rejects_mutation(lambda v:v['evidence']['events'].pop(1))
 def test_duplicate_request_cannot_pass(self):
  self.rejects_mutation(lambda v:v['evidence']['receipts'][1].update(requestId=v['evidence']['receipts'][0]['requestId']))
 def test_wrong_recipient_cannot_pass(self):
  self.rejects_mutation(lambda v:v['evidence']['receipts'][1].update(recipient=v['caller']))
 def test_pending_cleanup_cannot_pass(self):
  self.rejects_mutation(lambda v:v['evidence']['receipts'][0]['cleanup'].update(pending=1))
 def test_five_simultaneous_cannot_pass(self):
  def mutate(v):
   v['evidence']['receipts'][0]['cleanup']['maxOpenOperations']=3
   v['evidence']['receipts'][1]['cleanup']['maxOpenOperations']=2
  self.rejects_mutation(mutate)
 def test_stale_hold_label_cannot_pass(self):
  self.rejects_mutation(lambda v:v['evidence']['events'][1].update(label='another case'))
class UncertainDispatchTests(unittest.TestCase):
 def test_received_uncertainty_requires_teardown_and_no_retry(self):
  import types
  run='0123456789abcdef';identities={role:{'root':role,'instance':role+'-instance','profile':driver.PROFILE} for role in ('caller','primary','secondary')}
  guard={'run_id':run,'owner':{},'limits':{'case_wall_seconds':30},'roots':{r:{'name':r,'identity':v} for r,v in identities.items()},'origin':'http://127.0.0.1:18080'}
  # Legacy optional flag omitted intentionally. The adapter must preserve the explicit blocker.
  receipt={'id':'X001','run':run,'profile':driver.PROFILE,'caller':identities['caller'],'status':'BLOCKED','phase':'trace-unknown','traceEntered':False,'dispatchAttempted':True,'blocker':{'type':'BLOCKED_UNCERTAIN_DISPATCH','detail':'synthetic unavailable body receipt'},'cleanup':{'status':'UNKNOWN'}}
  class NoNetwork:
   def __init__(self,*args):pass
   def request(self,path,body=None):
    if path=='/health':return {'profile':driver.PROFILE,'caseIds':['X001']}
    if path=='/identity':return identities[body['name']]
    if path=='/run':return receipt
    raise AssertionError('unexpected route')
   def close(self):pass
  before=(driver.validate_guard,driver.PrivateClient,driver.signal)
  driver.validate_guard=lambda *args:None;driver.PrivateClient=NoNetwork
  driver.signal=types.SimpleNamespace(SIGALRM=1,ITIMER_REAL=0,setitimer=lambda *args:None,getitimer=lambda *args:(0.0,0.0),signal=lambda *args:None)
  try:result=driver.run_case('X001',guard)
  finally:driver.validate_guard,driver.PrivateClient,driver.signal=before
  self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['traceEntered']);self.assertTrue(result['traceEntryUnknown']);self.assertTrue(result['do_not_retry']);self.assertEqual(result['cleanup']['status'],'UNKNOWN');self.assertNotIn('semantic_status',result)
class NativeCleanupBlockerTests(unittest.TestCase):
 def test_unknown_native_cleanup_cannot_finalize(self):
  run='0123456789abcdef';identities={r:{'root':r,'instance':r,'profile':driver.PROFILE} for r in ['caller','primary','secondary']}
  guard={'run_id':run,'roots':{r:{'identity':v} for r,v in identities.items()}}
  receipt={'id':'X001','run':run,'profile':driver.PROFILE,'caller':identities['caller'],'recipients':{r:identities[r] for r in ['primary','secondary']},'traceEntered':True,'status':'BLOCKED','blocker':{'type':'BLOCKED_NATIVE_CLEANUP'},'evidence':{'events':[{'run':run,'kind':'main-enter','label':'X001','recipient':identities['primary'],'requestId':run+':primary:1'}],'receipts':[]}}
  driver.validate_terminal(receipt,'X001',guard)
  with self.assertRaises(driver.Blocked):driver.finalize({'status':'BLOCKED','traceEntered':True,'fixture_result':receipt},{'process_reaped':True})
if __name__=='__main__':unittest.main()
