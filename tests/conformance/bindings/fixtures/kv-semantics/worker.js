// Newly authored direct-celld source-contract cases K201-K220.
// Source-only deliverable. No claim of execution or universal Cloudflare parity.
// Execute one GET /case/Knnn at a time in a disposable, isolated deployment.
const PREFIX = "__celld_kv_semantics_v1__/";
const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
function canonical(x) {
  if (Array.isArray(x)) return x.map(canonical);
  if (x !== null && typeof x === "object") {
    const out = Object.create(null);
    for (const k of Object.keys(x).sort()) out[k] = canonical(x[k]);
    return out;
  }
  return x;
}
function makeAssertions() {
  const passed = [];
  return {
    passed,
    equal(actual, expected, label) {
      if (JSON.stringify(canonical(actual)) !== JSON.stringify(canonical(expected))) {
        throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
      }
      passed.push(label);
    },
    ok(value, label) {
      if (!value) throw new Error(label);
      passed.push(label);
    },
    bytes(actual, expected, label) {
      this.ok(actual instanceof ArrayBuffer, `${label}: ArrayBuffer result`);
      this.equal([...new Uint8Array(actual)], expected, label);
    },
  };
}
const cases = {
  K201: {
    owned: { A: ["empty", "absent"] },
    async run({ A, k, t }) {
      t.equal(await A.get(k("absent")), null, "absent is null");
      await A.put(k("empty"), "");
      t.equal(await A.get(k("empty")), "", "empty text is present");
      const page = await A.list({ prefix: k("") });
      t.equal(page.keys.map(x => x.name), [k("empty")], "empty value remains listed");
      await A.delete(k("empty"));
      t.equal(await A.get(k("empty")), null, "delete changes present-empty to absent");
      await A.put(k("empty"), "restored");
      t.equal(await A.get(k("empty")), "restored", "deleted name can be recreated");
    },
  },
  K202: {
    owned: { A: ["config"] },
    async run({ A, k, t }) {
      const text = '{"enabled":true,"title":"café 🧪","nested":{"n":7},"items":[null,false,0]}';
      const expected = { enabled: true, title: "café 🧪", nested: { n: 7 }, items: [null, false, 0] };
      await A.put(k("config"), text);
      const parsed = await A.get(k("config"), "json");
      t.equal(parsed, expected, "json selector parses structured configuration");
      parsed.nested.n = 99;
      parsed.items.push("local");
      t.equal(await A.get(k("config"), { type: "json" }), expected, "later parse is independent of local mutation");
      t.equal(await A.get(k("config")), text, "default text preserves original JSON serialization");
    },
  },
  K203: {
    owned: { A: ["slice"] },
    async run({ A, k, t }) {
      const backing = new Uint8Array([201, 202, 0, 127, 128, 255, 203]);
      const view = new DataView(backing.buffer, 2, 4);
      const pending = A.put(k("slice"), view);
      backing.fill(41);
      await pending;
      t.bytes(await A.get(k("slice"), "arrayBuffer"), [0, 127, 128, 255], "view offset and extent are copied before caller reuse");
    },
  },
  K204: {
    owned: { A: ["attachment"] },
    async run({ A, k, t }) {
      const input = new Uint8Array([11, 0, 255, 12]).buffer;
      await A.put(k("attachment"), input);
      new Uint8Array(input).fill(88);
      const first = await A.get(k("attachment"), { type: "arrayBuffer" });
      t.bytes(first, [11, 0, 255, 12], "ArrayBuffer put stores independent bytes");
      new Uint8Array(first).fill(99);
      const second = await A.get(k("attachment"), "arrayBuffer");
      t.bytes(second, [11, 0, 255, 12], "mutating a returned buffer cannot mutate storage");
      t.ok(first !== second, "reads materialize separate ArrayBuffers");
    },
  },
  K205: {
    owned: { A: ["upload"] },
    async run({ A, k, t }) {
      // Split a valid UTF-8 euro sign across chunk boundaries, plus binary NUL.
      const chunks = [new Uint8Array([65, 0xe2]), new Uint8Array(0), new Uint8Array([0x82]), new Uint8Array([0xac, 0, 66])];
      let index = 0;
      const stream = new ReadableStream({ pull(controller) {
        if (index === chunks.length) controller.close();
        else controller.enqueue(chunks[index++]);
      } });
      await A.put(k("upload"), stream, { metadata: { kind: "upload", chunks: 4 } });
      t.equal(index, 4, "put consumed all four finite chunks");
      t.equal(stream.locked, false, "put released its reader lock");
      t.bytes(await A.get(k("upload"), "arrayBuffer"), [65, 0xe2, 0x82, 0xac, 0, 66], "stream chunks concatenate without offset or zero-chunk loss");
      const read = await A.getWithMetadata(k("upload"), "text");
      t.equal(read.value, "A€\u0000B", "decoding occurs after byte concatenation");
      t.equal(read.metadata, { kind: "upload", chunks: 4 }, "stream upload retains metadata");
    },
  },
  K206: {
    owned: { A: ["download"] },
    async run({ A, k, t }) {
      await A.put(k("download"), "old-body");
      const oldStream = await A.get(k("download"), "stream");
      t.ok(oldStream instanceof ReadableStream, "stream selector returns a ReadableStream");
      await A.put(k("download"), "new-body");
      const newStream = await A.get(k("download"), { type: "stream" });
      t.ok(newStream !== oldStream, "reads return independent streams");
      t.equal(await new Response(newStream).text(), "new-body", "new download sees completed replacement");
      t.equal(await new Response(oldStream).text(), "old-body", "unconsumed earlier download remains its read snapshot");
      t.equal(await A.get(k("download")), "new-body", "consuming earlier stream does not revert storage");
    },
  },
  K207: {
    owned: { A: ["profile"] },
    async run({ A, k, t }) {
      const metadata = { revision: 1, labels: ["saved"], preferences: { compact: false } };
      const expected = { revision: 1, labels: ["saved"], preferences: { compact: false } };
      const pending = A.put(k("profile"), "body", { metadata });
      metadata.revision = 2;
      metadata.labels.push("local");
      metadata.preferences.compact = true;
      await pending;
      const first = await A.getWithMetadata(k("profile"));
      t.equal(first.metadata, expected, "metadata serializes before input mutation");
      first.metadata.labels.push("read-local");
      first.metadata.preferences.compact = true;
      t.equal((await A.getWithMetadata(k("profile"))).metadata, expected, "returned metadata mutation is not persisted");
      t.equal((await A.list({ prefix: k("") })).keys, [{ name: k("profile"), metadata: expected }], "list independently parses stored metadata");
    },
  },
  K208: {
    owned: { A: ["document"] },
    async run({ A, k, t }) {
      await A.put(k("document"), "version-one", { metadata: { owner: "fixture", old: true } });
      await A.put(k("document"), "version-two", { metadata: { revision: 2 } });
      const replaced = await A.getWithMetadata(k("document"));
      t.equal([replaced.value, replaced.metadata], ["version-two", { revision: 2 }], "replacement metadata replaces instead of merging");
      t.equal((await A.list({ prefix: k("") })).keys, [{ name: k("document"), metadata: { revision: 2 } }], "list has replacement metadata only");
      await A.put(k("document"), "version-three");
      const cleared = await A.getWithMetadata(k("document"));
      t.equal([cleared.value, cleared.metadata], ["version-three", null], "omitting metadata on replacement clears old metadata");
      t.equal((await A.list({ prefix: k("") })).keys, [{ name: k("document") }], "cleared metadata field is absent from list");
    },
  },
  K209: {
    owned: { A: ["false", "zero", "null", "absent"] },
    async run({ A, k, t }) {
      await A.put(k("false"), "f", { metadata: false });
      await A.put(k("zero"), "z", { metadata: 0 });
      await A.put(k("null"), "n", { metadata: null });
      await A.put(k("absent"), "a");
      t.equal((await A.getWithMetadata(k("false"))).metadata, false, "false metadata survives");
      t.equal((await A.getWithMetadata(k("zero"))).metadata, 0, "zero metadata survives");
      const listed = (await A.list({ prefix: k("") })).keys;
      t.equal(listed, [
        { name: k("absent") }, { name: k("false"), metadata: false },
        { name: k("null"), metadata: null }, { name: k("zero"), metadata: 0 },
      ], "list distinguishes absent metadata from explicit JSON null and falsy scalars");
    },
  },
  K210: {
    owned: { A: ["hole"] }, raw: { A: ["__proto__", "constructor", "toString"] },
    async run({ A, k, t }) {
      await A.put("__proto__", "prototype-value");
      await A.put("constructor", "constructor-value");
      await A.put("toString", "string-value");
      const values = await A.get(["toString", k("hole"), "__proto__", "constructor", "toString"]);
      t.ok(values instanceof Map, "bulk returns Map rather than property bag");
      t.equal([...values.keys()], ["toString", k("hole"), "__proto__", "constructor"], "Map preserves first occurrence order and collapses duplicate key");
      t.equal([...values.values()], ["string-value", null, "prototype-value", "constructor-value"], "special property names and missing hole stay correctly paired");
      t.ok(values.has(k("hole")), "missing requested key remains a Map entry");
    },
  },
  K211: {
    owned: { A: ["first", "second", "missing"] },
    async run({ A, k, t }) {
      await A.put(k("first"), '{"name":"one","n":1}', { metadata: { revision: 11 } });
      await A.put(k("second"), '[false,0,"two"]', { metadata: ["revision", 22] });
      const values = await A.getWithMetadata([k("second"), k("missing"), k("first")], { type: "json" });
      t.ok(values instanceof Map, "bulk metadata result is Map");
      t.equal([...values.entries()], [
        [k("second"), { value: [false, 0, "two"], metadata: ["revision", 22] }],
        [k("missing"), { value: null, metadata: null }],
        [k("first"), { value: { name: "one", n: 1 }, metadata: { revision: 11 } }],
      ], "bulk JSON conversion preserves per-key metadata pairing and null holes");
      values.get(k("first")).metadata.revision = 99;
      t.equal((await A.getWithMetadata(k("first"), "json")).metadata, { revision: 11 }, "bulk decoded metadata is detached from storage");
    },
  },
  K212: {
    owned: { A: ["a", "b", "c", "missing"] },
    async run({ A, k, t }) {
      await A.put(k("a"), "A");
      await A.put(k("b"), "B");
      await A.put(k("c"), "C");
      await A.deleteBulk([k("b"), k("missing"), k("b")]);
      t.equal([...await A.get([k("a"), k("b"), k("c"), k("missing")])], [[k("a"), "A"], [k("b"), null], [k("c"), "C"], [k("missing"), null]], "duplicate and absent deletions preserve untargeted keys");
      await A.deleteBulk(k("a"));
      t.equal((await A.list({ prefix: k("") })).keys.map(x => x.name), [k("c")], "scalar deleteBulk branch removes exactly one key");
      await A.put(k("b"), "B2");
      t.equal(await A.get(k("b")), "B2", "bulk-deleted key can be recreated");
    },
  },
  K213: {
    owned: { A: ["order/10", "order/2", "order/A", "order/a", "order/é", "order/\ue000", "order/🧪"] },
    async run({ A, k, t }) {
      const input = ["order/🧪", "order/2", "order/é", "order/A", "order/\ue000", "order/a", "order/10"];
      for (const name of input) await A.put(k(name), name);
      const page = await A.list({ prefix: k("order/") });
      t.equal(page.keys.map(x => x.name), ["order/10", "order/2", "order/A", "order/a", "order/é", "order/\ue000", "order/🧪"].map(k), "list uses UTF-8 byte order, not insertion, numeric, locale, or UTF-16 order");
      t.equal(page.list_complete, true, "small sorted catalog completes in one page");
    },
  },
  K214: {
    owned: { A: ["A%_/1", "A%_/2", "a%_/3", "ABx/4", "A%X/5", "A%_/1-near"] },
    async run({ A, k, t }) {
      for (const name of ["a%_/3", "A%_/2", "ABx/4", "A%X/5", "A%_/1-near", "A%_/1"]) await A.put(k(name), name);
      const page = await A.list({ prefix: k("A%_/") });
      t.equal(page.keys.map(x => x.name), [k("A%_/1"), k("A%_/1-near"), k("A%_/2")], "prefix is case-sensitive and treats percent and underscore literally");
      t.equal((await A.list({ prefix: k("A%_/1") })).keys.map(x => x.name), [k("A%_/1"), k("A%_/1-near")], "a prefix includes exact key and longer descendants");
    },
  },
  K215: {
    owned: { A: ["pages/a", "pages/b", "pages/c", "pages/d"] },
    async run({ A, k, t }) {
      for (const suffix of ["d", "b", "a", "c"]) await A.put(k(`pages/${suffix}`), suffix);
      const first = await A.list({ prefix: k("pages/"), limit: 2 });
      t.equal(first.keys.map(x => x.name), [k("pages/a"), k("pages/b")], "first page has exactly first two keys");
      t.equal(first.list_complete, false, "lookahead finds additional keys");
      t.ok(typeof first.cursor === "string" && first.cursor.length > 0, "nonterminal page provides opaque cursor");
      const second = await A.list({ prefix: k("pages/"), limit: 2, cursor: first.cursor });
      t.equal(second.keys.map(x => x.name), [k("pages/c"), k("pages/d")], "second page resumes strictly after first");
      t.equal(second.list_complete, true, "exactly full final page is complete");
      t.equal(has(second, "cursor"), false, "complete page does not advertise another cursor");
    },
  },
  K216: {
    owned: { A: ["scan/a", "scan/b", "scan/c", "scan/d", "scan/e", "scan/f", "scan/g"] },
    async run({ A, k, t }) {
      for (const suffix of ["a", "c", "e", "g"]) await A.put(k(`scan/${suffix}`), suffix);
      const first = await A.list({ prefix: k("scan/"), limit: 2 });
      t.equal(first.keys.map(x => x.name), [k("scan/a"), k("scan/c")], "cursor first names c");
      t.equal(first.list_complete, false, "initial page is nonterminal");
      await A.delete(k("scan/a"));
      await A.delete(k("scan/c"));
      for (const suffix of ["b", "d", "f"]) await A.put(k(`scan/${suffix}`), suffix);
      const second = await A.list({ prefix: k("scan/"), limit: 2, cursor: first.cursor });
      t.equal(second.keys.map(x => x.name), [k("scan/d"), k("scan/e")], "deleted cursor key still resumes by name; earlier insertion is behind cursor");
      t.equal(second.list_complete, false, "second page remains nonterminal");
      const third = await A.list({ prefix: k("scan/"), limit: 2, cursor: second.cursor });
      t.equal(third.keys.map(x => x.name), [k("scan/f"), k("scan/g")], "later insertions remain visible without offset skip");
      t.equal(third.list_complete, true, "fixed three-page trace terminates");
    },
  },
  K217: {
    owned: { A: ["🧪", "🧪/a", "🧪/b", "🧪x", "🧫/a", "🧩/a"] },
    async run({ A, k, t }) {
      for (const suffix of ["🧫/a", "🧪x", "🧪/b", "🧪", "🧩/a", "🧪/a"]) await A.put(k(suffix), suffix);
      const first = await A.list({ prefix: k("🧪"), limit: 2 });
      t.equal(first.keys.map(x => x.name), [k("🧪"), k("🧪/a")], "astral-ending prefix includes exact name and first descendant");
      t.equal(first.list_complete, false, "emoji-prefix page produces continuation");
      const second = await A.list({ prefix: k("🧪"), limit: 2, cursor: first.cursor });
      t.equal(second.keys.map(x => x.name), [k("🧪/b"), k("🧪x")], "UTF-8 cursor roundtrip retains every astral-prefixed key");
      t.equal(second.list_complete, true, "astral successor bound excludes adjacent glyphs on both sides");
    },
  },
  K218: {
    owned: { A: ["shared", "only-a"], B: ["shared", "only-b"] },
    async run({ A, B, k, t }) {
      await A.put(k("shared"), "tenant-A", { metadata: { tenant: "A" } });
      await B.put(k("shared"), "tenant-B", { metadata: { tenant: "B" } });
      await A.put(k("only-a"), "A");
      await B.put(k("only-b"), "B");
      t.equal((await A.getWithMetadata(k("shared"))).metadata, { tenant: "A" }, "namespace A owns its metadata");
      t.equal((await B.getWithMetadata(k("shared"))).metadata, { tenant: "B" }, "namespace B owns its metadata");
      t.equal((await A.list({ prefix: k("") })).keys.map(x => x.name), [k("only-a"), k("shared")], "A listing excludes B-only row");
      await A.deleteBulk([k("shared"), k("only-a")]);
      t.equal(await A.get(k("shared")), null, "A deletion took effect");
      t.equal(await B.get(k("shared")), "tenant-B", "A deletion cannot remove same name in B");
      t.equal((await B.list({ prefix: k("") })).keys.map(x => x.name), [k("only-b"), k("shared")], "B catalog remains intact");
    },
  },
  K219: {
    owned: { A: ["retention"] },
    async run({ A, k, t }) {
      const deadline = Math.floor(Date.now() / 1000) + 3600;
      await A.put(k("retention"), "temporary", { expiration: deadline, metadata: { phase: "temporary" } });
      t.equal((await A.list({ prefix: k("") })).keys, [{ name: k("retention"), metadata: { phase: "temporary" }, expiration: deadline }], "absolute expiration is reported in seconds with row metadata");
      await A.put(k("retention"), "permanent", { metadata: { phase: "permanent" } });
      const page = await A.list({ prefix: k("") });
      t.equal(page.keys, [{ name: k("retention"), metadata: { phase: "permanent" } }], "replacement without expiry clears old deadline rather than inheriting it");
      t.equal(await A.get(k("retention")), "permanent", "promoted value remains readable");
    },
  },
  K220: {
    owned: { A: ["jobs/a", "jobs/b", "jobs/c", "jobs/d"] },
    async run({ A, k, t }) {
      const jobs = ["d", "b", "a", "c"];
      // Four finite, disjoint writes overlap; no same-key ordering is asserted.
      await Promise.all(jobs.map((name, i) => A.put(k(`jobs/${name}`), `result-${name}`, { metadata: { ordinal: i } })));
      const [values, page] = await Promise.all([
        A.getWithMetadata(jobs.map(name => k(`jobs/${name}`))),
        A.list({ prefix: k("jobs/") }),
      ]);
      t.equal([...values.entries()], jobs.map((name, i) => [k(`jobs/${name}`), { value: `result-${name}`, metadata: { ordinal: i } }]), "acknowledged fan-out preserves every disjoint result and metadata");
      t.equal(page.keys.map(x => x.name), ["a", "b", "c", "d"].map(name => k(`jobs/${name}`)), "fan-in catalog contains exact complete key set");
      t.equal(page.list_complete, true, "fan-in fits complete single page");
      await Promise.all([A.delete(k("jobs/b")), A.delete(k("jobs/d"))]);
      t.equal((await A.list({ prefix: k("jobs/") })).keys.map(x => x.name), [k("jobs/a"), k("jobs/c")], "concurrent disjoint deletions preserve surviving jobs");
    },
  },
};

