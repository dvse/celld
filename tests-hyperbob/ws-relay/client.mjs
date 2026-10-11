const ws = new WebSocket(process.argv[2]);
ws.onopen = () => ws.send("hi");
ws.onmessage = (event) => { console.log(String(event.data)); process.exit(0); };
ws.onerror = () => { console.log("error"); process.exit(0); };
ws.onclose = (event) => { console.log("close " + event.code); process.exit(0); };
setTimeout(() => { console.log("timeout"); process.exit(0); }, 10000);
