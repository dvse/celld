#!/usr/bin/env python3
"""Portable export of the bounded direct-State regression runner.
Packaging transformations are documented; this export has not been executed.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'celld'
COMPILER = Path(shutil.which(os.environ.get('RUSTC', 'rustc')) or os.environ.get('RUSTC', 'rustc')).resolve()
TOTAL_WALL = 270

class TotalDeadline(Exception):
    pass

class ExternalTermination(Exception):
    def __init__(self, signum):
        self.signum = signum
        super().__init__(f'runner received signal {signum}')

def protect_cleanup():
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGHUP, signal.SIG_IGN)

def terminated(signum, _frame):
    protect_cleanup()
    raise ExternalTermination(signum)

def expired(_signal, _frame):
    protect_cleanup()
    raise TotalDeadline('independent total wall deadline expired')

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

def limits(cpu):
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256 * 1024**2, 256 * 1024**2))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def child_setup(cpu, prior_mask):
    limits(cpu)
    for signum in (signal.SIGALRM, signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, signal.SIG_DFL)
    signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)

def verify(pins, expected_pins_hash):
    observed = {name: sha(SOURCE / name) for name in pins['source_files_sha256']}
    mismatches = {name: {'expected': pins['source_files_sha256'][name], 'actual': value}
        for name, value in observed.items() if value != pins['source_files_sha256'][name]}
    for name, expected in pins['test_files_sha256'].items():
        actual = sha(HERE / name)
        if actual != expected:
            mismatches['test/' + name] = {'expected': expected, 'actual': actual}
    manifest_hash = sha(HERE / 'source-pins.json')
    if manifest_hash != expected_pins_hash:
        mismatches['source-pins.json'] = {'expected': expected_pins_hash, 'actual': manifest_hash}
    return {'source_files_sha256': observed, 'mismatches': mismatches}

def exited_unreaped(child):
    return os.waitid(os.P_PID, child.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None

def group_present(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False

def cleanup(child):
    # Keep the leader unreaped while signaling, so its PGID cannot be reused.
    signalled = []
    if group_present(child.pid):
        try:
            os.killpg(child.pid, signal.SIGTERM); signalled.append('SIGTERM')
        except ProcessLookupError:
            pass
    end = time.monotonic() + 1
    while not exited_unreaped(child) and time.monotonic() < end:
        time.sleep(0.025)
    if group_present(child.pid):
        try:
            os.killpg(child.pid, signal.SIGKILL); signalled.append('SIGKILL')
        except ProcessLookupError:
            pass
    code = child.wait(timeout=5)
    # After reap, observe only; never signal a potentially reused number.
    return {'returncode': code, 'child_reaped': True, 'signals': signalled,
            'remaining_owned_group_observed': group_present(child.pid)}

def phase(name, command, out, env, seconds, cpu):
    if seconds <= 0:
        return {'name': name, 'timed_out': True, 'started': False}
    started = time.monotonic()
    row = {'name': name, 'command': [str(x) for x in command], 'started_utc': utc(),
           'budget_seconds': seconds, 'rlimit_as_bytes': 1024**3, 'rlimit_cpu_seconds': cpu}
    logfile = out / (name + '.log')
    with logfile.open('x') as log:
        # Defer handled signals across spawn until child ownership and the cleanup
        # finally are installed. Child setup restores its inherited signal mask.
        prior_mask = signal.pthread_sigmask(signal.SIG_BLOCK,
            {signal.SIGALRM, signal.SIGTERM, signal.SIGHUP})
        child = None
        try:
            child = subprocess.Popen(command, cwd=out, env=env, stdout=log,
                stderr=subprocess.STDOUT, start_new_session=True,
                preexec_fn=lambda: child_setup(cpu, prior_mask))
            row['pid'] = child.pid
            signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
            while not exited_unreaped(child) and time.monotonic() < started + seconds:
                time.sleep(0.025)
            row['timed_out'] = not exited_unreaped(child)
        finally:
            # The total timer stays armed. Pending signals are delivered only
            # after owned-child cleanup and its receipt have completed.
            signal.pthread_sigmask(signal.SIG_BLOCK,
                {signal.SIGALRM, signal.SIGTERM, signal.SIGHUP})
            try:
                if child is not None:
                    row.update(cleanup(child))
                row.update(elapsed_seconds=time.monotonic() - started,
                           log_path=str(logfile), log_sha256=sha(logfile))
                (out / (name + '-receipt.json')).write_text(json.dumps(row, indent=2) + '\n')
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, prior_mask)
    return row

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-label', required=True)
    parser.add_argument('--expected-pins-sha256', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', args.run_label):
        parser.error('run-label must use 1–80 letters, digits, underscore or hyphen')
    if not re.fullmatch(r'[0-9a-f]{64}', args.expected_pins_sha256):
        parser.error('expected-pins-sha256 must be the independently reviewed manifest SHA256')
    pins_path = HERE / 'source-pins.json'
    pins = json.loads(pins_path.read_text())
    out = HERE / 'runs' / args.run_label
    out.mkdir(parents=True, exist_ok=False)
    report = {'status': 'STARTED', 'started_utc': utc(),
        'exclusivity_limit': 'Run only in a user-provisioned isolated resource envelope; no global process claim is inferred.',
        'export_runner_qualification': 'NOT_PREVIOUSLY_EXECUTED',
        'source_root': str(SOURCE), 'pins_path': str(pins_path), 'pins_sha256': sha(pins_path),
        'expected_pins_sha256': args.expected_pins_sha256,
        'production_modified': False, 'sut_executed': False, 'network_used': False,
        'scope': 'Actual production State only; no application output tests.',
        'profile': {'rlimit_as_bytes': 1024**3, 'build_cpu_per_process_seconds': 60,
                    'build_wall_total_seconds': 90, 'jobs': 1, 'linker_threads': 1,
                    'test_cpu_seconds': 10, 'test_wall_seconds': 10, 'test_threads': 1,
                    'independent_total_wall_seconds': TOTAL_WALL}, 'phases': []}
    env = dict(os.environ)
    env['PATH'] = str(COMPILER.parent) + os.pathsep + env.get('PATH', '')
    status_code = 3
    signal.signal(signal.SIGALRM, expired)
    signal.signal(signal.SIGTERM, terminated)
    signal.signal(signal.SIGHUP, terminated)
    signal.setitimer(signal.ITIMER_REAL, TOTAL_WALL)
    try:
        report['before'] = verify(pins, args.expected_pins_sha256)
        if report['before']['mismatches']:
            report['status'] = 'BLOCKED_PIN_MISMATCH'
        else:
            lib = out / 'libcelld_logic.rlib'
            test = out / 'lease_continuity_tests'
            suite = out / 'lease_continuity_suite.rs'
            suite.write_bytes((HERE / 'lease_continuity.rs').read_bytes() + b'\n'
                + (HERE / 'guard_predicate.rs').read_bytes())
            report['compiled_test_source_path'] = str(suite)
            report['compiled_test_source_sha256'] = sha(suite)
            build_deadline = time.monotonic() + 90
            commands = [
                ('compile_core', [str(COMPILER), '--crate-name', 'celld_logic', '--crate-type', 'rlib',
                    '--edition=2021', '-C', 'debuginfo=0', '-C', 'codegen-units=1',
                    str(SOURCE / 'crates/logic/lib.rs'), '-o', str(lib)]),
                ('compile_tests', [str(COMPILER), '--test', '--edition=2021', '-C', 'debuginfo=0',
                    '-C', 'codegen-units=1', '-C', 'link-arg=-Wl,--threads=1',
                    str(suite), '--extern', 'celld_logic=' + str(lib),
                    '-o', str(test)]),
            ]
            for name, command in commands:
                row = phase(name, command, out, env, build_deadline - time.monotonic(), 60)
                report['phases'].append(row)
                if row['timed_out']:
                    report['status'] = 'BLOCKED_BUILD_TIMEOUT'; break
                if row.get('remaining_owned_group_observed'):
                    report['status'] = 'BLOCKED_OWNED_CLEANUP'; break
                if row['returncode'] != 0:
                    report['status'] = 'BLOCKED_COMPILE_ERROR'; break
            else:
                report['compiled_artifacts_sha256'] = {'library': sha(lib), 'test': sha(test)}
                failed = []
                for index, name in enumerate(pins['test_functions']):
                    row = phase(f'test_{index:02d}', [str(test), name, '--exact', '--test-threads=1',
                        '--nocapture'], out, env, 10, 10)
                    row['test_function'] = name
                    report['phases'].append(row)
                    if row['timed_out']:
                        report['status'] = 'BLOCKED_TEST_TIMEOUT'; break
                    if row.get('remaining_owned_group_observed'):
                        report['status'] = 'BLOCKED_OWNED_CLEANUP'; break
                    log = Path(row['log_path']).read_text()
                    expected = 'running 1 test' in log and (f'test {name} ...' in log)
                    if not expected:
                        report['status'] = 'BLOCKED_MISSING_EXACT_TEST_RECEIPT'; break
                    if row['returncode'] != 0:
                        if (row['returncode'] == 101 and 'test result: FAILED.' in log
                                and name in log and 'panicked at' in log):
                            failed.append(name)
                        else:
                            report['status'] = 'BLOCKED_TEST_PROCESS_FAILURE'; break
                    elif 'test result: ok. 1 passed;' not in log:
                        report['status'] = 'BLOCKED_MISSING_TEST_SUCCESS'; break
                else:
                    report['failed_test_functions'] = failed
                    report['status'] = 'TEST_ASSERTIONS_FAILED' if failed else 'ALL_ASSERTIONS_PASSED'
                    status_code = 1 if failed else 0
    except ExternalTermination as error:
        report['status'] = 'BLOCKED_RUNNER_TERMINATED'; report['error'] = str(error)
        status_code = 128 + error.signum
    except TotalDeadline as error:
        report['status'] = 'BLOCKED_TOTAL_DEADLINE'; report['error'] = str(error)
    except Exception as error:
        report['status'] = 'BLOCKED_RUNNER_ERROR'
        report['error'] = {'type': type(error).__name__, 'detail': str(error)}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            report['after'] = verify(pins, args.expected_pins_sha256)
            if report['after']['mismatches']:
                report['status_before_pin_check'] = report['status']
                report['status'] = 'INVALID_SOURCE_CHANGED'; status_code = 3
        except Exception as error:
            report['status'] = 'INVALID_FINAL_PIN_CHECK'
            report['final_pin_error'] = str(error); status_code = 3
        report['finished_utc'] = utc()
        (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'report': str(out / 'report.json')}))
    return status_code

if __name__ == '__main__':
    raise SystemExit(main())
