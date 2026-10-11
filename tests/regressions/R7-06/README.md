# R7-06 — ctx.exports props snapshots

Workerd export-loopback.c++:12–29 snapshots props with Frankenvalue at binding
specialization; io/worker.c++:2433–2442 decodes in the receiving IoContext.
The fixture isolates both caller and receiver mutations, uses a persistent
capability after caller disposal, rejects transient target/stream props at
binding time, and covers repeated local RPC, HTTP, forwarded binding, loaded
cross-script use and storage decode. R6-02/channels.mjs remains the storage
permission control. Old p-form stored service tokens remain readable; new q
contains encoded channel snapshots. Uses the bounded-port regression launcher.
