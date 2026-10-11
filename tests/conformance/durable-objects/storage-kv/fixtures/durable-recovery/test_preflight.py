"""Pure guard/schema checks. These are not runtime cases and add no authored count."""
import ast, copy, importlib.util, json, pathlib, signal, unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('drs_driver_static',HERE/'driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
def guard():
    hashes=driver.pins()
    return {'exclusive_run_slot':True,'owned_disposable_fleet':True,'transfer_cleanup_ownership':True,'binary_sha256':driver.BINARY,'implementation_hashes':hashes,'reviewed_implementation_hashes':hashes,'reviewed_case_ids':['D001'],'profile':'bucket','run_id':'0123456789abcdef','profile_sha256':driver.digest(HERE/'bucket-profile.json'),'qemu_limits_verified':True,'guest_cgroup_limits_verified':True,'review_evidence':'test-only-no-admission','limits_evidence':'test-only-no-admission','deployment_evidence':'test-only-no-admission'}
class GuardTests(unittest.TestCase):
    def test_guard_schema_only_accepts_complete_values(self):driver.validate_guard(guard(),'D001')
    def test_empty_guard_blocks(self):
        with self.assertRaises(driver.Blocked):driver.validate_guard({},'D001')
    def test_stale_source_blocks(self):
        g=guard();g['implementation_hashes']={}
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_stale_review_blocks(self):
        g=guard();g['reviewed_implementation_hashes']={}
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_unreviewed_case_blocks(self):
        with self.assertRaises(driver.Blocked):driver.validate_guard(guard(),'D002')
    def test_fleet_blocks(self):
        g=guard();g['profile']='fleet'
        with self.assertRaisesRegex(driver.Blocked,'witness'):driver.validate_guard(g,'D001')
    def test_unowned_cleanup_blocks(self):
        g=guard();g['transfer_cleanup_ownership']=False
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_unbounded_guest_blocks(self):
        g=guard();g['guest_cgroup_limits_verified']=False
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_wrong_binary_blocks(self):
        g=guard();g['binary_sha256']='wrong'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_nonfresh_id_shape_blocks(self):
        g=guard();g['run_id']='../unowned'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_stale_profile_blocks(self):
        g=guard();g['profile_sha256']='wrong'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
    def test_missing_evidence_blocks(self):
        g=guard();g['review_evidence']=''
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'D001')
class ControlPathTests(unittest.TestCase):
    """Negative runner control-path regression tests; no SUT or real process fixture."""
    def test_trace_entry_is_receiver_witnessed(self):
        tree=ast.parse((HERE/'driver.py').read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Driver')
        methods={x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}
        batch=ast.get_source_segment((HERE/'driver.py').read_text(),methods['batch'])
        waiting=ast.get_source_segment((HERE/'driver.py').read_text(),methods['waiting'])
        self.assertNotIn('self.trace_entered=True',batch)
        self.assertLess(waiting.index('self.wait(ready'),waiting.index('self.trace_entered=True'))
    def test_deadline_bypasses_ordinary_exception_handlers(self):
        self.assertTrue(issubclass(driver.CaseDeadline,BaseException))
        self.assertFalse(issubclass(driver.CaseDeadline,Exception))
    def test_failed_initializer_retains_cleanup_owner(self):
        cleaned=[]
        def broken(instance,*args):
            instance.cleanup_authorized=True
            raise driver.Blocked('controlled initialization failure after transfer')
        def cleanup(instance,force=False):
            cleaned.append(instance.cleanup_authorized)
            return {'status':'ok','scope':'unit-test-no-guests'}
        with patch.object(driver.Driver,'__init__',broken),patch.object(driver.Driver,'cleanup',cleanup):
            result=driver.run_case([],{},'D001')
        self.assertEqual(cleaned,[True]);self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['traceEntered'])
    def test_sigterm_enters_cleanup_and_restores_handler(self):
        previous=signal.getsignal(signal.SIGTERM);cleaned=[]
        def interrupted(instance,*args):
            instance.cleanup_authorized=True
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        def cleanup(instance,force=False):
            cleaned.append(True);return {'status':'ok','scope':'unit-test-no-guests'}
        with patch.object(driver.Driver,'__init__',interrupted),patch.object(driver.Driver,'cleanup',cleanup):
            result=driver.run_case([],{},'D001')
        self.assertEqual(cleaned,[True]);self.assertEqual(result['status'],'BLOCKED');self.assertEqual(signal.getsignal(signal.SIGTERM),previous)
    def test_cleanup_deadline_enters_forced_path(self):
        calls=[]
        def broken(instance,*args):
            instance.cleanup_authorized=True
            raise driver.Blocked('controlled initializer failure')
        def cleanup(instance,force=False):
            calls.append(force)
            if not force:raise driver.CaseDeadline('controlled cleanup deadline')
            return {'status':'ok','scope':'unit-test-no-guests'}
        with patch.object(driver.Driver,'__init__',broken),patch.object(driver.Driver,'cleanup',cleanup):
            result=driver.run_case([],{},'D001')
        self.assertEqual(calls,[False,True]);self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['cleanup']['status'],'FAILED')
if __name__=='__main__':unittest.main()
