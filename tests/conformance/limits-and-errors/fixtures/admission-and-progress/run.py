#!/usr/bin/env python3
"""One-case request-only adapter. Never deploys or launches runtimes or guests."""
import argparse, datetime, hashlib, ipaddress, json, pathlib, signal, time, urllib.error, urllib.parse, urllib.request, uuid
HERE = pathlib.Path(__file__).resolve().parent
BINARY = '62695e9e0eaec3e2a4c62279144ef42b47d60a571343356509a758f3f895853e'
FILES = ('fixture.js', 'cases.js', 'entry.js', 'workers.js', 'manifest.json', 'source-pins.json', 'wrangler.jsonc', 'run.py')
PROFILE = 'bounded-load-native-2026-09-04'
EXECUTION_BLOCKED_IDS = {f'B{i:03d}' for i in range(17, 25)}
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): raise ValueError('redirect prohibited')
def validate_terminal(value, request_id, case_id, origin, owner):
    if value.get('requestId') != request_id: raise ValueError('terminal receipt dispatch correlation mismatch')
    if value.get('id') != case_id or value.get('profile') != PROFILE or value.get('origin') != origin or value.get('owner') != owner: raise ValueError('terminal receipt identity or profile mismatch')
    if value.get('status') not in ('PASS', 'FAIL', 'BLOCKED'): raise ValueError('invalid terminal fixture status')
    if value['status'] == 'PASS' and (value.get('traceEntered') is not True or value.get('phase') != 'complete' or 'evidence' not in value or value.get('cleanup', {}).get('status') != 'ok'): raise ValueError('PASS lacks complete assertion receipt or checked cleanup')
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base-url'); p.add_argument('--guard', type=pathlib.Path)
    p.add_argument('--case', required=True); p.add_argument('--report', type=pathlib.Path, required=True)
    a = p.parse_args(); report = {'id': a.case, 'status': 'BLOCKED', 'traceEntered': False, 'started_utc': now(), 'adapter': 'bounded-load-request-only-v1'}
    alarm_installed = False
    try:
        rows = json.loads((HERE / 'manifest.json').read_text())
        if a.case not in {row['id'] for row in rows}: raise ValueError('unknown case ID')
        if a.case in EXECUTION_BLOCKED_IDS: raise ValueError('Loader case execution BLOCKED pending explicit owner overlap/authorization review; this adapter cannot launch restricted stateless-capability lifetime work')
        if not a.base_url or not a.guard: raise ValueError('reviewed supervisor endpoint and guard required; no network request made')
        u = urllib.parse.urlsplit(a.base_url)
        if u.scheme != 'http' or u.username or u.password or u.query or u.fragment or u.path not in ('', '/'):
            raise ValueError('base URL must be a credential-free private HTTP origin')
        ip = ipaddress.ip_address(u.hostname)
        private = ip.is_loopback or any(ip.version == n.version and ip in n for n in map(ipaddress.ip_network, ['10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16']))
        if not private: raise ValueError('only loopback and RFC1918 IP literals are allowed')
        guard = json.loads(a.guard.read_text())
        for flag in ('exclusive_run_slot', 'owned_disposable_fleet', 'pid_health_verified', 'limits_enforced', 'storage_teardown_owned'):
            if guard.get(flag) is not True: raise ValueError('missing supervisor guard: ' + flag)
        for witness in ('limits_evidence', 'owner_evidence', 'readiness_evidence', 'review_evidence'):
            if not isinstance(guard.get(witness), str) or not guard[witness]: raise ValueError('missing evidence reference: ' + witness)
        if guard.get('base_url', '').rstrip('/') != a.base_url.rstrip('/'): raise ValueError('guard endpoint mismatch')
        if guard.get('binary_sha256') != BINARY: raise ValueError('frozen binary mismatch')
        hashes = {name: sha(HERE / name) for name in FILES}
        if guard.get('implementation_hashes') != hashes: raise ValueError('guard does not match exact staged source, cases and profile')
        if a.case not in guard.get('reviewed_case_ids', []): raise ValueError('case lacks independent accepted review')
        if guard.get('reviewed_implementation_hashes') != hashes: raise ValueError('independent review does not match staged implementation')
        limits = guard.get('limits', {})
        def bounded_number(key, low, high):
            value = limits.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high: raise ValueError('missing or excessive enforced bound: ' + key)
        bounded_number('case_wall_seconds', 1, 30)
        bounded_number('memory_mib_per_guest', 1, 1024)
        bounded_number('pids_per_guest', 1, 128)
        bounded_number('vcpus_per_guest', 1, 2)
        if limits.get('logical_payload_bytes_max') != 2097152 or limits.get('loaded_workers_max') != 4 or limits.get('fixture_active_jobs_max') != 16: raise ValueError('fixture resource bound mismatch')
        if guard.get('profile_sha256') != hashes['wrangler.jsonc']: raise ValueError('profile mismatch')
        timeout = guard.get('request_timeout_seconds', 0)
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 30: raise ValueError('request timeout must be 1..30 seconds')
        endpoints = guard.get('roots', {})
        for role in ('origin', 'owner'):
            item = endpoints.get(role, {})
            if not isinstance(item.get('name'), str) or not item['name']: raise ValueError('missing root name')
            if not isinstance(item.get('runtime_pid'), int) or item['runtime_pid'] <= 0: raise ValueError('missing verified runtime PID')
            if not isinstance(item.get('vm_id'), str) or not item['vm_id']: raise ValueError('missing process/VM owner identity')
        first, second = endpoints['origin'], endpoints['owner']
        if first['name'] == second['name'] or (first['vm_id'], first['runtime_pid']) == (second['vm_id'], second['runtime_pid']): raise ValueError('real-process-RPC requires distinct verified runtime owners')
        deadline = time.monotonic() + limits['case_wall_seconds']
        def expired(_signum, _frame): raise TimeoutError('absolute supervised case deadline reached; owned fleet teardown required')
        if not hasattr(signal, 'setitimer'): raise ValueError('absolute wall timer unavailable')
        signal.signal(signal.SIGALRM, expired); signal.setitimer(signal.ITIMER_REAL, limits['case_wall_seconds']); alarm_installed = True
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        def request(path, body=None):
            r = urllib.request.Request(a.base_url.rstrip('/') + path, data=None if body is None else json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
            try: response = opener.open(r, timeout=max(0.001, min(timeout, deadline-time.monotonic())))
            except urllib.error.HTTPError as error: response = error
            with response:
                data = response.read(1048577)
                if len(data) > 1048576: raise ValueError('response exceeds evidence bound')
                return json.loads(data)
        health = request('/health')
        if health.get('profile') != PROFILE or health.get('rpcParamsDupStubs') is not True or a.case not in health.get('caseIds', []): raise ValueError('deployed fixture/modern-profile precondition mismatch')
        origin, owner = request('/identity', {'root': first['name']}), request('/identity', {'root': second['name']})
        if not all(isinstance(x.get(k), str) and x[k] for x in (origin, owner) for k in ('root', 'isolate')): raise ValueError('identity witness missing')
        if origin['root'] == owner['root'] or origin['isolate'] == owner['isolate']: raise ValueError('fixture recipients not distinct')
        request_id = str(uuid.uuid4())
        report.update(dispatch_attempted=True, requestId=request_id, qualification='PENDING_EXTERNAL_SUPERVISOR_TEARDOWN_REVIEW', guard_sha256=sha(a.guard), binary_sha256=BINARY, implementation_hashes=hashes, layer='real-process-RPC', owner_witness=endpoints, enforced_limits=limits)
        value = request('/run', {'id': a.case, 'root': first['name'], 'peer': second['name'], 'requestId': request_id})
        validate_terminal(value, request_id, a.case, origin, owner)
        report.update(status=value['status'], traceEntered=value.get('traceEntered') is True, result=value)
    except Exception as error:
        report['error'] = str(error)
        if report.get('dispatch_attempted'):
            report['traceEntryUnknown'] = True
            report['cleanup'] = {'status': 'UNKNOWN', 'required': 'Supervisor must tear down owned fleet; do not automatically retry an uncertain dispatch.'}
    finally:
        if alarm_installed: signal.setitimer(signal.ITIMER_REAL, 0)
        report['finished_utc'] = now()
        a.report.parent.mkdir(parents=True, exist_ok=True); a.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'id': a.case, 'status': report['status'], 'traceEntered': report['traceEntered'], 'report': str(a.report)}))
    return 0 if report['status'] == 'PASS' else 1
if __name__ == '__main__': raise SystemExit(main())
