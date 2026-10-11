export class Repro {
  constructor(state, env) {
    this.state = state; this.env = env;
    this.results = [];

    this.job = new Promise((resolve) => {
      this.resolveJob = resolve;
    });

    // Start work from the constructor event without keeping that event alive.
    state.blockConcurrencyWhile(async () => {
      void this.runJob();
    });
  }

  async runJob() {
    try {
      await this.job;
      this.results.push("awaited");

      if (this.mode === "fetch") await fetch(this.env.ORIGIN);
      if (this.mode === "block") await this.state.blockConcurrencyWhile(async () => {});
      this.results.push("fetched");

      await this.state.storage.put("result", "ok");
      this.results.push("stored");
    } catch (error) {
      this.results.push(`error: ${error.message}`);
    }
  }

  async fetch(request) {
    const path = new URL(request.url).pathname;

    if (path === "/resolve") {
      this.mode = new URL(request.url).searchParams.get("mode"); this.resolveJob();
      return Response.json({ resolved: true });
    }

    if (path === "/log") {
      return Response.json(this.results);
    }

    return new Response("ok");
  }
}

export default {
  async fetch(request, env) {
    const id = env.REPRO.idFromName(new URL(request.url).searchParams.get("mode"));
    return env.REPRO.get(id).fetch(request);
  },
};
