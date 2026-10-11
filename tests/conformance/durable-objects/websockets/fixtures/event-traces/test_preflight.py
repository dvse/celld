"""Tiny no-network helper regressions. These are not authored celld stress cases."""
import importlib.util,pathlib,unittest
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ws_driver',HERE/'private_driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
class Guards(unittest.TestCase):
 def test_missing_guard_blocks(self):
  with self.assertRaises(driver.Blocked):driver.validate_guard({},'W001')
 def test_unknown_case_blocks(self):
  with self.assertRaises(driver.Blocked):driver.validate_guard({},'W999')
 def test_no_public_or_credential_origin(self):
  for origin in ('http://example.com:18080','http://8.8.8.8:18080','http://192.168.77.1:18080/path','http://x:y@192.168.77.1:18080','http://169.254.1.1:18080'):
   with self.assertRaises(driver.Blocked):driver.origin(origin)
 def test_private_literal_origin(self):self.assertEqual(driver.origin('http://192.168.77.1:18080'),'http://192.168.77.1:18080')
 def test_characterization_cannot_promote(self):
  with self.assertRaises(driver.Blocked):driver.finalize({'characterization':True},{})
 def test_uncertain_entry_cannot_promote(self):
  with self.assertRaises(driver.Blocked):driver.finalize({'semantic_status':'PASS','traceEntered':None},{})
 def test_incomplete_receipt_blocks(self):
  with self.assertRaises(driver.Blocked):driver.validate_terminal({'status':'PASS'},'W001',{'run_id':'1234567890abcdef'})
if __name__=='__main__':unittest.main()
