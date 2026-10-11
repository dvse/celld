const results = {};
for (const mode of ["handler", "loop", "waituntil"]) {
 results[mode] = await new Promise(resolve => {
  const ws = new WebSocket(`ws://127.0.0.1:${process.argv[2]}/?mode=${mode}`);
  let timer; const finish = value => { clearTimeout(timer); ws.close(); resolve(value); };
  timer = setTimeout(() => finish("TIMEOUT"), 3000);
  ws.onopen = () => ws.send("go"); ws.onmessage = m => finish(m.data);
  ws.onerror = () => finish("ERROR");
 });
}
console.log(JSON.stringify(results));
process.exit(0);
