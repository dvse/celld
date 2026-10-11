"""Tiny synthetic receipt/guard regressions; network constructor is replaced with a rejecting stub."""
import copy,importlib.util,pathlib,unittest
P=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('redirect_adapter',P/'private_driver.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Checks(unittest.TestCase):
 def setUp(self):
  self.caller={'root':'caller','isolate':'caller-isolate','profile':a.PROFILE};self.recipient={'root':'recipient','isolate':'recipient-isolate','profile':a.PROFILE}
  self.guard={'run_id':'0123456789abcdef','caller':{'identity':self.caller},'recipient':{'identity':self.recipient}}
  remote={**self.recipient,'run':self.guard['run_id'],'status':'ok','active':0,'readers':0,'controllers':0,'pulls':0,'journal':{**self.recipient,'run':self.guard['run_id'],'requests':5,'active':0,'pulls':0,'faults':[],'events':[{'name':'recovery','kind':'effect','value':1}],'ops':[{'name':'recovery','entered':1,'effect':1,'inputTerminal':'eof','inputBytes':131,'outputBytes':31,'active':False}]}}
  self.good={'id':'F001','run':self.guard['run_id'],'profile':a.PROFILE,'caller':self.caller,'recipient':self.recipient,'status':'PASS','phase':'complete','traceEntered':True,'cleanup':{'status':'ok','remote':remote,'local':dict(live=0,readers=0,responses=0,pending=0,controllers=0)},'evidence':{'events':[{'kind':'identities','caller':self.caller,'recipient':self.recipient},{'kind':'recovery','label':'recovery'}],'logicalPayloadAllowance':100,'maxNetworkRequests':2,'networkAttempts':5,'wallMs':1}}
 def test_accept_correlated_synthetic_receipt(self):a.validate_terminal(self.good,'F001',self.guard)
 def test_reject_bad_receipts(self):
  paths=[('recipient','root'),('cleanup','remote','pulls'),('cleanup','local','controllers'),('cleanup','remote','journal','faults'),('cleanup','remote','journal','active'),('evidence','networkAttempts'),('evidence','wallMs'),('cleanup','remote','journal','ops'),('cleanup','remote','journal','events'),('cleanup','remote','journal','requests')]
  values=['wrong',1,1,['assertion'],1,161,24001,[],[],185]
  for path,value in zip(paths,values):
   with self.subTest(path=path):
    bad=copy.deepcopy(self.good);target=bad
    for k in path[:-1]:target=target[k]
    target[path[-1]]=value
    with self.assertRaises(a.Blocked):a.validate_terminal(bad,'F001',self.guard)
 def test_cleanup_block_is_not_pass(self):
  x=copy.deepcopy(self.good);x.update(status='BLOCKED',phase='cleanup',blocker={'type':'BLOCKED_CLEANUP'});a.validate_terminal(x,'F001',self.guard);self.assertEqual(x['status'],'BLOCKED')
 def test_no_guard_never_constructs_network(self):
  old=a.http.client.HTTPConnection
  def forbidden(*args,**kw):raise AssertionError('network attempted by no-guard adapter')
  a.http.client.HTTPConnection=forbidden
  try:r=a.run_case('F001',{});self.assertEqual(r['status'],'BLOCKED');self.assertFalse(r.get('dispatch_attempted',False));self.assertIn('exclusive_run_slot',str(r['blocker']))
  finally:a.http.client.HTTPConnection=old
if __name__=='__main__':unittest.main()
