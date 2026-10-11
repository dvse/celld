# C6-03 — edge "read header from client timeout" failures and connection growth

Tunez Celld 6: the edge logged ~23,900 (28,500 by 23:19 AEST)
`http_connection_failures ... read header from client timeout`, all from
127.0.0.1 peers (planets on the internal surface, local clients on the
public one); planet→edge established connections peaked at 324.

Mechanism: celld's HTTP/1 servers close a keep-alive connection that sends
no request head for 30 s (`header_read_timeout`, hyper proto/h1/conn.rs
poll_read_head) and count it as a failure. The peer client kept idle
connections for 20 s, and every subrequest client (reqwest default) for 90 s.
hyper-util evicts idle connections only on an interval equal to the idle
timeout (client/legacy/pool.rs spawn_idle_interval), so a 20 s connection can
stay up to 40 s: every connection a burst opened and that then idled for
30–40 s was closed by the server as a failure (and a request sent on it as it
closed would fail ambiguously). The pool also kept every burst connection
(no per-host idle bound), so bursts of concurrent ordered calls — each call
holds its own HTTP/1 connection, longer while a lane waits — accumulated.

Fix: one keep-alive policy (`machine::pooled_client`) for the peer, log-tier
and subrequest clients: idle 10 s (≤ 20 s with eviction granularity, checked
at compile time against `SERVER_HEADER_READ_TIMEOUT`) and at most 16 idle
connections per host. Burst concurrency is bounded by the calls in flight;
ordering gaps no longer hold connections for 60 s (C6-02).

Before (`ported`, 4 cycles): 202 header timeouts, 153 connections pooled after
each burst. After: 0 timeouts, 35 pooled (16 + 16 + sessions).
