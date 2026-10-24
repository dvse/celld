// Copyright 2026 Deno Land Inc. Apache-2.0 license.
// Native network/heap adapter, outside the deterministic Actor execution domain.
#![allow(clippy::disallowed_methods)]
//! Live capability transport. A reference addresses one heap incarnation, never
//! a placement hint. Actor migration invalidates it; restoration is separate.
use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    future::Future,
    pin::Pin,
    sync::{Arc, Mutex, OnceLock, Weak},
};

pub const ENTRYPOINT: &str = "\0celld-capability-v1";
pub const RELEASE_ENTRYPOINT: &str = "\0celld-capability-release-v1";
pub const PATH: &str = "/peer/capability";
const TIMEOUT: std::time::Duration = std::time::Duration::from_secs(60);
const MAX_WIRE_BYTES: usize = 16 * 1024 * 1024;

pub const NOT_EXECUTED_HEADER: &str = "x-celld-capability-not-executed";
const NOT_EXECUTED_PREFIX: &str = "__CELLD_CAPABILITY_NOT_EXECUTED__:";
/// A host proof that this particular operation never entered target JS.
/// It must never be constructed from a handler exception or response body.
#[derive(Debug)]
struct NotExecuted(String);
impl std::fmt::Display for NotExecuted {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.0)
    }
}
impl std::error::Error for NotExecuted {}
pub fn not_executed(error: impl std::fmt::Display) -> anyhow::Error {
    anyhow::Error::new(NotExecuted(error.to_string()))
}
pub fn was_not_executed(error: &anyhow::Error) -> bool {
    error.downcast_ref::<NotExecuted>().is_some()
}
pub(crate) fn op_failure(error: anyhow::Error) -> String {
    if was_not_executed(&error) {
        format!("{NOT_EXECUTED_PREFIX}{error:#}")
    } else {
        format!("capability call failed: {error:#}")
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Route {
    pub node: String,
    pub addr: String,
    pub process: String,
    pub heap: String,
    pub token: String,
    pub seal: String,
    pub owner_scope: Option<String>,
    pub storage_scope: Option<String>,
    pub epoch: Option<u64>,
}
#[derive(Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Request {
    pub route: Route,
    #[serde(default)]
    pub order: Option<CallOrder>,
    pub path: Vec<String>,
    pub args: Option<Vec<u8>>,
    pub release: bool,
    #[serde(skip)]
    pub prepared_wire: Option<Vec<u8>>,
}
// Prepare before enqueue so a local serialization/size rejection does not
// consume an ordered channel sequence. Reuse the exact bytes for HTTP.
pub(crate) fn prepare_request(request: &mut Request) -> Result<()> {
    let body = serde_json::to_vec(request)?;
    anyhow::ensure!(body.len() <= MAX_WIRE_BYTES, "capability payload too large");
    request.prepared_wire = Some(body);
    Ok(())
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CallOrder {
    pub lane: String,
    pub sequence: u64,
}
#[derive(Default)]
struct OrderState {
    next: u64,
    active: bool,
    broken: bool,
}
#[derive(Default)]
struct OrderLane {
    state: Mutex<OrderState>,
    changed: tokio::sync::Notify,
}
struct OrderPermit(Arc<OrderLane>);
impl Drop for OrderPermit {
    fn drop(&mut self) {
        let mut state = self.0.state.lock().unwrap();
        state.active = false;
        state.next += 1;
        drop(state);
        self.0.changed.notify_waiters();
    }
}
struct Export {
    route: Route,
    lanes: HashMap<String, Arc<OrderLane>>,
    slot: Weak<crate::pool::Slot>,
    token: String,
}
static EXPORTS: OnceLock<Mutex<HashMap<String, Export>>> = OnceLock::new();
fn exports() -> &'static Mutex<HashMap<String, Export>> {
    EXPORTS.get_or_init(Default::default)
}
fn random_id() -> String {
    let mut bytes = [0; 32];
    getrandom::fill(&mut bytes).expect("OS random source unavailable");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
fn process() -> &'static str {
    static ID: OnceLock<String> = OnceLock::new();
    ID.get_or_init(random_id)
}
pub type Dispatch =
    Arc<dyn Fn(Request) -> Pin<Box<dyn Future<Output = Result<Vec<u8>>> + Send>> + Send + Sync>;
struct Transport {
    node: String,
    addr: String,
    http: reqwest::Client,
    auth: Arc<crate::peer_auth::PeerAuth>,
    dispatch: Dispatch,
}
static TRANSPORT: OnceLock<Transport> = OnceLock::new();
pub(crate) fn peer_auth() -> Option<Arc<crate::peer_auth::PeerAuth>> {
    TRANSPORT.get().map(|transport| transport.auth.clone())
}

pub(crate) fn configured() -> bool {
    TRANSPORT.get().is_some()
}
pub fn configure(
    node: String,
    addr: String,
    http: reqwest::Client,
    auth: Arc<crate::peer_auth::PeerAuth>,
    dispatch: Dispatch,
) {
    assert!(
        TRANSPORT
            .set(Transport {
                node,
                addr,
                http,
                auth,
                dispatch
            })
            .is_ok(),
        "capability transport already configured"
    );
}

pub(crate) fn export(
    slot: Arc<crate::pool::Slot>,
    token: String,
    storage_scope: Option<String>,
    owner_scope: Option<String>,
    epoch: Option<u64>,
) -> Result<String> {
    let transport = TRANSPORT.get();
    let mut route = Route {
        node: transport.map(|t| t.node.clone()).unwrap_or_default(),
        addr: transport.map(|t| t.addr.clone()).unwrap_or_default(),
        process: process().into(),
        heap: slot.heap_id().to_string(),
        token: random_id(),
        seal: String::new(),
        owner_scope,
        storage_scope,
        epoch,
    };
    if let Some(transport) = transport {
        route.seal = transport.auth.seal_capability(&serde_json::to_vec(&route)?);
    }
    let mut entries = exports().lock().unwrap();
    entries.retain(|_, entry| entry.slot.strong_count() > 0);
    anyhow::ensure!(
        entries.len() < 100_000,
        "live capability export limit reached"
    );
    tracing::debug!(event = "capability_export", node = %route.node, process = %route.process, heap = %route.heap, scope = ?route.owner_scope, "exported live capability");
    entries.insert(
        route.token.clone(),
        Export {
            route: route.clone(),
            lanes: HashMap::new(),
            slot: Arc::downgrade(&slot),
            token,
        },
    );
    Ok(serde_json::to_string(&route)?)
}
/// Called again inside the isolate, after acquiring its turn. The bearer and
/// exact heap are checked here too; a reserved RPC entrypoint is not authority.
pub(crate) fn validate(route: &Route) -> Result<String> {
    validate_before_dispatch(route).map_err(not_executed)
}
fn validate_before_dispatch(route: &Route) -> Result<String> {
    anyhow::ensure!(
        route.process == process(),
        "capability owner process is gone"
    );
    let entries = exports().lock().unwrap();
    let entry = entries
        .get(&route.token)
        .context("capability released or owner gone")?;
    anyhow::ensure!(&entry.route == route, "invalid capability route");
    let slot = crate::pool::current_slot().context("capability dispatched outside isolate")?;
    anyhow::ensure!(
        slot.heap_id().to_string() == route.heap,
        "capability heap changed"
    );
    if let Some(scope) = &route.storage_scope {
        anyhow::ensure!(
            crate::storage::activation_epoch(scope) == route.epoch && route.epoch.is_some(),
            "capability actor activation is gone"
        );
    }
    Ok(entry.token.clone())
}
pub(crate) fn revoke(route: &Route) -> Result<()> {
    let slot = crate::pool::current_slot().context("capability revocation outside isolate")?;
    anyhow::ensure!(
        route.process == process() && route.heap == slot.heap_id().to_string(),
        "capability revocation from wrong heap"
    );
    let mut entries = exports().lock().unwrap();
    if let Some(entry) = entries.get(&route.token) {
        anyhow::ensure!(&entry.route == route, "invalid capability revoke route");
        entries.remove(&route.token);
    }
    Ok(())
}

/// Fail before the actor router can perform any work on a supplied scope.
pub fn preflight(route: &Route) -> Result<()> {
    preflight_inner(route).map_err(not_executed)
}
fn preflight_inner(route: &Route) -> Result<()> {
    anyhow::ensure!(
        route.process == process(),
        "capability owner process is gone"
    );
    let entries = exports().lock().unwrap();
    let entry = entries
        .get(&route.token)
        .context("capability released or owner gone")?;
    anyhow::ensure!(&entry.route == route, "invalid capability route");
    anyhow::ensure!(
        entry.slot.strong_count() > 0,
        "capability owner isolate is gone"
    );
    Ok(())
}

// Admission ordering ends when target JS has entered its method, not when
// its promise settles. This preserves e-order without deadlocking callbacks.
async fn ordered_admission(
    route: &Route,
    order: Option<&CallOrder>,
) -> Result<Option<OrderPermit>> {
    let Some(order) = order else {
        return Ok(None);
    };
    anyhow::ensure!(
        !order.lane.is_empty() && order.lane.len() <= 128,
        "invalid capability ordering lane"
    );
    let lane = {
        let mut entries = exports().lock().unwrap();
        let export = entries
            .get_mut(&route.token)
            .ok_or_else(|| not_executed("capability released before ordered admission"))?;
        anyhow::ensure!(&export.route == route, "invalid capability ordering route");
        anyhow::ensure!(
            export.lanes.len() < 4096 || export.lanes.contains_key(&order.lane),
            "capability ordering lane limit reached"
        );
        export.lanes.entry(order.lane.clone()).or_default().clone()
    };
    let waiting = async {
        loop {
            let notified = lane.changed.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            {
                let mut state = lane.state.lock().unwrap();
                anyhow::ensure!(!state.broken, "capability ordering channel is broken");
                if order.sequence < state.next {
                    return Err(anyhow!("capability sequence was already dispatched; execution outcome is ambiguous"));
                }
                anyhow::ensure!(
                    order.sequence.saturating_sub(state.next) <= 4096,
                    "capability sequence gap too large"
                );
                if order.sequence == state.next && !state.active {
                    state.active = true;
                    return Ok(Some(OrderPermit(lane.clone())));
                }
            }
            notified.await;
        }
    };
    match tokio::time::timeout(TIMEOUT, waiting).await {
        Ok(result) => result,
        Err(_) => {
            lane.state.lock().unwrap().broken = true;
            lane.changed.notify_waiters();
            Err(anyhow!(
                "capability ordering channel broke: predecessor did not arrive"
            ))
        }
    }
}
#[derive(Serialize, Deserialize)]
pub(crate) struct Invocation {
    pub route: Route,
    pub started: String,
}
static STARTS: OnceLock<Mutex<HashMap<String, tokio::sync::oneshot::Sender<()>>>> = OnceLock::new();
fn starts() -> &'static Mutex<HashMap<String, tokio::sync::oneshot::Sender<()>>> {
    STARTS.get_or_init(Default::default)
}
pub(crate) fn acknowledge_start(ticket: &str) {
    if let Some(sender) = starts().lock().unwrap().remove(ticket) {
        let _ = sender.send(());
    }
}
struct StartTicket(String);
impl Drop for StartTicket {
    fn drop(&mut self) {
        starts().lock().unwrap().remove(&self.0);
    }
}

