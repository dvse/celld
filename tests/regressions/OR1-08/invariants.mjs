// OR1-08: structural invariants of call admission (change 1) and reusable
// props snapshots (change 2). Source-level, because ported's per-path repairs
// (fix-9) already made every path behave correctly: no runtime observation
// distinguishes one admission from N equivalent per-path captures. This test
// fails on ported (593181b) and passes on ported-2.
import assert from 'node:assert/strict';
import {source} from '../harness_unit.mjs';
const failures = [];
const check = (ok, what) => { if (!ok) failures.push(what); };
check(!source.includes('__admitRpcArgs'), 'no per-path __admitRpcArgs');
check(!source.includes('preparedArgs'), 'no preparedArgs side channel');
check(/const __invokeAdmitted = \(session, path, args\)/.test(source), 'one admission entry');
// Every session dispatcher receives an admission, never raw arguments.
const sessionCalls = [...source.matchAll(/\bcall: \(path, (\w+)/g)].map(m => m[1]);
check(sessionCalls.length >= 6, 'session dispatchers found: ' + sessionCalls.length);
check(sessionCalls.every(name => name === 'admission'), 'dispatchers take admissions: ' + sessionCalls.join(','));
check(!/async call\(path, args\)/.test(source), 'no raw-args async dispatcher');
// Traps admit through the single entry.
check(!/session\.call\(path, args\)/.test(source), 'traps do not pass raw args');
check(/__valueSession\(__invokeAdmitted\(__stubSession\(meta\), \[\], args\)\)/.test(source), 'callable stub trap admits');
// Change 2: the persistent service root's props are a reusable snapshot.
check(/root\.props === undefined \? new Uint8Array\(\) : __capturePropsBytes\(root\.props\)/.test(source), 'restore-root props snapshot');
console.log(JSON.stringify({id: 'OR1-08', sessionCalls: sessionCalls.length, failures}));
assert.deepEqual(failures, []);
