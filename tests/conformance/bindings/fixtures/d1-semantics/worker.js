// Newly authored direct-celld public-binding cases E201-E220.
// Source contract candidates, unreviewed and never run by the authoring task.
// One serial GET /case/<id> per fresh isolated deployment run; see README.
const has = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  }
  return value;
}
const cases = {
  E201: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, label TEXT); INSERT INTO ${t} VALUES (1,'red'),(2,'blue'),(3,'green');`, "seed lookup");
      const base = db.prepare(`SELECT label FROM ${t} WHERE id=?`);
      const red = base.bind(1), blue = red.bind(2), green = base.bind(3);
      c.eq(red === blue, false, "rebind returns a distinct statement");
      c.eq(base === red, false, "bind preserves the unbound template object");
      c.eq(await c.first(blue, "blue execution"), {label:"blue"}, "rebound statement uses replacement arguments");
      c.eq(await c.first(red, "red execution"), {label:"red"}, "earlier bound statement retains its arguments");
      c.eq(await c.first(green, "green execution"), {label:"green"}, "original template remains independently bindable");
      c.eq(await c.first(red, "red reuse"), {label:"red"}, "bound statement can be executed again");
    },
  },
  E202: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY); INSERT INTO ${t} VALUES (1);`, "seed numbered lookup");
      const result = await c.first(db.prepare(`SELECT ?2 AS quantity, ?1 AS sku, ?2 AS repeated, ?3 AS discount FROM ${t} WHERE id=?4`).bind("SKU-A", 7, null, 1), "numbered lookup");
      c.eq(result, {quantity:7, sku:"SKU-A", repeated:7, discount:null}, "numbered repeated parameters map by index rather than occurrence");
    },
  },
  E203: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, enabled, optional, note, amount);`, "create settings");
      const insert = db.prepare(`INSERT INTO ${t} VALUES (?, ?, ?, ?, ?)`);
      await c.batch(db, [insert.bind(1,true,null,"café\nready",2.5), insert.bind(2,false,null,"",0)], "save settings");
      const result = await c.all(db.prepare(`SELECT id, enabled, optional, note, amount, typeof(enabled) AS flag_type, typeof(optional) AS optional_type, typeof(note) AS note_type FROM ${t} ORDER BY id`), "load settings");
      c.eq(result.results, [{id:1,enabled:1,optional:null,note:"café\nready",amount:2.5,flag_type:"integer",optional_type:"null",note_type:"text"},{id:2,enabled:0,optional:null,note:"",amount:0,flag_type:"integer",optional_type:"null",note_type:"text"}], "boolean null text and finite number binds keep their intended SQL types and values");
    },
  },
  E204: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, payload BLOB);`, "create binary store");
      const buffer = new Uint8Array([8,0,255]).buffer;
      const wide = new Uint16Array([65,322]);
      const signed = new Int8Array([-1,0,127]);
      const insert = db.prepare(`INSERT INTO ${t} VALUES (?,?)`);
      const statements = [insert.bind(1,buffer), insert.bind(2,wide), insert.bind(3,signed), insert.bind(4,[1,0,255])];
      new Uint8Array(buffer).fill(9); wide.fill(9); signed.fill(9);
      await c.batch(db, statements, "save binary values");
      const result = await c.raw(db.prepare(`SELECT id,payload,typeof(payload) FROM ${t} ORDER BY id`), "load binary values");
      c.eq(result, [[1,[8,0,255],"blob"],[2,[65,66],"blob"],[3,[255,0,127],"blob"],[4,[1,0,255],"blob"]], "ArrayBuffer copies bytes and typed views copy byte-truncated elements at bind time");
      c.eq(result.every(row => Array.isArray(row[1])), true, "public D1 BLOB results are byte arrays");
    },
  },
  E205: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, label TEXT);`, "create method parity table");
      const first = await c.run(db.prepare(`INSERT INTO ${t} VALUES (1,'one') RETURNING id,label`), "run returning insert");
      const second = await c.all(db.prepare(`INSERT INTO ${t} VALUES (2,'two') RETURNING id,label`), "all returning insert");
      c.eq([first.success,second.success], [true,true], "all and run both expose successful results");
      c.eq([first.results,second.results], [[{id:1,label:"one"}],[{id:2,label:"two"}]], "both methods preserve DML RETURNING rows");
      const statement = db.prepare(`SELECT id,label FROM ${t} ORDER BY id`);
      const a = await c.all(statement, "all selection"), b = await c.run(statement, "run selection");
      c.eq(a.results, [{id:1,label:"one"},{id:2,label:"two"}], "all returns exact ordered data");
      c.eq(b.results, a.results, "run is also a read method");
    },
  },
  E206: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, note TEXT); INSERT INTO ${t} VALUES (1,NULL),(2,'later');`, "seed first selection");
      const selection = db.prepare(`SELECT id,note FROM ${t} ORDER BY id`);
      c.eq(await c.first(selection, "first object"), {id:1,note:null}, "first returns the ordered first row object");
      c.eq(await c.first(selection, "first scalar", "id"), 1, "first column selects one scalar");
      c.eq(await c.first(selection, "first null column", "note"), null, "present SQL NULL column returns null");
      const empty = db.prepare(`SELECT id,note FROM ${t} WHERE id=99`);
      c.eq(await c.first(empty, "empty first object"), null, "empty first returns null");
      c.eq(await c.first(empty, "empty first scalar", "id"), null, "empty first column returns null without a row");
    },
  },
  E207: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, label TEXT); INSERT INTO ${t} VALUES (1,'a'),(2,NULL);`, "seed export");
      const statement = db.prepare(`SELECT label AS caption,id AS record_id FROM ${t} ORDER BY id`);
      c.eq(await c.raw(statement, "raw data"), [["a",1],[null,2]], "raw preserves selected column order");
      c.eq(await c.raw(statement, "raw headings", {columnNames:true}), [["caption","record_id"],["a",1],[null,2]], "columnNames prepends one headings row");
      const empty = db.prepare(`SELECT label AS caption,id AS record_id FROM ${t} WHERE id=99`);
      c.eq(await c.raw(empty, "empty raw"), [], "empty raw has no data rows");
      c.eq(await c.raw(empty, "empty raw headings", {columnNames:true}), [["caption","record_id"]], "empty export retains its column headings");
    },
  },
  E208: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY); INSERT INTO ${t} VALUES (1);`, "seed special labels");
      const statement = db.prepare(`SELECT 'p' AS "__proto__",'c' AS "constructor",'s' AS "toString" FROM ${t}`);
      const result = await c.all(statement, "special object result");
      const row = result.results[0];
      c.eq(Object.keys(row).sort(), ["__proto__","constructor","toString"].sort(), "prototype-like SQL labels are own enumerable columns");
      c.eq([has(row,"__proto__"),has(row,"constructor"),has(row,"toString")], [true,true,true], "special columns never disappear into inherited properties");
      c.eq([row.__proto__,row.constructor,row.toString], ["p","c","s"], "special columns keep their exact scalar values");
      c.eq(await c.first(statement, "first special column", "__proto__"), "p", "first column uses the shaped own special column");
    },
  },
  E209: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY); INSERT INTO ${t} VALUES (1);`, "seed duplicate labels");
      const statement = db.prepare(`SELECT 10 AS amount,20 AS amount,30 AS other FROM ${t}`);
      c.eq((await c.all(statement, "duplicate object selection")).results, [{amount:20,other:30}], "object shape keeps the last duplicate column value");
      c.eq(await c.first(statement, "duplicate scalar selection", "amount"), 20, "first column shares last-duplicate shaping");
      c.eq(await c.raw(statement, "duplicate positional selection", {columnNames:true}), [["amount","amount","other"],[10,20,30]], "raw retains duplicate headings and both original positional values");
    },
  },
  E210: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      const result = await c.batch(db, [
        db.prepare(`CREATE TABLE ${t}(id INTEGER PRIMARY KEY, quantity INTEGER)`),
        db.prepare(`INSERT INTO ${t} VALUES (?,?)`).bind(1,4),
        db.prepare(`SELECT quantity FROM ${t} WHERE id=1`),
        db.prepare(`UPDATE ${t} SET quantity=quantity+? WHERE id=1`).bind(3),
        db.prepare(`SELECT quantity FROM ${t} WHERE id=1`),
      ], "schema write read batch");
      c.eq(result.length, 5, "batch returns one result per submitted statement");
      c.eq(result.map(item => item.success), [true,true,true,true,true], "all successful batch statements retain success flags");
      c.eq(result.map(item => item.results), [[],[],[{quantity:4}],[],[{quantity:7}]], "batch statements see earlier schema and writes in submission order");
      c.eq(await c.first(db.prepare(`SELECT quantity FROM ${t} WHERE id=1`), "committed batch read"), {quantity:7}, "successful batch final value is visible after return");
    },
  },
  E211: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, value INTEGER);`, "create metadata ledger");
      const result = await c.batch(db, [
        db.prepare(`INSERT INTO ${t} VALUES (11,1)`),
        db.prepare(`INSERT INTO ${t} VALUES (22,2)`),
        db.prepare(`UPDATE ${t} SET value=3 WHERE id=11`),
        db.prepare(`UPDATE ${t} SET value=4 WHERE id=99`),
        db.prepare(`SELECT id,value FROM ${t} ORDER BY id`),
      ], "snapshot metadata batch");
      c.eq(result.map(item => item.meta.changes), [1,1,1,0,0], "changes are captured for each batch statement");
      c.eq(result.map(item => item.meta.rows_written), [1,1,1,0,0], "rows_written does not accumulate earlier batch writes");
      c.eq(result.map(item => item.meta.last_row_id), [11,22,22,22,0], "write rowids are snapshotted while read rowid resets");
      c.eq(result.map(item => item.meta.changed_db), [true,true,true,false,false], "changed_db distinguishes writes no-op update and read");
      c.eq(result[4].results, [{id:11,value:3},{id:22,value:2}], "metadata accompanies the exact final batch rows");
    },
  },
  E212: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      const result = await c.exec(db, `-- first line; is a comment\nCREATE TABLE ${t}(id INTEGER PRIMARY KEY, note TEXT); INSERT INTO ${t} VALUES (1,'semi;colon');\n/* comment ; */ INSERT INTO ${t} VALUES (2,'two''s');\nUPDATE ${t}\n SET note=note||';done' WHERE id=1`, "parse multi statement script");
      c.eq(result.count, 4, "exec counts parsed statements rather than lines or semicolons");
      c.eq(Object.keys(result).sort(), ["count","duration"], "public exec exposes only count and duration");
      c.eq(Number.isFinite(result.duration) && result.duration >= 0, true, "exec duration is finite nonnegative metadata");
      c.eq((await c.all(db.prepare(`SELECT id,note FROM ${t} ORDER BY id`), "read parsed script effects")).results, [{id:1,note:"semi;colon;done"},{id:2,note:"two's"}], "comments quoted semicolons and final unterminated-by-semicolon statement execute correctly");
    },
  },
  E213: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      const result = await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, n INTEGER); INSERT INTO ${t} VALUES (1,2),(2,3),(3,4) RETURNING id; UPDATE ${t} SET n=n*2 RETURNING id,n; SELECT n FROM ${t} ORDER BY id;`, "exec returning script");
      c.eq(result.count, 4, "exec counts row-producing statements while discarding their results");
      c.eq(has(result,"results"), false, "public exec does not expose engine row sets");
      c.eq((await c.all(db.prepare(`SELECT id,n FROM ${t} ORDER BY id`), "read exec completion")).results, [{id:1,n:4},{id:2,n:6},{id:3,n:8}], "exec drains RETURNING statements and commits all successful effects");
    },
  },
  E214: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, note TEXT);`, "create read metadata table");
      const write = await c.run(db.prepare(`INSERT INTO ${t} VALUES (41,'saved')`), "write before readonly");
      c.eq([write.meta.changes,write.meta.rows_written,write.meta.last_row_id,write.meta.changed_db], [1,1,41,true], "write has concrete mutation metadata");
      const read = await c.all(db.prepare(`SELECT id,note FROM ${t} WHERE id=41`), "readonly after write");
      c.eq(read.results, [{id:41,note:"saved"}], "read after write returns the saved row");
      c.eq([read.meta.changes,read.meta.rows_written,read.meta.last_row_id,read.meta.changed_db], [0,0,0,false], "readonly metadata does not leak previous connection write counters");
      c.eq([read.meta.served_by,read.meta.served_by_region,read.meta.served_by_primary], ["celld","local",true], "celld explicitly identifies local primary service");
      c.eq(Number.isFinite(read.meta.duration) && read.meta.duration >= 0, true, "readonly duration remains well formed");
      c.eq(Number.isInteger(read.meta.size_after) && read.meta.size_after > 0, true, "database size is a positive integer without a page-size assumption");
    },
  },
  E215: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      const create = await c.run(db.prepare(`CREATE TABLE ${t}(id INTEGER PRIMARY KEY, n INTEGER)`), "schema mutation");
      c.eq([create.meta.rows_written,create.meta.changed_db], [0,true], "schema creation changes database without counted row writes");
      const idle = await c.run(db.prepare(`UPDATE ${t} SET n=7 WHERE id=99`), "no matching update");
      c.eq([idle.meta.rows_written,idle.meta.changes,idle.meta.changed_db], [0,0,false], "a writable statement with no matched row is not a database change");
      const drop = await c.run(db.prepare(`DROP TABLE ${t}`), "schema removal");
      c.eq([drop.meta.rows_written,drop.meta.changed_db], [0,true], "schema removal is visible to changed_db despite zero row writes");
    },
  },
  E216: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, n INTEGER); INSERT INTO ${t} VALUES (1,1),(2,2),(3,3);`, "seed first returning");
      const first = await c.first(db.prepare(`UPDATE ${t} SET n=n+10 RETURNING id,n`), "first mutation result");
      c.eq([1,2,3].includes(first.id) && first.n === first.id+10, true, "first RETURNING keeps one valid row without imposing return order");
      c.eq(Object.keys(first).sort(), ["id","n"], "first RETURNING exposes exactly one row shape");
      c.eq((await c.all(db.prepare(`SELECT id,n FROM ${t} ORDER BY id`), "verify all returning effects")).results, [{id:1,n:11},{id:2,n:12},{id:3,n:13}], "first drains the mutation to completion despite returning only one row");
    },
  },
  E217: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, n INTEGER); INSERT INTO ${t} VALUES (1,8);`, "seed session read");
      const session = db.withSession("first-primary"), other = db.withSession();
      c.eq([session.getBookmark(),other.getBookmark()], [null,null], "new constraint sessions start without completed-query bookmarks");
      c.eq(await c.first(session.prepare(`SELECT n FROM ${t} WHERE id=1`), "session read"), {n:8}, "session prepare reads its bound database");
      c.eq(session.getBookmark(), "celld:primary", "successful session query advances to the stable primary bookmark");
      c.eq(other.getBookmark(), null, "one session query does not mutate another session bookmark");
      const resumed = db.withSession(session.getBookmark());
      c.eq(resumed.getBookmark(), "celld:primary", "new session retains the supplied prior bookmark");
      c.eq(await c.first(resumed.prepare(`SELECT n FROM ${t} WHERE id=1`), "resumed session read"), {n:8}, "resumed session reads exact committed data");
      c.eq(resumed.getBookmark(), "celld:primary", "completed reads keep the stable opaque primary token");
    },
  },
  E218: {
    owned: [["DB", ""]],
    async run(c) {
      const db = c.env.DB, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, n INTEGER);`, "create session batch table");
      const session = db.withSession("first-unconstrained");
      c.eq(session.getBookmark(), null, "batch session has no initial completed-query bookmark");
      const result = await c.batch(session, [session.prepare(`INSERT INTO ${t} VALUES (1,6)`),session.prepare(`UPDATE ${t} SET n=n+2 WHERE id=1`),session.prepare(`SELECT n FROM ${t} WHERE id=1`)], "session batch");
      c.eq(result.map(item => item.results), [[],[],[{n:8}]], "session batch returns ordered dependent statement results");
      c.eq(session.getBookmark(), "celld:primary", "successful batch advances the session bookmark");
      c.eq(await c.first(db.prepare(`SELECT n FROM ${t} WHERE id=1`), "base read after session batch"), {n:8}, "session batch effects are committed to the underlying binding");
      c.eq(await c.first(session.prepare(`SELECT n FROM ${t} WHERE id=1`), "session read after batch"), {n:8}, "the same session reads its batch result");
    },
  },
  E219: {
    owned: [["DB", ""],["OTHER", ""]],
    async run(c) {
      const db = c.env.DB, other = c.env.OTHER, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, label TEXT); INSERT INTO ${t} VALUES (1,'primary');`, "seed shared identity");
      await c.exec(other, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, label TEXT); INSERT INTO ${t} VALUES (1,'separate');`, "seed separate identity");
      c.eq(await c.first(c.env.ALIAS.prepare(`SELECT label FROM ${t} WHERE id=1`), "alias read"), {label:"primary"}, "different binding and database names with one database_id share data");
      await c.run(c.env.ALIAS.prepare(`UPDATE ${t} SET label='alias-write' WHERE id=1`), "alias write");
      c.eq(await c.first(db.prepare(`SELECT label FROM ${t} WHERE id=1`), "shared read after alias"), {label:"alias-write"}, "alias writes are visible through the original binding");
      c.eq(await c.first(other.prepare(`SELECT label FROM ${t} WHERE id=1`), "isolated read"), {label:"separate"}, "a different database_id isolates an identical table and key");
    },
  },
  E220: {
    owned: [["FALLBACK", ""]],
    async run(c) {
      const db = c.env.FALLBACK, alias = c.env.FALLBACK_ALIAS, t = c.table();
      await c.exec(db, `CREATE TABLE ${t}(id INTEGER PRIMARY KEY, label TEXT); INSERT INTO ${t} VALUES (1,'by-name');`, "seed name identity");
      c.eq(await c.first(alias.prepare(`SELECT label FROM ${t} WHERE id=1`), "same name no-id read"), {label:"by-name"}, "two omitted-id declarations share their database_name identity");
      await c.run(c.env.EXPLICIT_NAME.prepare(`UPDATE ${t} SET label='explicit-id' WHERE id=1`), "explicit identity write");
      c.eq(await c.first(db.prepare(`SELECT label FROM ${t} WHERE id=1`), "fallback after explicit write"), {label:"explicit-id"}, "an explicit database_id equal to the fallback name addresses the same database");
      c.eq(await c.first(alias.prepare(`SELECT label FROM ${t} WHERE id=1`), "fallback alias after explicit write"), {label:"explicit-id"}, "no-id aliases retain shared identity after explicit-id access");
    },
  },
};

function context(id, env) {
  const assertions = [], trace = [], counts = {setup:0, main:0, cleanup:0};
  const c = {
    id, env, assertions, trace, counts, phase:"setup", claimed:[],
    table(suffix="") { return `d1_next_${id.toLowerCase()}${suffix}`; },
    eq(actual, expected, label) {
      if (JSON.stringify(canonical(actual)) !== JSON.stringify(canonical(expected))) {
        throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
      }
      assertions.push(label);
    },
    async call(label, operation) {
      if (++counts[c.phase] > 32) throw new Error(`public-call cap exceeded in ${c.phase}`);
      trace.push({phase:c.phase,label});
      return await operation();
    },
    exec(db, sql, label) { return c.call(label, () => db.exec(sql)); },
    batch(db, statements, label) { return c.call(label, () => db.batch(statements)); },
    all(statement, label) { return c.call(label, () => statement.all()); },
    run(statement, label) { return c.call(label, () => statement.run()); },
    first(statement, label, column) { return c.call(label, () => statement.first(column)); },
    raw(statement, label, options) { return c.call(label, () => statement.raw(options)); },
  };
  return c;
}
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const match = /^\/case\/(E2(?:0[1-9]|1[0-9]|20))$/.exec(url.pathname);
    if (request.method !== "GET" || !match || url.search) return new Response("GET /case/E201 through /case/E220 only", {status:404});
    const id = match[1], definition = cases[id];
    const required = id === "E219" ? ["DB","ALIAS","OTHER"] : id === "E220" ? ["FALLBACK","FALLBACK_ALIAS","EXPLICIT_NAME"] : ["DB"];
    const missing = required.filter(name => env[name] === undefined || env[name] === null);
    if (missing.length) return Response.json({id,status:"BLOCKED",reason:"Missing deployed D1 binding",missing,cleanup:{verified:false,tables:[],errors:[]}}, {status:503});
    const c = context(id, env);
    let failure = null;
    const cleanup = {verified:false, tables:[], errors:[]};
    try {
      // Verify no user/pre-existing table is present before claiming cleanup ownership.
      // The independently provisioned fresh store and serial runner are mandatory.
      for (const [binding,suffix] of definition.owned) {
        const db = env[binding], name = c.table(suffix);
        const existing = await c.first(db.prepare("SELECT name FROM sqlite_schema WHERE name=?").bind(name), `absence ${binding}:${name}`);
        if (existing !== null) throw new Error(`refusing pre-existing object ${binding}:${name}`);
        c.claimed.push({binding,db,name});
      }
      c.phase = "main";
      await definition.run(c);
    } catch (error) {
      failure = String(error && error.message || error);
    } finally {
      c.phase = "cleanup";
      for (const {binding,db,name} of c.claimed.slice().reverse()) {
        try {
          await c.exec(db, `DROP TABLE IF EXISTS ${name};`, `drop ${binding}:${name}`);
          const remaining = await c.first(db.prepare("SELECT name FROM sqlite_schema WHERE name=?").bind(name), `verify absent ${binding}:${name}`);
          if (remaining !== null) throw new Error(`owned object remains ${binding}:${name}`);
          cleanup.tables.push({binding,name,absent:true});
        } catch (error) {
          cleanup.errors.push(String(error && error.message || error));
        }
      }
      cleanup.verified = cleanup.errors.length === 0 && c.claimed.length === definition.owned.length;
    }
    const passed = failure === null && cleanup.verified && c.assertions.length > 0;
    return Response.json({id,status:passed?"PASS":"FAIL",contract:"PINNED_DIRECT_CELLD_SOURCE_CONTRACT",assertions:c.assertions,assertion_count:c.assertions.length,public_calls:c.counts,trace:c.trace,cleanup,failure,provenance:"External adapter must independently verify direct celld, fresh store and enforced limits."}, {status:passed?200:500});
  },
};
