"""Pure guard/receipt/control checks. They execute no guest, SUT, workload, or fault."""
import ast,importlib.util,json,pathlib,signal,time,unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('aes_pure_driver',HERE/'driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
def guard(runtime='candidate'):
    hashes=driver.pins()
    return {'exclusive_run_slot':True,'owned_disposable_fleet':True,'transfer_cleanup_ownership':True,'runtime':runtime,'binary_sha256':driver.BINARIES[runtime],'implementation_hashes':hashes,'reviewed_implementation_hashes':hashes,'reviewed_case_ids':['A001'],'profile':'bucket','run_id':'0123456789abcdef','profile_sha256':driver.digest(HERE/'bucket-profile.json'),'qemu_limits_verified':True,'guest_cgroup_limits_verified':True,'review_evidence':'unit-only-no-admission','limits_evidence':'unit-only-no-admission','deployment_evidence':'unit-only-no-admission'}
def receipt_driver():
    d=driver.Driver.__new__(driver.Driver);d.run_id='0123456789abcdef';d.case_id='A001';d.roots={'r':{'node':1,'identity':{'root':'native-root','isolate':'native-isolate'}}};d.trace_entered=False;d.events=[];d.deadline=time.monotonic()+360
    return d
def receipt(phase='armed'):
    return {'receipt':{'root':'native-root','isolate':'native-isolate','run_id':'0123456789abcdef','case_id':'A001','request':'q1','phase':phase,'now':100000},'value':{'alarm':101000}}
class GuardTests(unittest.TestCase):
    def test_exact_original_selected(self):driver.validate_guard(guard('original'),'A001')
    def test_exact_candidate_selected(self):driver.validate_guard(guard('candidate'),'A001')
    def test_empty_guard_blocks(self):
        with self.assertRaises(driver.Blocked):driver.validate_guard({},'A001')
    def test_runtime_must_be_explicit(self):
        g=guard();g.pop('runtime')
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
    def test_crossed_runtime_binary_blocks(self):
        g=guard();g['binary_sha256']=driver.BINARIES['original']
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
    def test_source_change_invalidates_review(self):
        g=guard();g['reviewed_implementation_hashes']={}
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
    def test_missing_case_review_blocks(self):
        with self.assertRaises(driver.Blocked):driver.validate_guard(guard(),'A002')
    def test_fleet_durability_blocks(self):
        g=guard();g['profile']='fleet'
        with self.assertRaisesRegex(driver.Blocked,'bucket-only'):driver.validate_guard(g,'A001')
    def test_ownership_transfer_required(self):
        g=guard();g['transfer_cleanup_ownership']=False
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
    def test_resource_evidence_required(self):
        g=guard();g['guest_cgroup_limits_verified']=False
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
    def test_stale_profile_blocks(self):
        g=guard();g['profile_sha256']='wrong'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
    def test_fresh_id_shape_required(self):
        g=guard();g['run_id']='../unowned'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'A001')
class ReceiptTests(unittest.TestCase):
    def test_case_operation_receipt_enters_trace(self):
        d=receipt_driver();self.assertEqual(d.verify_receipt('r','arm','q1',receipt()),{'alarm':101000});self.assertTrue(d.trace_entered)
    def test_read_receipt_does_not_enter_trace(self):
        d=receipt_driver();d.verify_receipt('r','inspect','q1',receipt('observed'));self.assertFalse(d.trace_entered)
    def test_generic_prepare_does_not_enter_trace(self):
        d=receipt_driver();d.verify_receipt('r','prepare','q1',receipt('prepared'));self.assertFalse(d.trace_entered)
    def test_wrong_request_cannot_enter(self):
        d=receipt_driver()
        with self.assertRaises(driver.Blocked):d.verify_receipt('r','arm','other',receipt())
        self.assertFalse(d.trace_entered)
    def test_wrong_root_cannot_enter(self):
        d=receipt_driver();x=receipt();x['receipt']['root']='different-root'
        with self.assertRaises(driver.Blocked):d.verify_receipt('r','arm','q1',x)
        self.assertFalse(d.trace_entered)
    def test_wrong_run_cannot_enter(self):
        d=receipt_driver();x=receipt();x['receipt']['run_id']='stale-run'
        with self.assertRaises(driver.Blocked):d.verify_receipt('r','arm','q1',x)
        self.assertFalse(d.trace_entered)
    def test_wrong_case_cannot_enter(self):
        d=receipt_driver();x=receipt();x['receipt']['case_id']='A028'
        with self.assertRaises(driver.Blocked):d.verify_receipt('r','arm','q1',x)
        self.assertFalse(d.trace_entered)
    def test_wrong_phase_cannot_enter(self):
        d=receipt_driver()
        with self.assertRaises(driver.Blocked):d.verify_receipt('r','arm','q1',receipt('observed'))
        self.assertFalse(d.trace_entered)
    def test_missing_receiver_is_blocked(self):
        d=receipt_driver()
        with self.assertRaises(driver.Blocked):d.verify_receipt('r','arm','q1',{'value':{}})
    def test_expired_native_gate_is_blocked(self):
        d=receipt_driver();d.op=lambda *a,**k:{'entries':[{'terminal':'gate-expired'}]}
        with self.assertRaisesRegex(driver.Blocked,'gate expired'):d.snapshot('r')
    def test_missed_predue_window_is_blocked(self):
        d=receipt_driver();d.snapshot=lambda r:{'now':1000,'entries':[]}
        with self.assertRaisesRegex(driver.Blocked,'window missed'):d.before_due('r',1100)
    def test_http_program_parses_without_execution(self):
        d=receipt_driver();seen=[]
        def capture(node,source,timeout):ast.parse(source);seen.append(source);return {'captured':True}
        d.py=capture;self.assertEqual(d.http(2,'http://192.168.77.1:18080/op',{'root':'r'}),{'captured':True});self.assertEqual(len(seen),1)
    def test_public_endpoint_rejected_before_guest_call(self):
        d=receipt_driver();d.py=lambda *a,**k:self.fail('guest call should not run')
        with self.assertRaises(driver.Blocked):d.http(2,'https://example.com/op')
