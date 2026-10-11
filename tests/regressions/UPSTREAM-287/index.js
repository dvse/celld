import { DurableObject } from "cloudflare:workers";

const CODE = `
  import { DurableObject } from "cloudflare:workers";
  export class App extends DurableObject { ping() { return "pong"; } }
`;

export class Host extends DurableObject {
  facet() {
    const worker = this.env.LOADER.get("app", () => ({
      compatibilityDate: "2026-02-01", mainModule: "app.js", modules: { "app.js": CODE },
    }));
    return this.ctx.facets.get("app", () => ({ class: worker.getDurableObjectClass("App") }));
  }

  fetch(request) {
    const mode = new URL(request.url).searchParams.get("mode");
    const [client, server] = Object.values(new WebSocketPair());
    server.accept();
    if (mode === "handler") {
      // The facet call starts inside the message handler: it resolves.
      server.addEventListener("message", async () => server.send(await this.facet().ping()));
    } else {
      // The facet call starts in a loop that fetch() started (this is what capnweb's
      // newWorkersWebSocketRpcResponse does): it never settles once fetch() has returned.
      let wake;
      server.addEventListener("message", () => wake());
      const loop = (async () => {
        for (;;) {
          await new Promise((resolve) => (wake = resolve));
          server.send(await this.facet().ping());
        }
      })();
      if (mode === "waituntil") this.ctx.waitUntil(loop); // workaround: resolves
    }
    return new Response(null, { status: 101, webSocket: client });
  }
}

export default {
  fetch: (request, env) => env.HOST.getByName("host").fetch(request),
};
