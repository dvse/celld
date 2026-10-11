#!/usr/bin/env python3
"""No-network guard/receipt regressions. Prepared, NOT RUN during syntax-only authoring."""
import copy, importlib.util, pathlib, unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('http_adapter',HERE/'private_driver.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
class GuardTests(unittest.TestCase):
 def test_missing_guard_blocks_before_network(self):
  with patch.object(adapter.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):
   result=adapter.run_case('H001',{})
  self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['traceEntered']);self.assertNotIn('dispatch_attempted',result)
  self.assertEqual(result['blocker']['type'],'BLOCKED_PREREQUISITE')
 def test_unknown_case_blocks(self):
  with patch.object(adapter.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):
   result=adapter.run_case('H999',{})
  self.assertEqual(result['status'],'BLOCKED');self.assertIn('unknown case',result['error'])
 def test_origin_refusals(self):
  for origin in ['http://example.com:18080','http://8.8.8.8:18080','http://169.254.1.1:18080','http://127.0.0.1:8080','https://127.0.0.1:18080','http://user@127.0.0.1:18080','http://127.0.0.1:18080/path','http://[::1]:18080']:
   with self.subTest(origin=origin),self.assertRaises(adapter.Blocked):adapter.origin(origin)
 def test_no_semantic_result_cannot_finalize(self):
  with self.assertRaises(adapter.Blocked):adapter.finalize({'id':'H001','status':'BLOCKED','traceEntered':False},{})
 def receipt(self):
  caller={'root':'caller','isolate':'caller-isolate','profile':adapter.PROFILE};recipient={'root':'recipient','isolate':'recipient-isolate','profile':adapter.PROFILE}
  guard={'run_id':'1234567890abcdef','caller':{'identity':caller},'recipient':{'identity':recipient}}
  receipt={'id':'H001','run':guard['run_id'],'profile':adapter.PROFILE,'caller':caller,'recipient':recipient,'status':'PASS','traceEntered':True,'phase':'complete','evidence':{'events':[{'kind':'identities','caller':caller,'recipient':recipient},{'kind':'recovery','label':'recovery'}],'logicalPayloadAllowance':1024,'maxNetworkRequests':4,'networkAttempts':20,'wallMs':1200},'cleanup':{'status':'ok','remote':{**recipient,'run':guard['run_id'],'status':'ok','active':0,'readers':0,'controllers':0},'local':{'live':0,'readers':0,'responses':0,'pending':0}}}
  return guard,receipt
 def test_valid_receipt_is_not_runtime_evidence(self):
  guard,value=self.receipt();adapter.validate_terminal(value,'H001',guard)
  # Synthetic validator input is never fed to run_case/finalize or saved as runtime PASS.
 def test_reject_uncorrelated_or_incomplete_pass(self):
  guard,original=self.receipt()
  for field,bad in [('id','H002'),('run','fedcba0987654321'),('profile','other'),('traceEntered',False),('phase','trace'),('recipient',{'root':'other'}),('cleanup',{})]:
   value=copy.deepcopy(original);value[field]=bad
   with self.subTest(field=field),self.assertRaises(adapter.Blocked):adapter.validate_terminal(value,'H001',guard)
  for field,bad in [('logicalPayloadAllowance',4194305),('maxNetworkRequests',7),('networkAttempts',161),('wallMs',24001),('events',[])]:
   value=copy.deepcopy(original);value['evidence'][field]=bad
   with self.subTest(field=field),self.assertRaises(adapter.Blocked):adapter.validate_terminal(value,'H001',guard)
 def test_matching_blocked_precondition(self):
  guard,base=self.receipt();base.update(status='BLOCKED',traceEntered=False,phase='precondition',blocker={'type':'BLOCKED_PREREQUISITE','detail':'fresh root missing'})
  base.pop('recipient');adapter.validate_terminal(base,'H001',guard)
 def test_entered_failure_retains_overbudget_evidence(self):
  guard,value=self.receipt();value.update(status='FAIL',phase='trace');value['evidence']['wallMs']=24001
  adapter.validate_terminal(value,'H001',guard)
if __name__=='__main__':unittest.main()
