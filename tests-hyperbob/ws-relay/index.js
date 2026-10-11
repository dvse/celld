// A WebSocket upgrade relayed Worker -> service binding -> Durable Object stub.fetch, with the
// Durable Object placed on another node (the Hyperbob published-socket path).
import {DurableObject, WorkerEntrypoint} from "cloudflare:workers";
export class Room extends DurableObject {
  async fetch(request) {
    if (request.headers.get("upgrade") !== "websocket") return new Response("room");
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    server.addEventListener("message", (event) => server.send("echo:" + event.data));
    return new Response(null, {status: 101, webSocket: client});
  }
}
export class Kernel extends WorkerEntrypoint {
  async fetch(request) {
    const name = new URL(request.url).searchParams.get("n");
    // Rebuilt the way Hyperbob's publication hop rebuilds it.
    // A fresh request carrying only the transport marker, as Hyperbob's publication
    // ingress builds it (no Connection header).
    const headers = new Headers({upgrade: "websocket"});
    const response = await this.ctx.exports.Room.getByName(name).fetch(
      new Request(request.url, {method: "GET", headers}));
    console.log("kernel hop status " + response.status);
    return response;
  }
}
export class Gateway extends WorkerEntrypoint {
  prepare() { return this.env.KERNEL; }
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === "/returned") {
      const kernel = await env.GATEWAY.prepare();
      try { return await kernel.fetch(request); }
      catch (error) { console.log("returned relay failed: " + error.stack); throw error; }
    }
    if (url.pathname === "/direct") return env.ROOM.getByName(url.searchParams.get("n")).fetch(request);
    return env.KERNEL.fetch(request);
  },
};
