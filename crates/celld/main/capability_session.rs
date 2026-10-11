// Copyright 2026 Deno Land Inc. Apache-2.0 license.
use super::*;
use celld::capability_session::{self as sessions, Hello, Session};
pub(super) async fn accept(mut request: Request<Incoming>, app: AppHandle) -> HttpReply {
    let upgrade = hyper::upgrade::on(&mut request);
    let (parts, body) = request.into_parts();
    let body = match collect_limited_body(body, 4096).await {
        Ok(body) => body,
        Err(error) => return peer_response(body_read_error("capability session", error)),
    };
    if let Err(error) = app.peer_auth.verify(
        &parts.method,
        sessions::PATH,
        &parts.headers,
        &body,
        app.peer_auth.source(),
    ) {
        return peer_response(response(error.status(), error.message()));
    }
    let result = (|| -> anyhow::Result<_> {
        anyhow::ensure!(parts.method == hyper::Method::POST, "session requires POST");
        let peer = parts
            .headers
            .get("x-cells-peer-source")
            .context("missing authenticated source")?
            .to_str()?;
        let hello: Hello = serde_json::from_slice(&body)?;
        Session::register(hello.id, peer.into(), hello.process)
    })();
    let session = match result {
        Ok(s) => s,
        Err(error) => {
            return peer_response(response(StatusCode::BAD_REQUEST, format!("{error:#}")))
        }
    };
    tokio::spawn(async move {
        match upgrade.await {
            Ok(stream) => session.watch(TokioIo::new(stream)).await,
            Err(_) => session.close(),
        }
    });
    let mut reply = response(StatusCode::SWITCHING_PROTOCOLS, "");
    reply.headers_mut().insert(
        "upgrade",
        hyper::header::HeaderValue::from_static("celld-capability-session"),
    );
    reply.headers_mut().insert(
        "connection",
        hyper::header::HeaderValue::from_static("upgrade"),
    );
    reply.headers_mut().insert(
        "x-cells-capability-process",
        celld::capability::process().parse().unwrap(),
    );
    peer_response(reply)
}
