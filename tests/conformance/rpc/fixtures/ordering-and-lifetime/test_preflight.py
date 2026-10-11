#!/usr/bin/env python3
"""Request adapter guard tests only; opener use is forbidden and no fixture is run."""
import importlib.util, json, pathlib, tempfile, unittest
from unittest.mock import patch
HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('order_request_adapter', HERE / 'run.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
class Preflight(unittest.TestCase):
    def blocked(self, args, guard=None):
        with tempfile.TemporaryDirectory() as directory:
            directory = pathlib.Path(directory); report = directory / 'report.json'; gp = directory / 'guard.json'
            argv = ['run.py', '--case', 'O001', '--report', str(report), *args]
            if guard is not None:
                gp.write_text(json.dumps(guard)); argv += ['--guard', str(gp)]
            with patch('sys.argv', argv), patch.object(runner.urllib.request, 'build_opener', side_effect=AssertionError('network forbidden')) as network, patch('builtins.print'):
                self.assertEqual(runner.main(), 1)
            result = json.loads(report.read_text()); self.assertEqual(result['status'], 'BLOCKED'); self.assertFalse(result['traceEntered']); network.assert_not_called()
            self.assertNotIn('dispatch_attempted', result)
            return result
    def test_missing_adapter(self): self.assertIn('guard required', self.blocked([])['error'])
    def test_public_literal_refused(self): self.assertIn('RFC1918', self.blocked(['--base-url', 'http://8.8.8.8:80'], {})['error'])
    def test_hostname_refused(self): self.assertIn('IPv4 or IPv6 address', self.blocked(['--base-url', 'http://example.com'], {})['error'])
    def test_credentials_refused(self): self.assertIn('credential-free', self.blocked(['--base-url', 'http://name:secret@127.0.0.1:8080'], {})['error'])
    def test_missing_ownership_guard(self): self.assertIn('exclusive_run_slot', self.blocked(['--base-url', 'http://127.0.0.1:8080'], {})['error'])
    def test_missing_evidence_ref(self):
        guard = {k: True for k in ('exclusive_run_slot', 'owned_disposable_fleet', 'pid_health_verified', 'limits_enforced', 'storage_teardown_owned')}
        self.assertIn('limits_evidence', self.blocked(['--base-url', 'http://127.0.0.1:8080'], guard)['error'])
class ReceiptContract(unittest.TestCase):
    # Only validates the evidence envelope; no RPC target or runtime is mocked.
    def receipt(self):
        return {'id': 'O001', 'requestId': 'current', 'profile': runner.PROFILE, 'origin': {'root': 'a', 'isolate': 'a'}, 'owner': {'root': 'b', 'isolate': 'b'}, 'status': 'PASS', 'phase': 'complete', 'traceEntered': True, 'evidence': {}, 'cleanup': {'status': 'ok'}}
    def validate(self, value): return runner.validate_terminal(value, 'current', 'O001', {'root': 'a', 'isolate': 'a'}, {'root': 'b', 'isolate': 'b'})
    def test_stale_receipt_refused(self):
        value = self.receipt(); value['requestId'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'correlation'): self.validate(value)
    def test_incomplete_pass_refused(self):
        value = self.receipt(); value['phase'] = 'trace'
        with self.assertRaisesRegex(ValueError, 'complete'): self.validate(value)
    def test_unclean_pass_refused(self):
        value = self.receipt(); value['cleanup']['status'] = 'FAIL'
        with self.assertRaisesRegex(ValueError, 'cleanup'): self.validate(value)
    def test_well_formed_receipt(self): self.validate(self.receipt())
if __name__ == '__main__': unittest.main()
