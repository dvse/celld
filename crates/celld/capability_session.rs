// Copyright 2026 Deno Land Inc. Apache-2.0 license.
//! Connection-owned capability references. A session never reconnects: a new
//! connection is a new owner, and cannot revive clients from the old one.
#![allow(clippy::disallowed_methods)]
use crate::capability::{Request, Route};
use anyhow::{Context, Result};
use std::{
    collections::HashMap,
    sync::{Arc, Mutex, OnceLock},
};
static EXECUTOR: OnceLock<tokio::runtime::Handle> = OnceLock::new();
pub fn initialize() {
    let _ = EXECUTOR.set(tokio::runtime::Handle::current());
}
fn spawn(f: impl std::future::Future<Output = ()> + Send + 'static) {
    if let Some(handle) = EXECUTOR.get() {
        handle.spawn(f);
    }
}
pub const PATH: &str = "/peer/capability-session";
pub const HEADER: &str = "x-cells-capability-session";
pub const CALL_HEADER: &str = "x-cells-capability-call";
#[derive(serde::Serialize, serde::Deserialize, Debug)]
#[serde(tag = "kind", deny_unknown_fields)]
enum Control {
    Ping,
    Open {
        id: String,
    },
    Opened {
        id: String,
    },
    Received {
        id: String,
    },
    Finish {
        id: String,
        received: bool,
    },
    Settled {
        id: String,
        received: bool,
    },
    Release {
        route: Route,
    },
    /// A caller proves that one ordered call never reached this process.
    Skip {
        route: Route,
        order: crate::capability::CallOrder,
    },
}
#[derive(Default)]
struct Transfer {
    initiated: bool,
    closing: bool,
    received: bool,
    peer_received: bool,
    bound: bool,
    pending: Vec<Route>,
    opened: Option<tokio::sync::oneshot::Sender<()>>,
}
/// A call's receiving half is closed before asking the authenticated peer to
/// settle its sending half. This guard survives response-body collection.
#[derive(Clone)]
pub struct Call(Arc<CallOwner>);
struct CallOwner {
    session: Arc<Session>,
    id: String,
}
impl Call {
    pub fn id(&self) -> &str {
        &self.0.id
    }
    pub fn session(&self) -> &Arc<Session> {
        &self.0.session
    }
}
impl Drop for CallOwner {
    fn drop(&mut self) {
        self.session.finish(&self.id);
    }
}
#[derive(serde::Serialize, serde::Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Hello {
    pub id: String,
    pub process: String,
}
struct State {
    closed: bool,
    exports: HashMap<String, (Route, usize)>,
    calls: HashMap<String, Transfer>,
}
pub struct Session {
    pub id: String,
    pub peer: String,
    pub process: String,
    state: Mutex<State>,
    closed: tokio::sync::watch::Sender<bool>,
    changed: tokio::sync::watch::Sender<u64>,
    control: tokio::sync::mpsc::UnboundedSender<Control>,
    receive_control: Mutex<Option<tokio::sync::mpsc::UnboundedReceiver<Control>>>,
}
static SESSIONS: OnceLock<Mutex<HashMap<String, Arc<Session>>>> = OnceLock::new();
type SessionDials = HashMap<String, Arc<tokio::sync::Mutex<Option<String>>>>;
static DIALS: OnceLock<Mutex<SessionDials>> = OnceLock::new();
fn sessions() -> &'static Mutex<HashMap<String, Arc<Session>>> {
    SESSIONS.get_or_init(Default::default)
}
impl Session {
    pub fn register(id: String, peer: String, process: String) -> Result<Arc<Self>> {
        anyhow::ensure!(
            id.len() == 64 && id.bytes().all(|b| b.is_ascii_hexdigit()),
            "invalid capability session"
        );
        anyhow::ensure!(process.len() == 64, "invalid capability process");
        let mut table = sessions().lock().unwrap();
        anyhow::ensure!(
            !table.contains_key(&id),
            "capability session already exists"
        );
        let (control, receive_control) = tokio::sync::mpsc::unbounded_channel();
        let s = Arc::new(Self {
            id: id.clone(),
            peer,
            process,
            state: Mutex::new(State {
                closed: false,
                exports: HashMap::new(),
                calls: HashMap::new(),
            }),
            closed: tokio::sync::watch::channel(false).0,
            changed: tokio::sync::watch::channel(0).0,
            control,
            receive_control: Mutex::new(Some(receive_control)),
        });
        table.insert(id, s.clone());
        Ok(s)
    }
    pub fn get(id: &str) -> Result<Arc<Self>> {
        let s = sessions()
            .lock()
            .unwrap()
            .get(id)
            .cloned()
            .context("capability session is gone")?;
        anyhow::ensure!(
            !s.state.lock().unwrap().closed,
            "capability session disconnected"
        );
        Ok(s)
    }
    pub fn authenticated(id: &str, peer: &str) -> Result<Arc<Self>> {
        let s = Self::get(id)?;
        anyhow::ensure!(s.peer == peer, "capability session belongs to another peer");
        Ok(s)
    }
    pub async fn disconnected(&self) {
        let mut changed = self.closed.subscribe();
        while !*changed.borrow_and_update() {
            if changed.changed().await.is_err() {
                break;
            }
        }
    }
    pub async fn open(self: &Arc<Self>) -> Result<Call> {
        let id = crate::capability::random_id();
        let (send, receive) = tokio::sync::oneshot::channel();
        {
            let mut state = self.state.lock().unwrap();
            anyhow::ensure!(!state.closed, "capability session disconnected");
            state.calls.insert(
                id.clone(),
                Transfer {
                    initiated: true,
                    opened: Some(send),
                    ..Default::default()
                },
            );
            self.control.send(Control::Open { id: id.clone() })?;
        }
        // Construct before awaiting: cancellation during setup also settles.
        let call = Call(Arc::new(CallOwner {
            session: self.clone(),
            id,
        }));
        crate::asyncrt::select! {
            result = receive => result.context("RPC transfer setup disconnected")?,
            _ = self.disconnected() => anyhow::bail!("RPC transfer setup disconnected"),
        }
        Ok(call)
    }
    fn finish(&self, id: &str) {
        let mut state = self.state.lock().unwrap();
        if let Some(call) = state.calls.get_mut(id) {
            if call.closing {
                return;
            }
            call.closing = true;
            let _ = self.control.send(Control::Finish {
                id: id.into(),
                received: call.received,
            });
        }
    }
    pub fn accept_call(&self, id: &str) -> Result<()> {
        let state = self.state.lock().unwrap();
        anyhow::ensure!(
            !state.closed && state.calls.get(id).is_some_and(|c| !c.closing),
            "RPC transfer is not open"
        );
        Ok(())
    }
    pub async fn call_closed(&self, id: &str) {
        let mut changed = self.changed.subscribe();
        loop {
            changed.borrow_and_update();
            if self.accept_call(id).is_err() {
                break;
            }
            if changed.changed().await.is_err() {
                break;
            }
        }
    }
    pub fn received(&self, id: &str) -> Result<()> {
        let mut state = self.state.lock().unwrap();
        anyhow::ensure!(!state.closed, "RPC transfer session disconnected");
        let call = state.calls.get_mut(id).context("RPC transfer is gone")?;
        anyhow::ensure!(
            !call.closing && !call.received,
            "RPC transfer already consumed or canceled"
        );
        call.received = true;
        // Ordered with Release on this same authenticated connection. Once
        // this is queued, a native packet owner must release an unread value.
        self.control.send(Control::Received { id: id.into() })?;
        Ok(())
    }
    pub fn release_peer(&self, route: Route) -> Result<()> {
        let state = self.state.lock().unwrap();
        anyhow::ensure!(!state.closed, "RPC release session disconnected");
        self.control.send(Control::Release { route })?;
        Ok(())
    }
    fn settle(&self, call: Transfer, received: bool) {
        if received || call.peer_received {
            return;
        }
        for route in call.pending {
            if self.release(&route) {
                release_local(route);
            }
        }
    }
    fn on_control(&self, message: Control) -> Result<()> {
        let mut state = self.state.lock().unwrap();
        anyhow::ensure!(!state.closed, "RPC control after disconnect");
        match message {
            Control::Ping => {}
            Control::Open { id } => {
                anyhow::ensure!(
                    id.len() == 64
                        && id.bytes().all(|b| b.is_ascii_hexdigit())
                        && !state.calls.contains_key(&id),
                    "invalid RPC transfer id"
                );
                state.calls.insert(id.clone(), Transfer::default());
                self.control.send(Control::Opened { id })?;
            }
            Control::Opened { id } => {
                if let Some(call) = state.calls.get_mut(&id) {
                    anyhow::ensure!(call.initiated, "unsolicited RPC transfer acknowledgement");
                    if let Some(opened) = call.opened.take() {
                        let _ = opened.send(());
                    }
                }
            }
            Control::Received { id } => {
                if let Some(call) = state.calls.get_mut(&id) {
                    call.peer_received = true;
                    call.pending.clear();
                }
            }
            Control::Finish { id, received } => {
                if let Some(call) = state.calls.remove(&id) {
                    anyhow::ensure!(!call.initiated, "wrong RPC transfer finisher");
                    self.control.send(Control::Settled {
                        id,
                        received: call.received,
                    })?;
                    drop(state);
                    self.settle(call, received);
                }
            }
            Control::Settled { id, received } => {
                if let Some(call) = state.calls.remove(&id) {
                    anyhow::ensure!(
                        call.initiated && call.closing,
                        "unsolicited RPC transfer settlement"
                    );
                    drop(state);
                    self.settle(call, received);
                }
            }
            Control::Release { route } => {
                drop(state);
                if self.release(&route) {
                    release_local(route);
                }
            }
            Control::Skip { route, order } => {
                drop(state);
                crate::capability::skip_order(&route, &order, Some(&self.id));
            }
        }
        self.changed.send_modify(|n| *n = n.wrapping_add(1));
        Ok(())
    }
    pub fn bind(&self, id: &str, routes: &[Route]) -> Result<()> {
        let mut state = self.state.lock().unwrap();
        anyhow::ensure!(
            !state.closed,
            "capability session disconnected before transfer"
        );
        let call = state.calls.get_mut(id).context("RPC transfer is gone")?;
        anyhow::ensure!(
            !call.closing && !call.bound,
            "RPC transfer closed or already bound"
        );
        for route in routes {
            crate::capability::preflight(route)?;
        }
        let call = state.calls.get_mut(id).unwrap();
        call.bound = true;
        call.pending = routes.to_vec();
        for route in routes {
            state
                .exports
                .entry(route.token.clone())
                .or_insert_with(|| (route.clone(), 0))
                .1 += 1;
        }
        Ok(())
    }
    /// Consume before dispatch, so EOF and explicit release cannot both own it.
    pub fn release(&self, route: &Route) -> bool {
        let mut state = self.state.lock().unwrap();
        let Some((stored, n)) = state.exports.get_mut(&route.token) else {
            return false;
        };
        if stored != route {
            return false;
        }
        *n -= 1;
        if *n == 0 {
            state.exports.remove(&route.token);
        }
        true
    }
    pub fn contains(&self, route: &Route) -> bool {
        let state = self.state.lock().unwrap();
        !state.closed
            && state
                .exports
                .get(&route.token)
                .is_some_and(|(r, n)| r == route && *n > 0)
    }
    pub fn close(&self) {
        let exports = {
            let mut s = self.state.lock().unwrap();
            if s.closed {
                return;
            }
            s.closed = true;
            s.calls.clear();
            std::mem::take(&mut s.exports)
        };
        self.closed.send_replace(true);
        self.changed.send_modify(|n| *n = n.wrapping_add(1));
        sessions().lock().unwrap().remove(&self.id);
        crate::capability::close_session_lanes(&self.id);
        let count: usize = exports.values().map(|(_, n)| n).sum();
        tracing::debug!(event="capability_session_closed",peer=%self.peer,references=count,"releasing disconnected session");
        for (_, (route, n)) in exports {
            for _ in 0..n {
                release_local(route.clone());
            }
        }
    }
    pub async fn watch<S: tokio::io::AsyncRead + tokio::io::AsyncWrite + Unpin>(&self, stream: S) {
        use tokio::io::{AsyncBufReadExt, AsyncWriteExt};
        let (reader, mut writer) = tokio::io::split(stream);
        let mut lines = tokio::io::BufReader::new(reader).lines();
        let Some(mut controls) = self.receive_control.lock().unwrap().take() else {
            self.close();
            return;
        };
        let read = async {
            while let Ok(Some(line)) = lines.next_line().await {
                if line.len() > 1024 * 1024 {
                    break;
                }
                match serde_json::from_str(&line) {
                    Ok(message) => {
                        if self.on_control(message).is_err() {
                            break;
                        }
                    }
                    _ => break,
                }
            }
        };
        let write = async {
            loop {
                let message = crate::asyncrt::select! {
                    message = controls.recv() => match message { Some(message) => message, None => break },
                    _ = tokio::time::sleep(std::time::Duration::from_secs(10)) => Control::Ping,
                };
                let Ok(mut bytes) = serde_json::to_vec(&message) else {
                    break;
                };
                bytes.push(b'\n');
                if writer.write_all(&bytes).await.is_err() {
                    break;
                }
            }
        };
        // No handler deadline. EOF/keepalive failure revokes the session.
        crate::asyncrt::select! { _ = read => {}, _ = write => {}, _ = self.disconnected() => {} }
        self.close();
    }
}
pub fn release_local(route: Route) {
    spawn(async move {
        let _ = crate::capability::call(Request {
            route,
            order: None,
            path: vec![],
            args: None,
            release: true,
            session: None,
            transfer: None,
            prepared_wire: None,
        })
        .await;
    });
}
/// Resolve an undelivered ordered call at its remote callee. Ordered behind
/// every earlier control message on this authenticated connection. A closed
/// session needs no notice: the callee fails that session's lanes itself.
pub fn skip_remote(route: Route, order: crate::capability::CallOrder, session: &str) {
    if let Ok(session) = Session::get(session) {
        if !session.state.lock().unwrap().closed {
            let _ = session.control.send(Control::Skip { route, order });
        }
    }
}
pub fn release_remote(route: Route, session: String) {
    if let Ok(session) = Session::get(&session) {
        let _ = session.release_peer(route);
    }
}
pub async fn connect(
    http: &reqwest::Client,
    auth: &crate::peer_auth::PeerAuth,
    addr: &str,
    node: &str,
) -> Result<Arc<Session>> {
    let key = format!("{node}@{addr}");
    let gate = DIALS
        .get_or_init(Default::default)
        .lock()
        .unwrap()
        .entry(key)
        .or_default()
        .clone();
    let mut dial = gate.lock().await;
    if let Some(id) = dial.as_ref() {
        if let Ok(s) = Session::get(id) {
            return Ok(s);
        }
    }
    let hello = Hello {
        id: crate::capability::random_id(),
        process: crate::capability::process().into(),
    };
    let body = serde_json::to_vec(&hello)?;
    let response = auth
        .sign(
            http.post(format!("http://{addr}{PATH}"))
                .header("upgrade", "celld-capability-session")
                .header("connection", "upgrade"),
            "POST",
            PATH,
            &body,
            node,
        )?
        .body(body)
        .send()
        .await?;
    crate::peer_auth::validate_response(response.headers())?;
    anyhow::ensure!(
        response.status() == reqwest::StatusCode::SWITCHING_PROTOCOLS,
        "capability session upgrade refused"
    );
    let process = response
        .headers()
        .get("x-cells-capability-process")
        .context("missing peer process")?
        .to_str()?
        .to_string();
    let stream = response.upgrade().await?;
    let s = Session::register(hello.id, node.into(), process)?;
    let watching = s.clone();
    tokio::spawn(async move {
        watching.watch(stream).await;
    });
    *dial = Some(s.id.clone());
    Ok(s)
}

