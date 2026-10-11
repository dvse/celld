#!/usr/bin/env python3
"""Tiny mocked support checks only. No case assertion body, SQLite or SUT runs."""
import copy, importlib.util, pathlib, unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sqlite_adapter',HERE/'private_driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
class AdapterTests(unittest.TestCase):
 def test_missing_guard_never_opens_socket(self):
  with patch.object(driver.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):result=driver.run_case('T001',{})
  self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['traceEntered']);self.assertNotIn('dispatch_attempted',result);self.assertEqual(result['blocker']['type'],'BLOCKED_PREREQUISITE')
 def test_unknown_case_never_opens_socket(self):
  with patch.object(driver.http.client,'HTTPConnection',side_effect=AssertionError('network forbidden')):result=driver.run_case('T999',{})
  self.assertIn('unknown case',result['error']);self.assertNotIn('dispatch_attempted',result)
 def test_reject_destination_escape(self):
  for value in ['https://127.0.0.1:18080','http://example.com:18080','http://8.8.8.8:18080','http://169.254.1.1:18080','http://user@127.0.0.1:18080','http://127.0.0.1:8080','http://127.0.0.1:18080/path','http://[::1]:18080']:
   with self.subTest(value=value),self.assertRaises(driver.Blocked):driver.origin(value)
 def test_private_literal_origin(self):self.assertEqual(driver.origin('http://192.168.77.1:18080/'),'http://192.168.77.1:18080')
 def example(self,case_id='T011'):
  run='0123456789abcdef';identity=lambda value:{'root':value,'instance':value+'-instance','profile':driver.PROFILE}
  caller=identity('caller');primary=identity('primary');secondary=identity('secondary');request=run+':primary:1';peer=run+':primary:2'
  guard={'run_id':run,'roots':{'caller':{'identity':caller},'primary':{'identity':primary},'secondary':{'identity':secondary}}}
  event=lambda kind,label,request_id:{'run':run,'kind':kind,'label':label,'recipient':primary,'requestId':request_id}
  local={'run':run,'label':'body-enter:'+case_id,'recipient':primary,'requestId':request,'sequence':0}
  receipt={'run':run,'id':case_id,'requestId':request,'recipient':primary,'status':'PASS','traceEntered':True,'value':{'assertions':'synthetic-validator-input-only'},'cohort':{'queuedBeforeHold':True,'releaseBeforeContenderEntry':True},'localEvents':[local]}
  other={'run':run,'op':'cursor-peer','requestId':peer,'recipient':primary,'value':[],'localEvents':[]}
  cleanup=lambda who:{'run':run,'recipient':who,'status':'ok','active':0,'cursors':0,'timers':0}
  value={'id':case_id,'run':run,'profile':driver.PROFILE,'caller':caller,'recipients':{'primary':primary,'secondary':secondary},'status':'PASS','traceEntered':True,'phase':'complete','evidence':{'events':[event('trace-enter',case_id,request),event('held','cursor',request),event('peer-enter','cursor-peer',peer),event('mark','peer-done:cursor-peer',peer),event('released','cursor',request)],'receipts':[receipt,other],'wallMs':10},'cleanup':{'status':'ok','run':run,'pending':0,'held':0,'remote':[cleanup(primary),cleanup(secondary)]},'qualification':'PENDING_EXTERNAL_SUPERVISOR_REVIEW'}
  return guard,value
 def test_unknown_dispatch_is_preserved_without_entry_credit(self):
  guard,value=self.example();value.update(status='BLOCKED',traceEntered=False,phase='trace-unknown',dispatchAttempted=True,traceAttempted=True,traceEntryUnknown=True,blocker={'type':'BLOCKED_UNCERTAIN_DISPATCH'})
  driver.validate_terminal(value,'T011',guard)
  value['dispatchAttempted']=False
  with self.assertRaises(driver.Blocked):driver.validate_terminal(value,'T011',guard)
 def test_t014_is_nonpromoting(self):
  self.assertIn('T014',driver.CHARACTERIZATIONS)
 def test_synthetic_receipt_validates_without_becoming_runtime_evidence(self):
  guard,value=self.example();driver.validate_terminal(value,'T011',guard)
 def test_reject_identity_case_run_and_entry_mismatch(self):
  guard,base=self.example()
  for field,value in [('run','fedcba9876543210'),('id','T012'),('profile','other'),('caller',{}),('recipients',{}),('traceEntered',False),('cleanup',{})]:
   bad=copy.deepcopy(base);bad[field]=value
   with self.subTest(field=field),self.assertRaises(driver.Blocked):driver.validate_terminal(bad,'T011',guard)
 def test_reject_missing_body_and_per_request_witnesses(self):
  guard,base=self.example()
  for mutate in [lambda v:v['evidence']['receipts'][0].update(localEvents=[]),lambda v:v['evidence']['receipts'][0].update(requestId='wrong'),lambda v:v['evidence']['events'][1].update(requestId='wrong'),lambda v:v['evidence'].update(receipts=v['evidence']['receipts'][:1])]:
   value=copy.deepcopy(base);mutate(value)
   with self.assertRaises(driver.Blocked):driver.validate_terminal(value,'T011',guard)
 def test_same_request_cohort_needs_observed_queue_witness(self):
  guard,value=self.example('T001');value['evidence']['receipts'][0]['cohort']=None
  with self.assertRaises(driver.Blocked):driver.validate_terminal(value,'T001',guard)
 def test_characterization_cannot_be_mislabeled_for_promotion(self):
  guard,value=self.example('T021')
  with self.assertRaises(driver.Blocked):driver.validate_terminal(value,'T021',guard)
  value['qualification']='NONPROMOTING_PINNED_CHARACTERIZATION';driver.validate_terminal(value,'T021',guard)
 def test_typed_missing_schedule_remains_blocked_after_entry(self):
  guard,value=self.example('T031');value.update(status='BLOCKED',phase='trace',blocker={'type':'BLOCKED_SCHEDULE','detail':'unavailable continuation'})
  driver.validate_terminal(value,'T031',guard)
 def test_cleanup_timers_cannot_be_silently_left_running(self):
  guard,value=self.example();value['cleanup']['remote'][0]['timers']=1
  with self.assertRaises(driver.Blocked):driver.validate_terminal(value,'T011',guard)
 def test_finalize_requires_actual_semantic_result(self):
  with self.assertRaises(driver.Blocked):driver.finalize({'id':'T001','status':'BLOCKED'}, {})
if __name__=='__main__':unittest.main()