struct Running(Option<tokio::task::JoinHandle<()>>);
impl Drop for Running {
    fn drop(&mut self) {
        if let Some(task) = self.0.take() {
            task.abort();
        }
    }
}

pub async fn invoke_local(request: Request) -> Result<Vec<u8>> {
    preflight(&request.route)?;
    let mut permit = ordered_admission(&request.route, request.order.as_ref()).await?;
    let slot = (|| -> Result<_> {
        let entries = exports().lock().unwrap();
        let entry = entries
            .get(&request.route.token)
            .context("capability released or owner gone")?;
        anyhow::ensure!(entry.route == request.route, "invalid capability route");
        entry
            .slot
            .upgrade()
            .context("capability owner isolate is gone")
    })()
    .map_err(not_executed)?;
    // The temporary affiliation closes the retirement race, but exports never
    // pin an isolate between calls or obstruct actor migration.
    let _live = slot
        .try_affiliate()
        .await
        .ok_or_else(|| not_executed("capability owner isolate retired"))?;
    let (reply, mut receive) = tokio::sync::oneshot::channel();
    let ticket = StartTicket(random_id());
    let (start_send, mut start_receive) = tokio::sync::oneshot::channel();
    starts()
        .lock()
        .unwrap()
        .insert(ticket.0.clone(), start_send);
    let invocation = Invocation {
        route: request.route.clone(),
        started: ticket.0.clone(),
    };
    let operation = match request.args {
        Some(args) => crate::WorkerRpcOperation::Call {
            path: request.path,
            args,
        },
        None => crate::WorkerRpcOperation::Get { path: request.path },
    };
    let job = crate::WorkerJob::Rpc {
        entrypoint: if request.release {
            RELEASE_ENTRYPOINT
        } else {
            ENTRYPOINT
        }
        .into(),
        operation,
        props: serde_json::to_vec(&invocation)?,
        invocation_limits: None,
        tail_report: None,
        reply,
    };
    let mut driving = Running(Some(tokio::spawn(crate::runtime::drive(slot, job, None))));
    let completion = async {
        crate::asyncrt::select! {
            _ = &mut start_receive => { permit.take(); receive.await },
            result = &mut receive => { permit.take(); result },
        }
    };
    let result = tokio::time::timeout(TIMEOUT, completion).await;
    match result {
        Ok(Ok(result)) => {
            driving.0.take();
            result
        }
        Ok(Err(_)) => {
            let _ = driving.0.as_mut().unwrap().await;
            Err(anyhow!("capability owner dropped reply"))
        }
        Err(_) => {
            if let Some(task) = driving.0.take() {
                task.abort();
            }
            Err(anyhow!("capability call timed out; it was not retried"))
        }
    }
}

