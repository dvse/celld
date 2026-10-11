import {bytes,vectors} from './vectors.js';
import {eq,ok,same,hex,rejection,typeError,decompressionError,unsupported,observed} from './common.js';

// Every body owns its actual schedule and assertions. hold() is a cross-request
// rendezvous in the active coordinator invocation; no SQL/input/output gate is used.
export const operations={
 async X001(c){
  const t=c.open('gzip');const data=bytes('archive');await t.writer.write(data.subarray(0,211));
  await c.hold('prefix-encoder');await t.writer.write(data.subarray(211));await t.writer.close();
  const encoded=await t.output;await c.roundtrip(encoded,'gzip',data);return {compressedBytes:encoded.length};
 },
 async X002(c){
  const t=c.open('gzip',true),wire=bytes('gzip');await t.writer.write(wire.subarray(0,wire.length-8));
  await c.hold('trailer-pending');await t.writer.write(wire.subarray(wire.length-8));await t.writer.close();
  same(await t.output,bytes('archive'),'delayed valid trailer restores complete archive');return {trailerBytes:8};
 },
 async X003(c){
  const t=c.open('gzip',true,false),wire=bytes('gzip');await t.writer.write(wire.subarray(0,wire.length-8));
  const prefix=await t.reader.read();ok(!prefix.done&&prefix.value.length>0,'decoder produced a prefix');
  same(prefix.value,bytes('archive').subarray(0,prefix.value.length),'decoded prefix is owned archive');
  await c.hold('decoded-prefix-retained');const reason=new Error('planned:X003-consumer-cancel');await t.reader.cancel(reason);
  await rejection(t.writer.write(wire.subarray(wire.length-8)),e=>e===reason,'cancel prevents later native write');
  return {prefixBytes:prefix.value.length,consumerCancelled:true};
 },
 async X004(c){
  const t=c.open('gzip',false,false);const pending=t.reader.read();await t.writer.write(bytes('pack').subarray(0,64));
  await c.hold('pending-native-read');const reason=new Error('planned:X004-cancel');await t.reader.cancel(reason);
  await rejection(pending,e=>e===reason,'native pending read rejects exact cancellation reason');
  await rejection(t.writer.close(),e=>e===reason,'cancelled encoder cannot flush');return {pendingReadRejected:true};
 },
 async X005(c){
  const t=c.open('deflate-raw');await t.writer.write(bytes('sheet').subarray(0,257));
  await c.hold('unflushed-raw-state');const reason=new Error('planned:X005-abort');await t.writer.abort(reason);
  await rejection(t.output,e=>e===reason,'writable abort reaches output reader');
  await c.encodeChecked('deflate-raw',bytes('sheet'));return {freshEncoderRecovered:true};
 },
 async X006(c){
  const t=c.open('gzip');let pulled=0;const reason=new Error('planned:X006-source-zero');
  const source=new ReadableStream({pull(controller){pulled++;controller.error(reason);}});const destination=c.sink(t);
  await c.hold('encoder-before-source');const pipe=c.pipe(source,destination);
  await rejection(pipe,e=>e===reason,'zero-prefix source failure propagates to pipe');
  await rejection(t.output,e=>e===reason,'zero-prefix source failure aborts native transform');eq(pulled,1,'one finite failed pull');
  return {sourceError:'planned:X006-source-zero',pulled};
 },
 async X007(c){
  const t=c.open('gzip',true),wire=bytes('gzip'),reason=new Error('planned:X007-source-prefix');let controller;
  const source=new ReadableStream({start(v){controller=v;}},{highWaterMark:0});c.ownStopper('decoder-source',reason=>controller.error(reason));const pipe=c.pipe(source,c.sink(t));
  c.charge(wire.length-8);controller.enqueue(wire.subarray(0,wire.length-8));await c.until(()=>t.observedOutputBytes>0,'decoder received prefix');
  await c.hold('source-tail-error');controller.error(reason);
  await rejection(pipe,e=>e===reason,'prefix source error reaches pipe');await rejection(t.output,e=>e===reason,'prefix error prevents successful decoder EOF');
  return {sourceError:'planned:X007-source-prefix',observedDecodedPrefix:t.observedOutputBytes};
 },
 async X008(c){
  const t=c.open('gzip',true),wire=bytes('gzip');wire[wire.length-8]^=1;
  await t.writer.write(wire.subarray(0,wire.length-8));await c.hold('crc-awaiting-validation');
  const result=c.track((async()=>{await t.writer.write(wire.subarray(wire.length-8));await t.writer.close();})());
  await rejection(result,decompressionError,'bad fixture CRC rejected at write or finish');
  await rejection(t.output,decompressionError,'bad CRC cannot become successful EOF');return {corruption:'one public CRC bit'};
 },
 async X009(c){
  const t=c.open('gzip',true),wire=bytes('gzip');await t.writer.write(wire.subarray(0,wire.length-4));
  await c.hold('missing-size-trailer');await rejection(t.writer.close(),decompressionError,'truncated gzip rejected on finalization');
  await rejection(t.output,decompressionError,'truncated gzip readable errors');await c.decodeChecked('gzip',bytes('gzip'),bytes('archive'));
  return {freshDecoderRecovered:true};
 },
 async X010(c){
  const t=c.open('gzip',true);await t.writer.write(bytes('gzip'));await c.hold('eof-before-trailing-write');
  await rejection(t.writer.write(Uint8Array.of(1,2,3)),decompressionError,'strict trailing garbage rejected');
  await rejection(t.output,decompressionError,'trailing garbage poisons readable');return {trailingBytes:3};
 },
 async X011(c){
  const t=c.open('deflate-raw');await t.writer.write(bytes('sheet').subarray(0,128));await c.hold('typed-prefix-before-invalid-chunk');
  await rejection(t.writer.write({not:'bytes'}),typeError,'invalid object chunk rejected');
  await rejection(t.output,typeError,'invalid chunk errors readable');await c.encodeChecked('deflate-raw',bytes('sheet'));
  return {freshEncoderRecovered:true,nativeRegistryReclamation:'external-teardown-only'};
 },
 async X012(c){
  const t=c.open('gzip'),data=bytes('archive');const boxed=new Uint8Array(data.length+10);boxed.fill(255);boxed.set(data,5);
  await t.writer.write(new DataView(boxed.buffer,5,100));t.writer.releaseLock();await c.hold('writer-lock-handoff');
  t.writer=t.stream.writable.getWriter();t.writer.closed.catch(()=>{});await t.writer.write(new Uint8Array(boxed.buffer,105,data.length-100));await t.writer.close();
  await c.roundtrip(await t.output,'gzip',data);return {sentinelBytesExcluded:10,writerReacquired:true};
 },
 async X013(c){
  const t=c.open('gzip');let controller,pulled=0,cancelReason;const reason=new Error('planned:X013-signal');
  const source=new ReadableStream({start(v){controller=v;},pull(){pulled++;},cancel(v){cancelReason=v;}},{highWaterMark:0});
  const signal=new AbortController();c.ownStopper('pipe-signal',r=>signal.abort(r));
  const destination=c.sink(t),pipe=c.track(source.pipeTo(destination,{signal:signal.signal}),'pipe');controller.enqueue(bytes('pack'));
  await c.until(()=>t.acceptedInputBytes===bytes('pack').length,'native destination accepted complete prefix');
  await c.hold('pipe-source-open');signal.abort(reason);await rejection(pipe,e=>e===reason,'pipe abort rejects exact reason');
  await rejection(t.output,e=>e===reason,'pipe abort errors output');ok(cancelReason===reason,'source cancellation callback witnessed');ok(pulled<=4,'finite source pull bound');
  return {sourceCancelled:true,acceptedPrefixBytes:t.acceptedInputBytes,nativeComputationPreemptionClaim:false};
 },
 async X014(c){
  const t=c.open('gzip',true,false);t.reader.releaseLock();const [a,b]=t.stream.readable.tee(),left=c.ownReader(a.getReader(),a),right=c.ownReader(b.getReader(),b);
  const kept=c.track(c.collect(right));const first=c.track(left.read());const wire=bytes('gzip');
  await t.writer.write(wire.subarray(0,wire.length-8));const prefix=await first;ok(!prefix.done&&prefix.value.length>0,'tee branch read prefix');
  const cancelled=c.track(left.cancel('planned:X014-one-branch'));await c.hold('tee-survivor-open');
  await t.writer.write(wire.subarray(wire.length-8));await t.writer.close();same(await kept,bytes('archive'),'surviving decompressed branch complete');await cancelled;
  return {cancelledBranches:1,survivingBytes:bytes('archive').length};
 },
 async X015(c){
  const t=c.open('gzip',true,false),wire=bytes('gzip');await t.writer.write(wire.subarray(0,wire.length-8));
  await c.hold('consumer-not-draining');await t.writer.write(wire.subarray(wire.length-8));await t.writer.close();
  same(await c.collect(t.reader),bytes('archive'),'queued decoded bytes survive delayed consumer');return {queueCapacityClaim:false};
 },
 async X016(c){
  const good=c.open('gzip',true),wire=bytes('gzip');await good.writer.write(wire.subarray(0,wire.length-8));
  const bad=c.open('gzip',true);await c.hold('good-and-bad-decoder-handles');
  const failure=c.track((async()=>{await bad.writer.write(Uint8Array.of(0,0,0,0,0,0,0,0,0,0));await bad.writer.close();})());
  await rejection(failure,decompressionError,'malformed sibling header rejected');await rejection(bad.output,decompressionError,'malformed sibling readable rejects');
  await good.writer.write(wire.subarray(wire.length-8));await good.writer.close();same(await good.output,bytes('archive'),'poison removes only bad decoder');
  return {poisonedSiblingIsolated:true};
 },
 async X018(c){
  const d=c.digest(),data=bytes('pack');await d.writer.write(data.subarray(0,12));await c.hold('pack-header-hashed-list');
  await d.writer.write(data.subarray(12));await d.writer.close();eq(hex(await d.stream.digest),vectors.sha1pack,'pack stream digest after peer closes first');
  eq(String(d.stream.bytesWritten),String(data.length),'pack byte count');return {sha1:vectors.sha1pack,bytesWritten:Number(d.stream.bytesWritten)};
 },
 async X019(c){
  const d=c.digest();await d.writer.write(bytes('pack').subarray(0,32));await c.hold('digest-abort-pending');
  const reason=new Error('planned:X019-digest-abort');await d.writer.abort(reason);await rejection(d.stream.digest,e=>e===reason,'digest abort rejects exact reason');
  await rejection(d.writer.write(bytes('pack')),e=>e===reason,'aborted digest refuses later write');await c.digestChecked(bytes('pack'),vectors.sha1pack);
  return {healthyDigestRecovered:true};
 },
 async X020(c){
  const d=c.digest(),reason=new Error('planned:X020-pack-source');let controller;const prefix=bytes('pack').subarray(0,12);
  const source=new ReadableStream({start(v){controller=v;}},{highWaterMark:0});c.ownStopper('digest-source',r=>controller.error(r));const pipe=c.pipe(source,c.sink(d));controller.enqueue(prefix);
  await c.until(()=>d.stream.bytesWritten===12n,'pack header accepted');await c.hold('pack-body-source-failure');controller.error(reason);
  await rejection(pipe,e=>e===reason,'pack source error rejects pipe');await rejection(d.stream.digest,e=>e===reason,'failed pack stream has no digest');
  eq(String(d.stream.bytesWritten),'12','accepted header bytes counted before source failure');return {sourceError:'planned:X020-pack-source',acceptedHeader:12};
 },
 async X021(c){
  const d=c.digest();await d.writer.write(bytes('archive'));await c.hold('digest-close-after-peer-poison');
  await d.writer.close();eq(hex(await d.stream.digest),vectors.sha1archive,'peer decoder poison leaves buffered digest bytes intact');
  return {sha1:vectors.sha1archive};
 },
 async X022(c){
  const d=c.digest();await d.writer.write(bytes('pack'));d.writer.releaseLock();await c.hold('unlocked-digest-dispose');
  d.stream[Symbol.dispose]();await rejection(d.stream.digest,e=>/DigestStream was disposed/.test(String(e)),'explicit digest disposal rejects digest');
  const writer=d.stream.getWriter();d.writer=writer;writer.closed.catch(()=>{});await rejection(d.writer.write(bytes('pack')),e=>/DigestStream was disposed/.test(String(e)),'disposed digest refuses new write');
  d.stream[Symbol.dispose]();return {explicitDisposal:true};
 },
 async X023(c){
  const raw=bytes('key'),key=await c.native(()=>crypto.subtle.importKey('raw',raw,{name:'HMAC',hash:'SHA-256'},false,['sign']));raw.fill(0);
  await c.hold('imported-public-fixture-key');const signature=await c.native(()=>crypto.subtle.sign('HMAC',key,bytes('pack')));
  eq(hex(signature),vectors.hmacpack,'native HMAC uses imported copy after caller mutates original');return {signature:vectors.hmacpack,publicFixtureOnly:true};
 },
 async X024(c){
  const t=c.open('gzip');await t.writer.write(bytes('archive'));await c.hold('encoder-survives-crypto-rejections');
  await t.writer.close();await c.roundtrip(await t.output,'gzip',bytes('archive'));return {encoderRecoveredAfterPeerCryptoErrors:true};
 }
};

