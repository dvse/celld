#!/usr/bin/env python3
"""Harness regression only: exact SafeGuest wrapper, persistent ordinary sh.
No guest/runtime launched and no celld conformance case counted.
"""
import ast,re,shlex,subprocess,types,unittest,uuid
from pathlib import Path
class PersistentShell:
    def __init__(self):
        self.p=subprocess.Popen(['/bin/sh'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    def cmd(self,command,timeout=180):
        marker='END_'+uuid.uuid4().hex
        self.p.stdin.write(command+'; printf "\\n'+marker+'\\n"\n');self.p.stdin.flush()
        lines=[]
        for line in self.p.stdout:
            if line.strip()==marker:return ''.join(lines)
            lines.append(line)
        raise RuntimeError('persistent control shell exited: '+''.join(lines))
    def close(self):
        self.p.stdin.close()
        try:self.p.wait(timeout=3)
        except subprocess.TimeoutExpired:self.p.kill();self.p.wait(timeout=3)
        self.p.stdout.close()

def wrapper():
    source=Path(__file__).with_name('vm_pilot_v2.py').read_text();tree=ast.parse(source)
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.ClassDef) and n.name=='SafeGuest')
    ns={'module':types.SimpleNamespace(Guest=PersistentShell),'uuid':uuid,'shlex':shlex,'re':re}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'production-wrapper','exec'),ns)
    return ns['SafeGuest']

class CommandIsolation(unittest.TestCase):
    def setUp(self):self.g=wrapper()();self.pid=self.g.p.pid
    def tearDown(self):self.g.close()
    def test_nonzero_keeps_control_shell_alive(self):
        with self.assertRaisesRegex(RuntimeError,'guest command exited 17'):
            self.g.cmd("set -e; printf 'diagnostic-before-fail\\n'; exit 17")
        self.assertIsNone(self.g.p.poll());self.assertEqual(self.g.p.pid,self.pid)
        self.assertIn('still-alive',self.g.cmd("printf 'still-alive\\n'"))
    def test_errexit_does_not_persist_after_success(self):
        self.g.cmd('set -e; true')
        self.assertIn('after-false',self.g.cmd("false; printf 'after-false\\n'"))
    def test_failure_output_is_preserved(self):
        with self.assertRaisesRegex(RuntimeError,'actual-startup-error'):
            self.g.cmd("printf 'actual-startup-error\\n' >&2; exit 4")
        self.assertIn('ready',self.g.cmd("printf 'ready\\n'"))
    def test_quotes_and_newlines_stay_in_subshell(self):
        self.assertIn("quoted ' value",self.g.cmd('printf "%s\\n" "quoted \' value"\ntrue'))
        self.assertIsNone(self.g.p.poll())
if __name__=='__main__':unittest.main()
