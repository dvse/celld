// The Interplanetary Portal: binds the caller's replyTo as a hook on the caller's Overseer.
import {WorkerEntrypoint} from "cloudflare:workers";
export class Portal extends WorkerEntrypoint {
  async messagePlanetBob(message, replyTo, overseer) {
    return await this.env.OVERSEER.getByName(overseer).bindHook(replyTo);
  }
}
export default { fetch() { return new Response("portal"); } };
