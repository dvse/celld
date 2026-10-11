"""Pure guard/schema checks. These are not runtime cases and add no authored count."""
import ast, copy, importlib.util, json, pathlib, signal, unittest
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('upg_driver_static',HERE/'driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
def guard():
    hashes=driver.pins()
    return {'exclusive_run_slot':True,'owned_disposable_fleet':True,'transfer_cleanup_ownership':True,'binary_sha256':driver.BINARY,'implementation_hashes':hashes,'reviewed_implementation_hashes':hashes,'reviewed_case_ids':['U001'],'profile':'bucket','run_id':'0123456789abcdef','profile_sha256':driver.digest(HERE/'bucket-profile.json'),'qemu_limits_verified':True,'guest_cgroup_limits_verified':True,'review_evidence':'test-only-no-admission','limits_evidence':'test-only-no-admission','deployment_evidence':'test-only-no-admission'}
class GuardTests(unittest.TestCase):
    def test_guard_schema_only_accepts_complete_values(self):driver.validate_guard(guard(),'U001')
    def test_empty_guard_blocks(self):
        with self.assertRaises(driver.Blocked):driver.validate_guard({},'U001')
    def test_stale_source_blocks(self):
        g=guard();g['implementation_hashes']={}
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_stale_review_blocks(self):
        g=guard();g['reviewed_implementation_hashes']={}
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_unreviewed_case_blocks(self):
        with self.assertRaises(driver.Blocked):driver.validate_guard(guard(),'U002')
    def test_fleet_blocks(self):
        g=guard();g['profile']='fleet'
        with self.assertRaisesRegex(driver.Blocked,'bucket-only'):driver.validate_guard(g,'U001')
    def test_unowned_cleanup_blocks(self):
        g=guard();g['transfer_cleanup_ownership']=False
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_unbounded_guest_blocks(self):
        g=guard();g['guest_cgroup_limits_verified']=False
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_wrong_binary_blocks(self):
        g=guard();g['binary_sha256']='wrong'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_nonfresh_id_shape_blocks(self):
        g=guard();g['run_id']='../unowned'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_stale_profile_blocks(self):
        g=guard();g['profile_sha256']='wrong'
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
    def test_missing_evidence_blocks(self):
        g=guard();g['review_evidence']=''
        with self.assertRaises(driver.Blocked):driver.validate_guard(g,'U001')
class ControlPathTests(unittest.TestCase):
    """Negative runner control-path regression tests; no SUT or real process fixture."""
    def test_trace_entry_is_receiver_witnessed(self):
        tree=ast.parse((HERE/'driver.py').read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Driver')
        methods={x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}
        batch=ast.get_source_segment((HERE/'driver.py').read_text(),methods['batch'])
        waiting=ast.get_source_segment((HERE/'driver.py').read_text(),methods['waiting'])
        self.assertNotIn('self.trace_entered=True',batch)
        self.assertNotIn('self.trace_entered=True',waiting)
        root=ast.get_source_segment((HERE/'driver.py').read_text(),methods['root']);finish=ast.get_source_segment((HERE/'driver.py').read_text(),methods['finish_deploy'])
        self.assertNotIn('self.trace_entered=True',root);self.assertIn('self.setup_entered=True',root)
        self.assertLess(finish.index('native-deploy-terminal-receipt'),finish.index('operator_error'));self.assertLess(finish.index('operator_error'),finish.index('self.trace_entered=True'));self.assertLess(finish.index('self.trace_entered=True'),finish.index('self.verify_publication'))
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
            result=driver.run_case([],{},'U001')
        self.assertEqual(cleaned,[True]);self.assertEqual(result['status'],'BLOCKED');self.assertFalse(result['traceEntered'])
    def test_sigterm_enters_cleanup_and_restores_handler(self):
        previous=signal.getsignal(signal.SIGTERM);cleaned=[]
        def interrupted(instance,*args):
            instance.cleanup_authorized=True
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        def cleanup(instance,force=False):
            cleaned.append(True);return {'status':'ok','scope':'unit-test-no-guests'}
        with patch.object(driver.Driver,'__init__',interrupted),patch.object(driver.Driver,'cleanup',cleanup):
            result=driver.run_case([],{},'U001')
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
            result=driver.run_case([],{},'U001')
        self.assertEqual(calls,[False,True]);self.assertEqual(result['status'],'BLOCKED');self.assertEqual(result['cleanup']['status'],'FAILED')
class DeploymentPureTests(unittest.TestCase):
    def test_generated_guest_programs_parse_without_executing(self):
        d=driver.Driver.__new__(driver.Driver);d.roots={'r':{'name':'same-public-name','node':1,'namespace':'sibling'}};d.deadline=__import__('time').monotonic()+360;d.control_calls=0;d.events=[]
        captured=[]
        def py(node,source,timeout=25):
            compile(ast.parse(source),'<guest-source>','exec');captured.append(source);return {'status':200,'body':{}}
        d.py=py
        d.response('r','snapshot');self.assertIn('same-public-name',captured[-1]);self.assertIn('sibling',captured[-1])
    def test_fixture_overlap_deadline_is_blocked_with_original_receipts(self):
        d=driver.Driver.__new__(driver.Driver);seen=[];d.event=lambda *args,**kwargs:seen.append(kwargs)
        records=[{'status':500,'body':'Error: external gate deadline'}]
        with self.assertRaises(driver.Blocked):d.check_fixture_deadlines(records)
        self.assertEqual(seen[0]['original_receipts'],records)
    def test_forced_reload_source_contract(self):
        path=driver.PROJECT/'deliverable/patch-check-final/crates/celld/main.rs';source=path.read_text()
        function=source[source.index('async fn internal_reload('):];self.assertIn('force: true',function[:1000])
        adoption=source[source.index('async fn adopt_deployment('):source.index('fn start_pointer_watcher(')]
        self.assertIn('if !force && pointer.version == current.version()',adoption)
    def test_external_gate_bounds_are_explicit(self):
        source=(HERE/'fixture-body.js').read_text();self.assertIn('attempt<45',source);self.assertIn('size>2097152',source);self.assertIn('controller.abort()',source);self.assertIn('read<256',source);self.assertIn("redirect:'error'",source);self.assertIn('Math.max(0,deadline-Date.now())',source)
        case_source=(HERE/'cases.py').read_text();tree=ast.parse(case_source);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='U024');body=ast.get_source_segment(case_source,node)
        self.assertIn('signal_external',body);self.assertNotIn('close_old(',body)
    def test_native_operator_owns_child_before_evidence_steps(self):
        source=(HERE/'deploy_job.py').read_text();tree=ast.parse(source);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
        guard=next(n for n in fn.body if isinstance(n,ast.Try));self.assertTrue(guard.finalbody)
        body=ast.get_source_segment(source,guard);self.assertIn("atomic_json(directory/'child.json'",body);self.assertIn('terminate_owned_child',body)
    def test_no_unsupported_migration_success_is_implemented(self):
        cfg=json.loads((HERE/'versions/bad-rename/wrangler.jsonc').read_text());self.assertIn('renamed_classes',cfg['migrations'][1])
        source=(HERE/'cases.py').read_text();tree=ast.parse(source);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='U013');text=ast.get_source_segment(source,node)
        self.assertIn('success=False',text);self.assertIn('d.pointers()==before',text)
    def test_case_oracle_rejects_wrong_values_and_phantom_rows(self):
        spec=importlib.util.spec_from_file_location('upg_oracle_pure',HERE/'cases.py');cases=importlib.util.module_from_spec(spec);spec.loader.exec_module(cases)
        correct={'columns':['k','value','label'],'items':[{'k':'a','value':7,'label':'alpha'},{'k':'b','value':11,'label':'beta'}],'ops':[],'meta':[{'k':'migrations','v':0},{'k':'schema','v':1}],'indexes':[],'plans':[],'alarms':[]}
        cases.expect(correct)
        wrong=copy.deepcopy(correct);wrong['items'][0]['value']=8
        with self.assertRaises(AssertionError):cases.expect(wrong)
        wrong=copy.deepcopy(correct);wrong['ops'].append({'id':'phantom','k':'a','delta':0,'writer':'v1'})
        with self.assertRaises(AssertionError):cases.expect(wrong)
    def test_fixture_alias_materialization_is_exact(self):
        body=(HERE/'fixture-body.js').read_text()
        for version in ('v1','v2-add','v2-rebuild','v2-unique','v2-abort','v2-code','v2-sibling','v2-binding','v2-omitted','v2-script'):
            self.assertTrue((HERE/'versions'/version/'fixture.js').read_text().endswith(body))
            self.assertIs(json.loads((HERE/'versions'/version/'wrangler.jsonc').read_text())['no_bundle'],True)
if __name__=='__main__':unittest.main()
