// Copyright 2026 Deno Land Inc. Apache-2.0 license.
//! HTTP half of restored/live Fetcher capabilities. Never an RPC member walk.
use super::*;
use base64::Engine as _;
use futures_util::TryStreamExt;
use hyper::service::service_fn;
use std::convert::Infallible;
const CONTROL: &str = "x-cells-capability-http";
const ERROR: &str = "x-cells-capability-http-error";
const MAX_CONTROL: usize = 8 * 1024 * 1024;
pub(super) async fn fetch(
    app: &AppHandle,
    mut call: celld::capability::Fetch,
) -> anyhow::Result<HttpResponse> {
    celld::capability::verify_peer_route(&call.control.route)?;
    let session = celld::capability_session::Session::get(
        call.control
            .session
            .as_deref()
            .context("live HTTP capability has no session")?,
    )?;
    anyhow::ensure!(
        session.peer == call.control.route.node && session.process == call.control.route.process,
        "HTTP capability session owner changed"
    );
    complete_websocket_handshake(&mut call.headers);
    tracing::debug!(event = "capability_http_peer", node = %call.control.route.node, "dispatch live HTTP channel");
    let route = &call.control.route;
    let control = serde_json::to_vec(&call.control)?;
    anyhow::ensure!(
        control.len() <= MAX_CONTROL,
        "capability HTTP control too large"
    );
    let control = base64::engine::general_purpose::STANDARD.encode(control);
    let mut response = peer_tunnel::send_inner(
        &peer_tunnel::Peer {
            http: &app.peer_http,
            auth: &app.peer_auth,
            addr: &route.addr,
            node: &route.node,
        },
        "capability-http",
        |body| {
            let mut request = Request::builder()
                .method(call.method.as_str())
                .uri(call.url.as_str());
            for (name, value) in &call.headers {
                if name.eq_ignore_ascii_case(CONTROL)
                    || name.eq_ignore_ascii_case("content-length")
                    || name.eq_ignore_ascii_case("transfer-encoding")
                {
                    continue;
                }
                request = request.header(name, value);
            }
            Ok(request.header(CONTROL, &control).body(body)?)
        },
        call.body,
    )
    .await?;
    if response.headers().contains_key(ERROR) {
        let body = http_body_util::Limited::new(response.into_body(), MAX_PEER_CONTROL_BODY_BYTES)
            .collect()
            .await
            .map_err(|error| anyhow::anyhow!("capability error body: {error}"))?
            .to_bytes();
        anyhow::bail!(
            "capability HTTP owner failed: {}",
            String::from_utf8_lossy(&body)
        );
    }
    let status = response.status().as_u16();
    let headers = response
        .headers()
        .iter()
        .filter(|(key, _)| {
            status != 101
                || !matches!(
                    key.as_str(),
                    "upgrade" | "connection" | "sec-websocket-accept"
                )
        })
        .filter_map(|(name, value)| {
            value
                .to_str()
                .ok()
                .map(|value| (name.to_string(), value.to_string()))
        })
        .collect();
    if status == 101 {
        let parked = peer_tunnel::park_upgrade(hyper::upgrade::on(&mut response));
        return Ok(HttpResponse {
            status,
            headers,
            body: Vec::new(),
            stream: None,
            websocket: Some(HttpResponseWebSocket::Cell(celld::js::WsTarget {
                id: 0,
                scope: route.owner_scope.clone().unwrap_or_default(),
                tunnel: Some(parked),
            })),
            write_position: None,
            observed_position: None,
        });
    }
    Ok(HttpResponse {
        status,
        headers,
        body: Vec::new(),
        websocket: None,
        stream: Some(peer_tunnel::response_stream(response.into_body())),
        write_position: None,
        observed_position: None,
    })
}
pub(super) async fn serve(upgraded: hyper::upgrade::Upgraded, app: AppHandle, source: String) {
    let service = service_fn(move |mut inner: Request<Incoming>| {
        let app = app.clone();
        let source = source.clone();
        async move {
            let control = inner.headers_mut().remove(CONTROL).and_then(|value| {
                if value.as_bytes().len() > MAX_CONTROL * 2 {
                    return None;
                }
                let bytes = base64::engine::general_purpose::STANDARD
                    .decode(value.as_bytes())
                    .ok()?;
                serde_json::from_slice::<celld::capability::FetchControl>(&bytes).ok()
            });
            let Some(control) =
                control.filter(|control| celld::capability::local_route(&control.route))
            else {
                return Ok::<_, Infallible>(peer_response(response(
                    StatusCode::BAD_REQUEST,
                    "invalid capability HTTP control",
                )));
            };
            let session = control
                .session
                .as_deref()
                .and_then(|id| celld::capability_session::Session::authenticated(id, &source).ok());
            let Some(session) = session.filter(|s| s.contains(&control.route)) else {
                return Ok(peer_response(response(
                    StatusCode::GONE,
                    "HTTP capability session disconnected",
                )));
            };
            // Keyed by the authenticated session; every later answer carries
            // the resolution header (see capability::ORDER_RESOLVED_HEADER).
            let _slot = celld::capability::OrderSlot::new(
                &control.route,
                control.order.as_ref(),
                Some(&session.id),
            );
            let upgrade = if fastwebsockets::upgrade::is_upgrade_request(&inner) {
                match fastwebsockets::upgrade::upgrade(&mut inner) {
                    Ok(pair) => Some(pair),
                    Err(_) => {
                        return Ok(peer_response(response(
                            StatusCode::BAD_REQUEST,
                            "invalid upgrade",
                        )))
                    }
                }
            } else {
                None
            };
            let (parts, body) = inner.into_parts();
            let head = parts.method == hyper::Method::HEAD;
            let chunks: celld::js::HttpChunkStream = Box::pin(
                http_body_util::BodyStream::new(http_body_util::Limited::new(
                    body,
                    MAX_PEER_FORWARD_BODY_BYTES,
                ))
                .try_filter_map(|frame| async move { Ok(frame.into_data().ok()) })
                .map_ok(|bytes: Bytes| bytes.to_vec())
                .map_err(|error| error.to_string()),
            );
            let stream = match celld::js::register_body_stream(chunks) {
                Ok(id) => id,
                Err(error) => {
                    return Ok(peer_response(response(
                        StatusCode::SERVICE_UNAVAILABLE,
                        error,
                    )))
                }
            };
            let body = celld::js::RequestBody::Stream(stream);
            let _body_guard = celld::js::RequestBodyGuard::of(&body);
            let call = celld::capability::Fetch {
                control,
                url: parts.uri.to_string(),
                method: parts.method.to_string(),
                body,
                headers: parts
                    .headers
                    .iter()
                    .filter_map(|(name, value)| {
                        value
                            .to_str()
                            .ok()
                            .map(|value| (name.to_string(), value.to_string()))
                    })
                    .collect(),
            };
            let result = tokio::select! {
                result=dispatch_capability_fetch(app.clone(),call)=>result,
                _=session.disconnected()=>Err(anyhow::anyhow!("HTTP capability holder disconnected")),
            };
            let result=result.map(|mut response| {
                if let Some(stream)=response.stream.take() {
                    response.stream = Some(disconnect_body(stream, async move {
                        session.disconnected().await;
                    }));
                }
                response
            });
            let mut answer = match result {
                Ok(response) => {
                    let mut answer = websocket::reply_to_tunnel(app, response, upgrade, head).await;
                    answer.headers_mut().remove(ERROR);
                    answer
                }
                Err(error) => {
                    let mut answer =
                        response(StatusCode::INTERNAL_SERVER_ERROR, format!("{error:#}"));
                    answer
                        .headers_mut()
                        .insert(ERROR, hyper::header::HeaderValue::from_static("1"));
                    answer
                }
            };
            answer.headers_mut().insert(
                hyper::header::HeaderName::from_static(celld::capability::ORDER_RESOLVED_HEADER),
                hyper::header::HeaderValue::from_static("1"),
            );
            Ok(peer_response(answer))
        }
    });
    let _ = hyper::server::conn::http1::Builder::new()
        .max_buf_size(MAX_CONTROL * 2)
        .serve_connection(upgraded, service)
        .with_upgrades()
        .await;
}

// Losing the control session is a body error, never successful EOF. Drop the
// source immediately on either failure; the terminal state cannot emit twice.
fn disconnect_body(
    stream: celld::js::HttpChunkStream,
    disconnected: impl std::future::Future<Output = ()> + Send + 'static,
) -> celld::js::HttpChunkStream {
    Box::pin(futures_util::stream::unfold(
        Some((stream, Box::pin(disconnected))),
        |state| async move {
            use futures_util::StreamExt;
            let (mut stream, mut disconnected) = state?;
            tokio::select! {
                item = stream.next() => match item {
                    Some(Ok(chunk)) => Some((Ok(chunk), Some((stream, disconnected)))),
                    Some(Err(error)) => Some((Err(error), None)),
                    None => None,
                },
                _ = &mut disconnected => Some((
                    Err("HTTP capability holder disconnected during response body".into()), None)),
            }
        },
    ))
}
#[cfg(test)]
#[path = "../../../tests/regressions/R9-07/body.rs"]
mod body_tests;
