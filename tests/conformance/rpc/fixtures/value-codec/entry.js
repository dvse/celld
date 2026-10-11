// Optional standalone fixture entry. Stage the repository-relative imports intact.
// This does not modify the pilot fixture, launch a process, or provision a runner.
import pilotWorker, { Root as PilotRoot } from '../../fixture/index.js';
import { extendCodecRoot, codecCases } from './codec.js';

export class Root extends extendCodecRoot(PilotRoot) {
  async run(id, peerName) {
    if (!Object.hasOwn(codecCases, id)) return super.run(id, peerName);
    const peer = this.env.ROOT.getByName(peerName), origin = this.inspect();
    const tag = id + ':' + crypto.randomUUID();
    let owner, traceEntered = false, phase = 'precondition';
    try {
      owner = await peer.inspect();
      if (origin.isolate === owner.isolate || origin.root === owner.root) {
        throw new Error('PRECONDITION: codec roots must be distinct remote recipients');
      }
      traceEntered = true; phase = 'trace';
      // codecCases includes codecCleanup in a finally block.
      const evidence = await codecCases[id]({ peer, tag });
      return { id, status: 'PASS', phase: 'complete', origin, owner, evidence, traceEntered, cleanup: { status: 'ok' } };
    } catch (error) {
      const text = String(error), blocked = !traceEntered || error?.code === 'CODEC_PRECONDITION' || error?.name === 'CodecPreconditionError' || text.includes('PRECONDITION:');
      const cleanupFailed = text.includes('CLEANUP_BLOCKED:') || text.includes('codec cleanup:');
      return { id, status: blocked ? 'BLOCKED' : 'FAIL', phase: cleanupFailed ? 'cleanup' : blocked ? 'precondition' : phase, origin, owner, error: text, errorName: error?.name, errorCode: error?.code, traceEntered: blocked ? false : traceEntered, setupOperationsEntered: traceEntered, cleanup: { status: cleanupFailed ? 'FAIL' : traceEntered ? 'ok' : 'NOT_RUN' } };
    }
  }
}

// Reuses the existing /identity and /run request interface. No outgoing HTTP here.
export default pilotWorker;
