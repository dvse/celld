// client.mjs PORT: open the session socket, send a message, poke with a client that hangs up
// after 0.5 s, and report the socket's answer (or timeout).
const port = process.argv[2];
const ws = new WebSocket(`ws://127.0.0.1:${port}/session`);
ws.onopen = async () => {
  ws.send("go");
  await new Promise((resolve) => setTimeout(resolve, 300));
  const abort = new AbortController();
  setTimeout(() => abort.abort(), 500);
  fetch(`http://127.0.0.1:${port}/poke`, {signal: abort.signal}).catch(() => {});
};
ws.onmessage = (event) => { console.log(String(event.data)); process.exit(0); };
ws.onerror = () => { console.log("error"); process.exit(0); };
setTimeout(() => { console.log("timeout: no answer"); process.exit(0); }, 15000);