pub async fn call(mut request: Request) -> Result<Vec<u8>> {
    let result = async {
        if request.route.process == process() {
            request.prepared_wire = None;
            return match TRANSPORT.get() {
                Some(transport) => (transport.dispatch)(request).await,
                None => invoke_local(request).await,
            };
        }
        let transport = TRANSPORT
            .get()
            .context("cross-process capability transport unavailable")?;
        let mut unsigned = request.route.clone();
        let seal = std::mem::take(&mut unsigned.seal);
        anyhow::ensure!(
            transport
                .auth
                .verify_capability(&serde_json::to_vec(&unsigned)?, &seal),
            "capability route authentication failed"
        );
        anyhow::ensure!(
            !request.route.addr.is_empty() && !request.route.node.is_empty(),
            "capability owner has no peer route"
        );
        tracing::debug!(event = "capability_peer_call", node = %request.route.node, process = %request.route.process, heap = %request.route.heap, release = request.release, "calling live capability peer");
        let body = match request.prepared_wire.take() {
            Some(body) => body,
            None => serde_json::to_vec(&request)?,
        };
        anyhow::ensure!(body.len() <= MAX_WIRE_BYTES, "capability payload too large");
        let http = transport.auth.sign(
            transport
                .http
                .post(format!("http://{}{}", request.route.addr, PATH)),
            "POST",
            PATH,
            &body,
            &request.route.node,
        )?;
        let mut response = http.body(body).send().await.map_err(|error| {
            if error.is_connect() {
                not_executed(error)
            } else {
                anyhow!("capability owner transport failed: {error}")
            }
        })?;
        crate::peer_auth::validate_response(response.headers())?;
        let status = response.status();
        let not_run = response
            .headers()
            .get(NOT_EXECUTED_HEADER)
            .is_some_and(|v| v == "1");
        anyhow::ensure!(
            response.content_length().unwrap_or(0) <= MAX_WIRE_BYTES as u64,
            "capability reply too large"
        );
        let mut bytes = Vec::new();
        while let Some(chunk) = response.chunk().await? {
            anyhow::ensure!(
                bytes.len().saturating_add(chunk.len()) <= MAX_WIRE_BYTES,
                "capability reply too large"
            );
            bytes.extend_from_slice(&chunk);
        }
        if !status.is_success() {
            let message = format!(
                "capability owner rejected call: {}",
                String::from_utf8_lossy(&bytes)
            );
            return Err(if not_run {
                not_executed(message)
            } else {
                anyhow!(message)
            });
        }
        Ok(bytes.to_vec())
    };
    tokio::time::timeout(TIMEOUT, result)
        .await
        .context("capability call timed out; it was not retried")?
}

#[cfg(test)]
mod not_executed_tests {
    use super::*;

    #[test]
    fn handler_text_cannot_forge_not_executed_proof() {
        let error = anyhow!("{NOT_EXECUTED_PREFIX}application supplied message");
        assert!(!was_not_executed(&error));
        assert!(!op_failure(error).starts_with(NOT_EXECUTED_PREFIX));
        let error = not_executed("owner incarnation no longer exists");
        assert!(was_not_executed(&error));
        assert!(op_failure(error).starts_with(NOT_EXECUTED_PREFIX));
    }

    #[test]
    fn missing_owner_preflight_is_typed_not_executed() {
        let route = Route {
            node: "old-owner".into(),
            addr: "127.0.0.1:1".into(),
            process: "nonexistent-incarnation".into(),
            heap: "1".into(),
            token: "invalid".into(),
            seal: "invalid".into(),
            owner_scope: None,
            storage_scope: None,
            epoch: None,
        };
        assert!(was_not_executed(&preflight(&route).unwrap_err()));
    }
}