class LifecycleTests(unittest.TestCase):
    def test_baseexception_deadline(self):
        self.assertTrue(issubclass(driver.CaseDeadline,BaseException));self.assertFalse(issubclass(driver.CaseDeadline,Exception))
    def test_no_case_entry_from_batch_dispatch(self):
        source=(HERE/'driver.py').read_text();tree=ast.parse(source);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Driver')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='batch');self.assertNotIn('trace_entered=True',ast.get_source_segment(source,method))
    def test_failed_init_keeps_transferred_cleanup_owner(self):
        calls=[]
        def broken(instance,*args):instance.cleanup_authorized=True;raise driver.Blocked('unit-only controlled initialization failure')
        def cleanup(instance,force=False):calls.append(instance.cleanup_authorized);return {'status':'ok','unit_only':True}
        with patch.object(driver.Driver,'__init__',broken),patch.object(driver.Driver,'cleanup',cleanup):result=driver.run_case([],{},'A001')
        self.assertEqual(calls,[True]);self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['traceEntered'])
    def test_cleanup_deadline_enters_bounded_forced_path(self):
        calls=[]
        def broken(instance,*args):instance.cleanup_authorized=True;raise driver.Blocked('unit-only setup failure')
        def cleanup(instance,force=False):
            calls.append(force)
            if not force:raise driver.CaseDeadline('unit-only teardown expiry')
            return {'status':'ok','unit_only':True}
        with patch.object(driver.Driver,'__init__',broken),patch.object(driver.Driver,'cleanup',cleanup):result=driver.run_case([],{},'A001')
        self.assertEqual(calls,[False,True]);self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['cleanup']['status'],'FAILED')
    def test_sigterm_restores_original_handler(self):
        previous=signal.getsignal(signal.SIGTERM);calls=[]
        def interrupted(instance,*args):instance.cleanup_authorized=True;signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        def cleanup(instance,force=False):calls.append(True);return {'status':'ok','unit_only':True}
        with patch.object(driver.Driver,'__init__',interrupted),patch.object(driver.Driver,'cleanup',cleanup):result=driver.run_case([],{},'A001')
        self.assertEqual(calls,[True]);self.assertEqual(result['status'],'BLOCKED');self.assertEqual(signal.getsignal(signal.SIGTERM),previous)
class StaticFixtureTests(unittest.TestCase):
    def test_alarm_has_only_one_public_probe_path(self):
        source=(HERE/'fixture.js').read_text();self.assertEqual(source.count('root.alarm('),1);self.assertNotIn('__fireAlarm',source);self.assertNotIn('this.alarm(',source)
    def test_no_denied_capability_path(self):
        source=(HERE/'fixture.js').read_text();self.assertNotIn('getEntrypoint',source);self.assertNotIn('RpcTarget',source);self.assertNotIn('STATELESS',source)
    def test_real_alarm_transaction_calls_exist(self):
        source=(HERE/'fixture.js').read_text()
        for text in ['await storage.setAlarm(at)','await storage.deleteAlarm()','await this.ctx.storage.transaction(async tx=>','await storage.transaction(async inner=>','tx.rollback()','async alarm(info)']:
            self.assertIn(text,source)
    def test_characterization_is_nonpromoting(self):
        records=json.loads((HERE/'manifest.json').read_text());case=next(x for x in records if x['id']=='A019');self.assertFalse(case['promotion_gate']);self.assertIn('BLOCKED',case['preconditions'][-1])
    def test_failure_ceiling_does_not_arm_a_loop(self):
        source=(HERE/'fixture.js').read_text();self.assertIn("plan.mode==='always-throw'",source);self.assertIn("count(*) AS n FROM entries').one().n<16",source)
class OptionalAlarmObservationTests(unittest.TestCase):
    def test_only_absent_observation_is_optional(self):
        d=receipt_driver()
        def absent(*args):raise driver.ObservationTimeout('no event')
        d.wait=absent;self.assertIsNone(d.alarm_entry('r','label',optional=True))
    def test_optional_observation_does_not_swallow_assertion(self):
        d=receipt_driver()
        def invalid(*args):raise AssertionError('semantic mismatch')
        d.wait=invalid
        with self.assertRaisesRegex(AssertionError,'semantic mismatch'):d.alarm_entry('r','label',optional=True)
    def test_retry_mismatch_keeps_observed_trace_and_fails(self):
        d=receipt_driver();d.wait=lambda *args:({'root':'native-root'},{'is_retry':1})
        with self.assertRaisesRegex(AssertionError,'retry metadata'):d.alarm_entry('r','label',retry=0,optional=True)
        self.assertTrue(d.trace_entered);self.assertEqual(d.events[-1]['kind'],'native-alarm-entry')
if __name__=='__main__':unittest.main()
