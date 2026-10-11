// One I/O context per Durable Object (workerd io/io-context.h): work a continuation of one event
// starts must survive whichever other event of the same object happened to run that
// continuation. The Session object accepts a WebSocket in fetch (the long-lived event). Each
// message parks on a promise that a separate HTTP request (/poke) resolves; the continuation then
// starts a slow call to another object and answers on the socket. The /poke client hangs up
// before the slow call finishes, so a celld that hands the slow call to the /poke event cancels it
// with that event, and the socket never gets its answer.
import {DurableObject} from "cloudflare:workers";
export class Slow extends DurableObject {
  async work(ms) { await new Promise((resolve) => setTimeout(resolve, ms)); return "slow-done"; }
}
export class Session extends DurableObject {
  fetch(request) {
    if (new URL(request.url).pathname === "/poke") {
      this.release?.();
      return new Promise(() => {});
    }
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    server.addEventListener("message", () => {
      void (async () => {
        await new Promise((resolve) => { this.release = resolve; });
        const result = await this.env.SLOW.getByName("s").work(3000);
        server.send("answer:" + result);
      })();
    });
    return new Response(null, {status: 101, webSocket: client});
  }
}
export default {
  fetch(request, env) { return env.SESSION.getByName("one").fetch(request); },
};
