// The code-mode runner: receives `self` and passes it on to a Portal, as executeCode's
// `env.INTERPLANETARY.messagePlanetBob(message, self)` does.
import {WorkerEntrypoint} from "cloudflare:workers";
export class Runner extends WorkerEntrypoint {
  async run({self, overseer}) { return await this.env.PORTAL.messagePlanetBob({prompt: "hi"}, self, overseer); }
}
export default { fetch() { return new Response("runner"); } };