#[cfg(test)]
mod tests {
    use super::*;
    fn route() -> Route {
        Route {
            node: "source".into(),
            addr: "127.0.0.1:9700".into(),
            process: "p".repeat(64),
            heap: "h".into(),
            token: "t".into(),
            seal: "s".into(),
            owner_scope: None,
            storage_scope: None,
            epoch: None,
        }
    }
    #[test]
    fn release_is_counted_and_cannot_consume_another_sessions_alias() {
        let a = Session::register(
            crate::capability::random_id(),
            "peer-a".into(),
            "a".repeat(64),
        )
        .unwrap();
        let b = Session::register(
            crate::capability::random_id(),
            "peer-b".into(),
            "b".repeat(64),
        )
        .unwrap();
        let r = route();
        a.state
            .lock()
            .unwrap()
            .exports
            .insert(r.token.clone(), (r.clone(), 2));
        b.state
            .lock()
            .unwrap()
            .exports
            .insert(r.token.clone(), (r.clone(), 1));
        assert!(a.release(&r));
        assert!(a.contains(&r));
        assert!(a.release(&r));
        assert!(!a.release(&r));
        assert!(b.contains(&r));
        assert!(b.release(&r));
        a.close();
        b.close();
        assert!(Session::get(&a.id).is_err());
    }
    #[test]
    fn authenticated_peer_cannot_borrow_another_session() {
        let a = Session::register(
            crate::capability::random_id(),
            "peer-a".into(),
            "a".repeat(64),
        )
        .unwrap();
        assert!(Session::authenticated(&a.id, "peer-b").is_err());
        assert!(Session::authenticated(&a.id, "peer-a").is_ok());
        a.close();
        assert!(Session::authenticated(&a.id, "peer-a").is_err());
    }
}

#[cfg(test)]
#[path = "../../tests/regressions/R6-04/native.rs"]
mod transfer_regressions;
