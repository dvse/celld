// Sends kv, svc, kv, sql and expects four answers; exits 1 otherwise.
const socket = new WebSocket(process.argv[2]);
const answers = [];
socket.onopen = () => { for (const mode of ["kv", "svc", "kv", "sql"]) socket.send(mode); };
socket.onmessage = (event) => { answers.push(JSON.parse(event.data)); if (answers.length === 4) done(); };
const done = () => {
  const ok = JSON.stringify(answers.map((a) => a.value)) === JSON.stringify(["v1", "hi", "v1", 1]);
  console.log(JSON.stringify({ok, answers})); process.exit(ok ? 0 : 1);
};
setTimeout(done, 10000);
