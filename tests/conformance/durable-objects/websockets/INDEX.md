# durable-objects/websockets

26 cases; 26 dispatched by the runner. Runtime-specific applicability and outcomes are in RESULTS.json.

| Case | Quick | Adapter |
|---|---|---|
| [Accept upgrades independently](accept-upgrades-independently.case.json) | no | topology |
| [Carry legal UTF-8 close boundary](carry-legal-utf-8-close-boundary.case.json) | no | topology |
| [Change binary representation between deliveries](change-binary-representation-between-deliveries.case.json) | no | topology |
| [Close held application work locally](close-held-application-work-locally.case.json) | no | topology |
| [Close in receiver message turn](close-in-receiver-message-turn.case.json) | no | topology |
| [Drain client frames before clean close](drain-client-frames-before-clean-close.case.json) | no | topology |
| [Drain server frames before clean close](drain-server-frames-before-clean-close.case.json) | no | topology |
| [Keep concurrent client lanes independent](keep-concurrent-client-lanes-independent.case.json) | no | topology |
| [Keep independent application credits moving](keep-independent-application-credits-moving.case.json) | no | topology |
| [Keep mixed message opcodes distinct](keep-mixed-message-opcodes-distinct.case.json) | no | topology |
| [Make repeated close calls idempotent](make-repeated-close-calls-idempotent.case.json) | no | topology |
| [Preserve application close metadata](preserve-application-close-metadata.case.json) | no | topology |
| [Preserve both directions while replies are held](preserve-both-directions-while-replies-are-held.case.json) | no | topology |
| [Relay witnessed messages across peers](relay-witnessed-messages-across-peers.case.json) | no | topology |
| [Respect native binary view ranges](respect-native-binary-view-ranges.case.json) | no | topology |
| [Retain empty message boundaries](retain-empty-message-boundaries.case.json) | no | topology |
| [Route server fanout to exact peers](route-server-fanout-to-exact-peers.case.json) | no | topology |
| [Send reentrantly from message listener](send-reentrantly-from-message-listener.case.json) | no | topology |
| [Serve third peer beside held sockets](serve-third-peer-beside-held-sockets.case.json) | no | topology |
| [Settle competing normal close requests](settle-competing-normal-close-requests.case.json) | no | topology |
| [Snapshot binary bytes before mutation](snapshot-binary-bytes-before-mutation.case.json) | no | topology |
| [Use fresh socket after clean completion](use-fresh-socket-after-clean-completion.case.json) | no | topology |
| [ws relay](ws-relay.case.json) | no | example |
| [ws session loop](ws-session-loop.case.json) | no | example |
| [wsclient](wsclient.case.json) | yes | example |
| [wsecho](wsecho.case.json) | no | example |
