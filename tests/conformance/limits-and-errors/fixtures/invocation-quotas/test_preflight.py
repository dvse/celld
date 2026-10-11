#!/usr/bin/env python3
"""No-network adapter tests only, not runtime proof."""
import contextlib,importlib.util,io,json,pathlib,sys,tempfile,unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('adapter',HERE/'run.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
class GuardTests(unittest.TestCase):
 def invoke(self,args):
  with tempfile.TemporaryDirectory(dir=HERE) as tmp:
   report=pathlib.Path(tmp)/'r.json';guard=pathlib.Path(tmp)/'g.json';guard.write_text('{}')
   args=[str(guard) if x=='GUARD' else x for x in args]
   with patch.object(sys,'argv',['run.py','--case','Q001','--report',str(report),*args]),patch.object(adapter.urllib.request,'build_opener',side_effect=AssertionError('network forbidden in static preflight')),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(adapter.main(),1)
   value=json.loads(report.read_text());self.assertEqual(value['status'],'BLOCKED');self.assertFalse(value['traceEntered']);self.assertNotIn('dispatch_attempted',value);return value
 def test_no_guard(self):self.assertIn('supervisor guard',self.invoke([])['error'])
 def test_public_endpoint(self):self.assertIn('RFC1918',self.invoke(['--base-url','http://8.8.8.8:8080','--guard','GUARD'])['error'])
 def test_missing_owner_review(self):self.assertIn('exclusive_run_slot',self.invoke(['--base-url','http://127.0.0.1:8080','--guard','GUARD'])['error'])
 def test_credentials(self):self.assertIn('credential-free',self.invoke(['--base-url','http://user@127.0.0.1:8080','--guard','GUARD'])['error'])
 def test_hostname(self):self.invoke(['--base-url','http://localhost:8080','--guard','GUARD'])
 def test_source_gap_cannot_dispatch(self):
  value=self.invoke(['--case','Q017','--base-url','http://127.0.0.1:8080','--guard','GUARD']);self.assertIn('execution BLOCKED',value['error'])
 def test_receipt_qualification(self):
  origin={'root':'r','isolate':'i'};base={'id':'Q001','requestId':'request','profile':adapter.PROFILE,'origin':origin,'status':'PASS','traceEntered':True,'phase':'complete','cleanup':{'status':'ok'},'evidence':{}}
  adapter.validate_terminal(base,'request','Q001',origin)
  for field,value in [('requestId','other'),('traceEntered',False),('phase','precondition'),('cleanup',{'status':'UNKNOWN'}),('evidence',None)]:
   with self.assertRaises(ValueError):adapter.validate_terminal({**base,field:value},'request','Q001',origin)
  with self.assertRaises(ValueError):adapter.validate_terminal({**base,'id':'Q010'},'request','Q010',origin)
  for ident in ['Q016','Q017','Q018']:
   with self.assertRaises(ValueError):adapter.validate_terminal({**base,'id':ident},'request',ident,origin)
if __name__=='__main__':unittest.main()
