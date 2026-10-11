// ws.mjs PORT PATH: send "0", "1", "2" and print the three replies as JSON (or an error string).
const [port, path] = process.argv.slice(2);
const ws = new WebSocket(`ws://127.0.0.1:${port}${path}`);
const got = [];
const done = setTimeout(() => { console.log(JSON.stringify({timeout: got})); process.exit(0); }, 10000);
ws.onopen = () => { for (const i of [0, 1, 2]) ws.send(String(i)); };
ws.onmessage = e => { got.push(String(e.data)); if (got.length === 3) { clearTimeout(done); console.log(JSON.stringify(got)); ws.close(); process.exit(0); } };
ws.onerror = e => { clearTimeout(done); console.log(JSON.stringify({error: String(e.message || e.type)})); process.exit(0); };