async function execute(id, env) {
  const definition = cases[id];
  const t = makeAssertions();
  const trace = [];
  const operationCounts = { setup: 0, case: 0, cleanup: 0 };
  let phase = "setup";
  const k = suffix => `${PREFIX}${id}/${suffix}`;
  const owned = {};
  const bindings = {};
  for (const name of Object.keys(definition.owned)) {
    const raw = env[`KV_${name}`];
    if (!raw) return { id, status: "BLOCKED", reason: `Missing KV_${name} public binding`, runtime_verified: false };
    owned[name] = [...definition.owned[name].map(k), ...(definition.raw?.[name] ?? [])];
    bindings[name] = {};
    for (const method of ["get", "getWithMetadata", "put", "delete", "deleteBulk", "list"]) {
      if (typeof raw[method] !== "function") return { id, status: "BLOCKED", reason: `Missing KV_${name}.${method}`, runtime_verified: false };
      bindings[name][method] = (...args) => {
        if (++operationCounts[phase] > 64) throw new Error(`${phase} exceeded 64 KV calls`);
        trace.push({ phase, binding: name, method, argument: args[0] });
        return raw[method](...args);
      };
    }
  }
  let failure = null;
  const cleanupErrors = [];
  try {
    for (const name of Object.keys(owned)) {
      for (const key of owned[name]) await bindings[name].delete(key);
    }
    phase = "case";
    await definition.run({ ...bindings, k, t });
  } catch (error) {
    failure = { phase, message: String(error?.message ?? error) };
  } finally {
    phase = "cleanup";
    for (const name of Object.keys(owned)) {
      for (const key of owned[name]) {
        try { await bindings[name].delete(key); }
        catch (error) { cleanupErrors.push({ binding: name, key, message: String(error?.message ?? error) }); }
      }
      try {
        const remaining = await bindings[name].get(owned[name]);
        if (!(remaining instanceof Map) || remaining.size !== owned[name].length || [...remaining.values()].some(value => value !== null)) {
          cleanupErrors.push({ binding: name, message: "Cleanup verification did not return one null Map entry for every owned key" });
        }
      } catch (error) {
        cleanupErrors.push({ binding: name, message: String(error?.message ?? error) });
      }
    }
  }
  return {
    id,
    status: failure || cleanupErrors.length ? "FAIL" : "PASS",
    qualification: "DIRECT_CELLD_SOURCE_CONTRACT_ONLY",
    assertions: t.passed,
    assertion_count: t.passed.length,
    operation_counts: operationCounts,
    trace,
    failure,
    cleanup: { verified: cleanupErrors.length === 0, errors: cleanupErrors },
  };
}

export default {
  async fetch(request, env) {
    const match = /^\/case\/(K2(?:0[1-9]|1[0-9]|20))$/.exec(new URL(request.url).pathname);
    if (request.method !== "GET" || !match || !has(cases, match[1])) {
      return Response.json({ status: "NOT_RUN", message: "Use GET /case/K201 through /case/K220" }, { status: 404 });
    }
    const result = await execute(match[1], env);
    return Response.json(result, { status: result.status === "PASS" ? 200 : result.status === "BLOCKED" ? 503 : 500 });
  },
};