export const peers={
 async raw(c){await c.encodeChecked('deflate-raw',bytes('sheet'));return {rawRoundtrip:true};},
 async decode(c){await c.decodeChecked('gzip',bytes('gzip'),bytes('archive'));return {gzipDecoded:true};},
 async digest(c){await c.digestChecked(bytes('pack'),vectors.sha1pack);return {sha1:vectors.sha1pack};},
 async sign(c){const key=await c.native(()=>crypto.subtle.importKey('raw',bytes('key'),{name:'HMAC',hash:'SHA-256'},false,['sign']));eq(hex(await c.native(()=>crypto.subtle.sign('HMAC',key,bytes('pack')))),vectors.hmacpack,'public fixture HMAC');return {hmac:vectors.hmacpack};},
 async archiveDigest(c){const d=c.digest(),input=bytes('archive');await d.writer.write(input);await d.writer.close();eq(hex(await d.stream.digest),vectors.sha1archive,'distinct peer archive SHA1');eq(String(d.stream.bytesWritten),String(input.length),'distinct peer archive byte count');return {sha1:vectors.sha1archive,bytesWritten:Number(d.stream.bytesWritten)};},
 async badGzip(c){const t=c.open('gzip',true);const attempt=c.track((async()=>{await t.writer.write(Uint8Array.of(0,0,0,0,0,0,0,0,0,0));await t.writer.close();})());await rejection(attempt,decompressionError,'peer malformed header');await rejection(t.output,decompressionError,'peer poisoned output');await c.decodeChecked('gzip',bytes('gzip'),bytes('archive'));return {poisonThenRecovery:true};},
 async cryptoErrors(c){await rejection(c.native(()=>crypto.subtle.digest('fixture-unsupported',bytes('archive'))),unsupported,'unsupported digest isolated');await rejection(c.native(()=>crypto.subtle.digest('SHA-256',{not:'bytes'})),typeError,'bad digest bytes isolated');const key=await c.native(()=>crypto.subtle.importKey('raw',bytes('key'),{name:'HMAC',hash:'SHA-256'},false,['sign']));await rejection(c.native(()=>crypto.subtle.sign('fixture-unsupported',key,bytes('pack'))),unsupported,'unsupported sign isolated');eq(hex(await c.native(()=>crypto.subtle.sign('HMAC',key,bytes('pack')))),vectors.hmacpack,'HMAC recovery after rejection');eq(hex(await c.native(()=>crypto.subtle.digest('SHA-256',bytes('archive')))),vectors.sha256archive,'native digest recovery after rejection');return {rejections:3,healthyNativeResults:2};}
};
