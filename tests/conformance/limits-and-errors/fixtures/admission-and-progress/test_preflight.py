#!/usr/bin/env python3
"""No-network request-adapter guard/receipt checks, not SUT cases."""
import contextlib,importlib.util,io,json,pathlib,tempfile,unittest,sys
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('bounded_request_adapter',HERE/'run.py');adapter=importlib.util.module_from_spec(spec);spec.loader.exec_module(adapter)
class Preflight(unittest.TestCase):
 def test_no_guard_never_opens_socket(self):
  with tempfile.TemporaryDirectory(dir=HERE) as tmp:
   report=pathlib.Path(tmp)/'report.json'
   with patch.object(sys,'argv',['run.py','--case','B001','--report',str(report)]),patch.object(adapter.urllib.request,'build_opener',side_effect=AssertionError('network attempted')),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(adapter.main(),1)
   value=json.loads(report.read_text());self.assertEqual(value['status'],'BLOCKED');self.assertFalse(value['traceEntered']);self.assertNotIn('dispatch_attempted',value)
 def test_public_origin_never_opens_socket(self):
  with tempfile.TemporaryDirectory(dir=HERE) as tmp:
   report=pathlib.Path(tmp)/'report.json';guard=pathlib.Path(tmp)/'guard.json';guard.write_text('{}')
   with patch.object(sys,'argv',['run.py','--case','B001','--base-url','http://8.8.8.8:80','--guard',str(guard),'--report',str(report)]),patch.object(adapter.urllib.request,'build_opener',side_effect=AssertionError('network attempted')),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(adapter.main(),1)
   value=json.loads(report.read_text());self.assertEqual(value['status'],'BLOCKED');self.assertIn('RFC1918',value['error'])
 def test_loader_policy_block_never_opens_socket(self):
  with tempfile.TemporaryDirectory(dir=HERE) as tmp:
   report=pathlib.Path(tmp)/'report.json';guard=pathlib.Path(tmp)/'guard.json';guard.write_text('{}')
   with patch.object(sys,'argv',['run.py','--case','B020','--base-url','http://127.0.0.1:8080','--guard',str(guard),'--report',str(report)]),patch.object(adapter.urllib.request,'build_opener',side_effect=AssertionError('network attempted')),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(adapter.main(),1)
   value=json.loads(report.read_text());self.assertEqual(value['status'],'BLOCKED');self.assertIn('owner overlap/authorization review',value['error']);self.assertNotIn('dispatch_attempted',value)
 def test_pass_requires_correlation_trace_and_cleanup(self):
  origin={'root':'origin','isolate':'a'};owner={'root':'owner','isolate':'b'}
  base={'requestId':'request-token','id':'B001','profile':adapter.PROFILE,'origin':origin,'owner':owner,'status':'PASS','traceEntered':True,'phase':'complete','evidence':{},'cleanup':{'status':'ok'}}
  adapter.validate_terminal(base,'request-token','B001',origin,owner)
  for field,value in [('requestId','wrong'),('traceEntered',False),('cleanup',{'status':'FAIL'}),('phase','precondition')]:
   row={**base,field:value}
   with self.assertRaises(ValueError):adapter.validate_terminal(row,'request-token','B001',origin,owner)
if __name__=='__main__':unittest.main()
