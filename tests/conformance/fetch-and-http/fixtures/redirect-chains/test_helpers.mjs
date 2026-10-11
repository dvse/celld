// Inert helper regression checks. No fixture, native runtime, socket, or test case is run.
import assert from 'node:assert/strict';
import test from 'node:test';
import {Lab,NativeFailure} from './lab.js';
import {configuredLocation} from './common.js';
const make=()=>new Lab({recipient:'recipient',run:'run'}, {root:'caller',isolate:'caller-isolate'},'http://192.168.77.1:18080');
const reason=()=>new Error('F009 planned intermediate abort');
test('abort oracle refuses an ordinary assertion failure',async()=>{const t=make(),r=reason();await assert.rejects(t.aborted(t.watch(Promise.reject(new Error('oracle failed'))),r),/requires native fetch/);});
test('abort oracle refuses a different Error with identical text',async()=>{const t=make(),r=reason();await assert.rejects(t.aborted(t.watch(Promise.reject(new NativeFailure(reason(),'fetch'))),r),/exact intentional abort/);});
test('abort oracle refuses reader errors in place of fetch rejection',async()=>{const t=make(),r=reason();await assert.rejects(t.aborted(t.watch(Promise.reject(new NativeFailure(r,'reader.read'))),r),/requires native fetch/);});
test('abort oracle accepts only exact intended fetch reason',async()=>{const t=make(),r=reason();await t.aborted(t.watch(Promise.reject(new NativeFailure(r,'fetch'))),r);assert.equal(t.events[0].kind,'expected-error');});
test('recipient identity mismatch is an assertion failure',async()=>{const t=make();t.owner={root:'recipient-root',isolate:'recipient-isolate'};t.expected.set('start',{query:''});t.net=async()=>({headers:new Headers({'x-fetch-op':'wrong'})});await assert.rejects(t.open('start','final'),/endpoint\/run/);});
test('cancel failure retains reader ownership for cleanup',async()=>{const t=make(),reader={cancel:async()=>{throw new Error('cancel rejected');}},r={};t.readers.set(reader,r);await assert.rejects(t.cancelHeld({reader,r}),/cancel rejected/);assert.equal(t.readers.size,1);});
test('unobserved assertion in joined task blocks cleanup',async()=>{const t=make();t.owner={root:'recipient',isolate:'isolate'};t.control=async()=>({status:'ok',run:'run',root:'recipient',isolate:'isolate',active:0,readers:0,controllers:0,pulls:0});t.watch(Promise.reject(new Error('task assertion')));await assert.rejects(t.cleanup(),/unobserved task failure/);});
test('nonzero remote pulls blocks cleanup even after local settlement',async()=>{const t=make();t.owner={root:'recipient',isolate:'isolate'};t.control=async()=>({status:'ok',run:'run',root:'recipient',isolate:'isolate',active:0,readers:0,controllers:0,pulls:1});await assert.rejects(t.cleanup(),/matched remote drain/);});
test('F002 current-base route passes and original-base mutant is refused',()=>{
  const origin='http://192.168.77.1:18080',prefix=origin+'/root/recipient/op/';
  const original=prefix+'origin/start?phase=start';
  const middle={name:'middle',query:'?phase=middle'},final={name:'final',query:'?phase=done'};
  const routes=new Map([['branch/middle',middle],['branch/final',final]]);
  const first=configuredLocation('../branch/middle?phase=middle',original,origin,'recipient',routes);
  assert.equal(first.url,prefix+'branch/middle?phase=middle');
  const correct=configuredLocation('final?phase=done',first.url,origin,'recipient',routes);
  assert.equal(correct.url,prefix+'branch/final?phase=done');assert.equal(correct.target,final);
  assert.equal(new URL('final?phase=done',original).href,prefix+'origin/final?phase=done');
  assert.throws(()=>configuredLocation('final?phase=done',original,origin,'recipient',routes),/earlier configured endpoint/);
});
