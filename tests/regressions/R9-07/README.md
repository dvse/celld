R9-07. Workerd api/system-streams.c++:70–98 distinguishes read error from EOF.
The two-node fixture reads a prefix of a no-Content-Length response, closes only
capability-session connections and keeps HTTP tunnels/processes/store alive.
The remaining read must reject. Normal EOF, genuine source error and a fresh
session are controls. Stock workerd runs the unchanged normal/source-error program.
Native body.rs tests 1,000 pending-stream disconnects, exactly-once source drop,
normal complete EOF and terminal source errors. Include via capability_http.rs.
The session adapter did not exist at def239b; that baseline is a control, not a
claim that this post-baseline defect was present before session accounting.
