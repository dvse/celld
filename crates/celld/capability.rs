// Copyright 2026 Deno Land Inc. Apache-2.0 license.
// Native network/heap adapter, outside the deterministic Actor execution domain.
#![allow(clippy::disallowed_methods)]
//! Live capability transport. A reference addresses one heap incarnation, never
//! a placement hint. Actor migration invalidates it; restoration is separate.
use anyhow::{anyhow, Context, Result};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeSet, HashMap},
    future::Future,
    pin::Pin,
    sync::{Arc, Mutex, OnceLock, Weak},
};

pub const ENTRYPOINT: &str = "\0celld-capability-v1";
pub const CANCEL_ENTRYPOINT: &str = "\0celld-capability-cancel-v1";
pub const RELEASE_ENTRYPOINT: &str = "\0celld-capability-release-v1";
pub const PATH: &str = "/peer/capability";
/// How long an ordered call waits for a predecessor that never arrived: a gap
/// in a lane is transport loss, not a slow call. Calls themselves have no
/// duration bound, as a workerd JS RPC call has none: one lives as long as
/// its caller and the connection to its owner.
const ORDER_GAP_TIMEOUT: std::time::Duration = std::time::Duration::from_secs(60);
const MAX_WIRE_BYTES: usize = 16 * 1024 * 1024;

pub const NOT_EXECUTED_HEADER: &str = "x-celld-capability-not-executed";
/// Set by a callee on every answer produced after its `OrderSlot` exists. Only
/// such an answer proves the callee resolved the sequence slot; any other
/// answer (authentication, parse or session rejection) leaves resolution to
/// the caller's skip notice, which is idempotent at the callee.
pub const ORDER_RESOLVED_HEADER: &str = "x-celld-order-resolved";
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
    #[serde(with = "optional_bytes")]
    pub args: Option<bytes::Bytes>,
    pub release: bool,
    #[serde(default)]
    pub session: Option<String>,
    #[serde(default)]
    pub transfer: Option<String>,
    #[serde(skip)]
    pub prepared_wire: Option<Vec<u8>>,
}
mod optional_bytes {
    use super::*;
    pub fn serialize<S: serde::Serializer>(
        value: &Option<bytes::Bytes>,
        serializer: S,
    ) -> std::result::Result<S::Ok, S::Error> {
        value.as_ref().map(|b| b.as_ref()).serialize(serializer)
    }
    pub fn deserialize<'de, D: serde::Deserializer<'de>>(
        deserializer: D,
    ) -> std::result::Result<Option<bytes::Bytes>, D::Error> {
        Ok(Option::<Vec<u8>>::deserialize(deserializer)?.map(Into::into))
    }
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
/// One caller lane of an export. Every sequence number a caller assigns is
/// resolved exactly once: by dispatch (the permit), by the callee rejecting
/// the request before admission, or by the caller proving non-delivery with
/// a skip notice on the same authenticated process session. A gap therefore
/// means the caller process or its session is gone, which is reported as the
/// session's loss rather than discovered by a timeout. This is the e-order
/// workerd gets from one Cap'n Proto connection per peer, where a message
/// lost without the connection failing cannot happen (capnp/rpc.c++), and
/// where a broken connection fails every call made through it.
#[derive(Default)]
struct OrderState {
    next: u64,
    active: bool,
    broken: Option<String>,
    /// Resolved without dispatch; ahead of `next` until it reaches them.
    skipped: BTreeSet<u64>,
    /// The process session whose caller owns this lane, if remote.
    session: Option<String>,
}
impl OrderState {
    fn advance(&mut self) {
        while self.skipped.remove(&self.next) {
            self.next += 1;
        }
        // Entries a dispatched or skipped predecessor already passed.
        self.skipped = self.skipped.split_off(&self.next);
    }
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
        state.advance();
        drop(state);
        self.0.changed.notify_waiters();
    }
}
struct Export {
    route: Route,
    lanes: HashMap<String, Arc<OrderLane>>,
    slot: Weak<crate::pool::Slot>,
    token: String,
    /// A stateless heap's claim on its isolate while this export lives. In
    /// workerd a session's IoContext, and with it its Worker, stays alive
    /// until no capability crosses it (api/worker-rpc.c++ CompletionMembrane,
    /// io/io-context.h), so a pool shrink must not free a heap a remote
    /// holder still calls. Actor heaps have no pin: their cell's residency
    /// keeps the heap, and migration invalidates the export instead.
    pin: Option<crate::pool::ExportPin>,
}
static EXPORTS: OnceLock<Mutex<HashMap<String, Export>>> = OnceLock::new();
fn exports() -> &'static Mutex<HashMap<String, Export>> {
    EXPORTS.get_or_init(Default::default)
}
pub(crate) fn random_id() -> String {
    let mut bytes = [0; 32];
    getrandom::fill(&mut bytes).expect("OS random source unavailable");
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}
pub fn process() -> &'static str {
    static ID: OnceLock<String> = OnceLock::new();
    ID.get_or_init(random_id)
}
pub type Dispatch = Arc<
    dyn Fn(Request) -> Pin<Box<dyn Future<Output = Result<bytes::Bytes>> + Send>> + Send + Sync,
>;
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
    crate::capability_session::initialize();
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
    // A heap whose capabilities are closed (generation retirement,
    // condemnation) is never pinned again: every call on the export is
    // refused, and a pin would only keep the old heap from being freed.
    let pin = storage_scope.is_none().then(|| slot.pin_export()).flatten();
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
    retain_live_exports(&mut entries);
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
            pin,
        },
    );
    // Closing stores its flag before `drop_closed_exports` takes this lock:
    // either that pass sees this entry, or this check sees the flag.
    let late_pin = if slot.capabilities_closed() {
        entries.get_mut(&route.token).and_then(|entry| entry.pin.take())
    } else {
        None
    };
    drop(entries);
    drop(late_pin);
    Ok(serde_json::to_string(&route)?)
}
/// An export whose heap is gone can never dispatch again.
fn retain_live_exports(entries: &mut HashMap<String, Export>) {
    entries.retain(|_, entry| {
        let live = entry.slot.strong_count() > 0;
        if !live {
            forget_session_lanes(entry);
        }
        live
    });
}
/// Remove a departing export's lanes from the per-session index. Called with
/// the exports table locked (lock order: exports, then session lanes).
fn forget_session_lanes(export: &Export) {
    let mut index = session_lanes().lock().unwrap();
    for (name, lane) in &export.lanes {
        let Some(session) = lane.state.lock().unwrap().session.clone() else {
            continue;
        };
        if let Some(owned) = index.get_mut(&session) {
            owned.retain(|(token, lane)| !(token == &export.route.token && lane == name));
            if owned.is_empty() {
                index.remove(&session);
            }
        }
    }
}
/// A closed heap dispatches no capability again: release the pins its exports
/// hold, so it can be freed once drained. The entries stay until the heap is
/// gone, so a late call still learns that its owner was invalidated.
pub(crate) fn drop_closed_exports() {
    let released: Vec<crate::pool::ExportPin> = {
        let mut entries = exports().lock().unwrap();
        entries
            .values_mut()
            .filter(|entry| {
                !entry
                    .slot
                    .upgrade()
                    .is_some_and(|slot| !slot.capabilities_closed())
            })
            .filter_map(|entry| entry.pin.take())
            .collect()
    };
    // Pins drop outside the table lock.
    drop(released);
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
    // Invalidation closes later dispatch; it does not retroactively cancel JS
    // already running. Existing actor fencing and output gates still apply.
    anyhow::ensure!(
        !slot.capabilities_closed(),
        "capability owner isolate invalidated"
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
        if let Some(export) = entries.remove(&route.token) {
            forget_session_lanes(&export);
        }
        tracing::debug!(
            event = "capability_revoke",
            exports = entries.len(),
            pins = entries.values().filter(|e| e.pin.is_some()).count(),
            "released live capability"
        );
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

// A retained route owns one JS reference, including across cancellation of the
// async isolate turn that creates it. No peer endpoint can request retention.
pub(crate) struct RetainedRoute(Option<Route>);
impl RetainedRoute {
    pub(crate) fn transfer(mut self) {
        self.0.take();
    }
}
impl Drop for RetainedRoute {
    fn drop(&mut self) {
        if let Some(route) = self.0.take() {
            crate::capability_session::release_local(route);
        }
    }
}
pub(crate) async fn retain_local(route: &Route) -> Result<RetainedRoute> {
    preflight(route)?;
    let slot = {
        let entries = exports().lock().unwrap();
        entries
            .get(&route.token)
            .and_then(|entry| entry.slot.upgrade())
            .context("capability owner isolate is gone")?
    };
    let _live = slot
        .try_affiliate_capability()
        .await
        .context("capability owner isolate retired")?;
    slot.turn(|worker| {
        worker.retain_capability(route)?;
        // Construct the guard inside the turn: cancellation can drop a turn's
        // return value before the awaiting future sees it.
        Ok(RetainedRoute(Some(route.clone())))
    })
    .await
}

/// Lanes bound to each caller session, so a lost session removes exactly its
/// own lanes without scanning every export under the table lock.
static SESSION_LANES: OnceLock<Mutex<HashMap<String, Vec<(String, String)>>>> = OnceLock::new();
fn session_lanes() -> &'static Mutex<HashMap<String, Vec<(String, String)>>> {
    SESSION_LANES.get_or_init(Default::default)
}

fn order_lane(
    route: &Route,
    order: &CallOrder,
    session: Option<&str>,
) -> Result<Arc<OrderLane>> {
    anyhow::ensure!(
        !order.lane.is_empty() && order.lane.len() <= 128,
        "invalid capability ordering lane"
    );
    let mut entries = exports().lock().unwrap();
    let export = entries
        .get_mut(&route.token)
        .ok_or_else(|| not_executed("capability released before ordered admission"))?;
    anyhow::ensure!(&export.route == route, "invalid capability ordering route");
    anyhow::ensure!(
        export.lanes.len() < 4096 || export.lanes.contains_key(&order.lane),
        "capability ordering lane limit reached"
    );
    // Never create (or bind) a lane for a session that is already gone: a
    // late callee guard or Skip after `close_session_lanes` would otherwise
    // resurrect a removed lane bound to the dead session. The check runs with
    // the exports table locked, which `close_session_lanes` also takes after
    // the session is marked closed, so the two cannot interleave.
    if let Some(id) = session {
        let bound = export
            .lanes
            .get(&order.lane)
            .is_some_and(|lane| lane.state.lock().unwrap().session.is_some());
        anyhow::ensure!(
            bound || crate::capability_session::Session::get(id).is_ok(),
            "capability session disconnected"
        );
    }
    let lane = export.lanes.entry(order.lane.clone()).or_default().clone();
    let mut state = lane.state.lock().unwrap();
    // A lane belongs to one caller session for its whole life. Another
    // session can neither join nor resolve it.
    match (&state.session, session) {
        (None, Some(id)) if state.next == 0 && state.skipped.is_empty() && !state.active => {
            state.session = Some(id.to_string());
            session_lanes()
                .lock()
                .unwrap()
                .entry(id.to_string())
                .or_default()
                .push((route.token.clone(), order.lane.clone()));
        }
        (owner, session) => anyhow::ensure!(
            owner.as_deref() == session,
            "capability ordering lane belongs to another session"
        ),
    }
    drop(state);
    Ok(lane)
}

/// Resolve a sequence slot without dispatching it. Idempotent, and a no-op
/// for a slot that already dispatched or is dispatching.
pub(crate) fn skip_order(route: &Route, order: &CallOrder, session: Option<&str>) {
    if route.process != process() {
        return;
    }
    let Ok(lane) = order_lane(route, order, session) else {
        return;
    };
    let mut state = lane.state.lock().unwrap();
    if order.sequence < state.next || (order.sequence == state.next && state.active) {
        return;
    }
    if state.skipped.len() >= 4096 && !state.skipped.contains(&order.sequence) {
        state.broken = Some("capability ordering lane skip limit reached".into());
    } else {
        state.skipped.insert(order.sequence);
        if !state.active {
            state.advance();
        }
    }
    drop(state);
    lane.changed.notify_waiters();
    tracing::debug!(event = "capability_order_skip", lane = %order.lane, sequence = order.sequence, "resolved an undelivered ordered call");
}

/// Fail every lane owned by a lost process session, now: no later call can
/// arrive on it, so its waiters must not sit out the gap timeout.
/// The lanes are also removed: no later call can arrive on a closed session,
/// so their state would only occupy the export's lane budget.
pub(crate) fn close_session_lanes(session: &str) {
    let lanes: Vec<Arc<OrderLane>> = {
        // Lock order: exports, then session lanes (as in order_lane).
        let mut entries = exports().lock().unwrap();
        let owned = session_lanes().lock().unwrap().remove(session).unwrap_or_default();
        owned
            .into_iter()
            .filter_map(|(token, name)| {
                let export = entries.get_mut(&token)?;
                let lane = export.lanes.get(&name)?;
                if lane.state.lock().unwrap().session.as_deref() != Some(session) {
                    return None;
                }
                export.lanes.remove(&name)
            })
            .collect()
    };
    for lane in lanes {
        let mut state = lane.state.lock().unwrap();
        state.broken.get_or_insert_with(|| "capability session disconnected".into());
        drop(state);
        lane.changed.notify_waiters();
    }
}

/// The callee half of slot resolution: whatever happens to a received ordered
/// request after this point (rejection before admission, cancellation while
/// waiting, dispatch), its sequence slot is resolved when this is dropped.
pub struct OrderSlot {
    route: Route,
    order: Option<CallOrder>,
    session: Option<String>,
}
impl OrderSlot {
    pub fn new(route: &Route, order: Option<&CallOrder>, session: Option<&str>) -> Self {
        Self {
            route: route.clone(),
            order: order.cloned(),
            session: session.map(str::to_string),
        }
    }
}
impl Drop for OrderSlot {
    fn drop(&mut self) {
        if let Some(order) = self.order.take() {
            skip_order(&self.route, &order, self.session.as_deref());
        }
    }
}

/// The caller half: an ordered request that may not have reached its callee
/// is resolved there by a skip notice. Only an answer carrying
/// [`ORDER_RESOLVED_HEADER`] proves the remote callee resolved the slot, which
/// disarms this. A same-process call never disarms it: dispatch can end before
/// the callee builds its guard (preflight, actor routing or admission), and a
/// skip after the callee dispatched or skipped the slot is a no-op.
pub(crate) struct CallerOrderSlot {
    route: Route,
    order: Option<CallOrder>,
    session: Option<String>,
}
impl CallerOrderSlot {
    pub(crate) fn new(route: &Route, order: Option<&CallOrder>, session: Option<&str>) -> Self {
        Self {
            route: route.clone(),
            order: order.cloned(),
            session: session.map(str::to_string),
        }
    }
    pub(crate) fn delivered(&mut self) {
        self.order = None;
    }
}
impl Drop for CallerOrderSlot {
    fn drop(&mut self) {
        let Some(order) = self.order.take() else {
            return;
        };
        if self.route.process == process() {
            skip_order(&self.route, &order, self.session.as_deref());
        } else if let Some(session) = self.session.as_deref() {
            crate::capability_session::skip_remote(self.route.clone(), order, session);
        }
    }
}

// Admission ordering ends when target JS has entered its method, not when
// its promise settles. This preserves e-order without deadlocking callbacks.
async fn ordered_admission(
    route: &Route,
    order: Option<&CallOrder>,
    session: Option<&str>,
) -> Result<Option<OrderPermit>> {
    let Some(order) = order else {
        return Ok(None);
    };
    let lane = order_lane(route, order, session)?;
    let waiting = async {
        loop {
            let notified = lane.changed.notified();
            tokio::pin!(notified);
            notified.as_mut().enable();
            {
                let mut state = lane.state.lock().unwrap();
                if let Some(reason) = &state.broken {
                    anyhow::bail!("capability ordering channel is broken: {reason}");
                }
                if order.sequence < state.next || state.skipped.contains(&order.sequence) {
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
    match tokio::time::timeout(ORDER_GAP_TIMEOUT, waiting).await {
        Ok(result) => result,
        Err(_) => {
            lane.state
                .lock()
                .unwrap()
                .broken
                .get_or_insert_with(|| "predecessor did not arrive".into());
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

struct CancelCall {
    slot: Arc<crate::pool::Slot>,
    invocation: Vec<u8>,
    armed: bool,
}
impl Drop for CancelCall {
    fn drop(&mut self) {
        if !self.armed {
            return;
        }
        let (reply, receive) = tokio::sync::oneshot::channel();
        drop(receive);
        let job = crate::WorkerJob::Rpc {
            entrypoint: CANCEL_ENTRYPOINT.into(),
            operation: crate::WorkerRpcOperation::Get { path: vec![] },
            props: self.invocation.clone().into(),
            invocation_limits: None,
            tail_report: None,
            reply,
        };
        tokio::spawn(crate::runtime::drive_capability(self.slot.clone(), job));
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

pub async fn invoke_local(request: Request) -> Result<bytes::Bytes> {
    let _slot = OrderSlot::new(
        &request.route,
        request.order.as_ref(),
        request.session.as_deref(),
    );
    preflight(&request.route)?;
    let mut permit = ordered_admission(
        &request.route,
        request.order.as_ref(),
        request.session.as_deref(),
    )
    .await?;
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
    // The affiliation holds the heap for this dispatch. Between calls a
    // stateless heap is held by its export's pin; an actor heap by its cell,
    // so exports never obstruct actor migration.
    let _live = slot
        .try_affiliate_capability()
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
    let mut cancellation = CancelCall {
        slot: slot.clone(),
        invocation: serde_json::to_vec(&invocation)?,
        armed: !request.release,
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
        props: serde_json::to_vec(&invocation)?.into(),
        invocation_limits: None,
        tail_report: None,
        reply,
    };
    let mut driving = Running(Some(tokio::spawn(crate::runtime::drive_capability(
        slot, job,
    ))));
    let completion = async {
        crate::asyncrt::select! {
            _ = &mut start_receive => { permit.take(); receive.await },
            result = &mut receive => { permit.take(); result },
        }
    };
    // No duration bound: the call ends when the owner answers, when the
    // owner's isolate goes (the reply is dropped), or when the caller drops
    // this future, which cancels the owner's drive through `Running`.
    let result = completion.await;
    cancellation.armed = false;
    match result {
        Ok(result) => {
            driving.0.take();
            result
        }
        Err(_) => {
            let _ = driving.0.as_mut().unwrap().await;
            Err(anyhow!("capability owner dropped reply"))
        }
    }
}

pub async fn call(request: Request) -> Result<bytes::Bytes> {
    let slot = CallerOrderSlot::new(
        &request.route,
        request.order.as_ref(),
        request.session.as_deref(),
    );
    call_ordered(request, slot).await
}

/// `slot` is created by the caller before any output gate, so a call that is
/// canceled or fails before it reaches its callee still resolves its sequence.
pub(crate) async fn call_ordered(
    mut request: Request,
    mut slot: CallerOrderSlot,
) -> Result<bytes::Bytes> {
    if request.release {
        slot.delivered();
    }
    let result = async {
        if request.route.process == process() {
            request.prepared_wire = None;
            // The slot stays armed until this call ends (see CallerOrderSlot).
            #[cfg(test)]
            if let Some(dispatch) = test_local_dispatch() {
                return dispatch(request).await;
            }
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
        let session = crate::capability_session::Session::get(
            request
                .session
                .as_deref()
                .context("live capability has no session")?,
        )?;
        anyhow::ensure!(
            session.peer == request.route.node && session.process == request.route.process,
            "live capability session owner changed"
        );
        if request.release {
            session.release_peer(request.route)?;
            return Ok(bytes::Bytes::new());
        }
        let transfer = session.open().await?;
        request.transfer = Some(transfer.id().into());
        if let Some(args) = request.args.take() {
            request.args = Some(crate::capability_packet::bind(
                &args,
                &session,
                transfer.id(),
            )?);
        }
        let body = serde_json::to_vec(&request)?;
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
        // Only an answer the callee produced after building its own slot
        // guard proves resolution; a pre-guard rejection leaves it to the skip.
        if response
            .headers()
            .get(ORDER_RESOLVED_HEADER)
            .is_some_and(|v| v == "1")
        {
            slot.delivered();
        }
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
            // Peer responses are not authenticated, so a peer's "not executed"
            // header cannot authorize a replay: it is reported, but the error
            // stays ambiguous. Only a local proof (a failed connect) is typed.
            let message = format!(
                "capability owner rejected call{}: {}",
                if not_run {
                    " (peer reports not executed; unauthenticated, not retried)"
                } else {
                    ""
                },
                String::from_utf8_lossy(&bytes)
            );
            return Err(anyhow!(message));
        }
        crate::capability_packet::receive(bytes, &session, transfer.id())
    };
    tokio::time::timeout(TIMEOUT, result)
        .await
        .context("capability call timed out; it was not retried")?
}

#[cfg(test)]
type TestDispatch = Arc<dyn Fn(Request) -> Pin<Box<dyn Future<Output = Result<bytes::Bytes>> + Send>> + Send + Sync>;
#[cfg(test)]
thread_local! {
    static TEST_LOCAL_DISPATCH: std::cell::RefCell<Option<TestDispatch>> = const { std::cell::RefCell::new(None) };
}
/// Stand-in for the node's same-process dispatch (`main.rs dispatch_capability`),
/// which can wait or fail in actor routing before `invoke_local` runs.
#[cfg(test)]
fn test_local_dispatch() -> Option<TestDispatch> {
    TEST_LOCAL_DISPATCH.with_borrow(|d| d.clone())
}
#[cfg(test)]
pub(crate) fn set_test_local_dispatch(dispatch: Option<TestDispatch>) {
    TEST_LOCAL_DISPATCH.with_borrow_mut(|d| *d = dispatch);
}

#[cfg(test)]
mod order_slot_tests {
    //! C6-02: every sequence slot resolves exactly once, and a lost session
    //! fails its lanes immediately instead of after the gap timeout.
    use super::*;
    fn install(token: &str) -> Route {
        let route = Route {
            node: "n".into(),
            addr: "127.0.0.1:1".into(),
            process: process().into(),
            heap: "1".into(),
            token: token.into(),
            seal: String::new(),
            owner_scope: None,
            storage_scope: None,
            epoch: None,
        };
        exports().lock().unwrap().insert(
            route.token.clone(),
            Export {
                route: route.clone(),
                lanes: HashMap::new(),
                slot: Weak::new(),
                token: "1".into(),
                pin: None,
            },
        );
        route
    }
    fn order(sequence: u64) -> CallOrder {
        CallOrder {
            lane: "lane".into(),
            sequence,
        }
    }
    #[tokio::test]
    async fn skipped_predecessors_admit_the_next_call_at_once() {
        let route = install(&random_id());
        skip_order(&route, &order(0), None);
        skip_order(&route, &order(2), None);
        let permit = ordered_admission(&route, Some(&order(1)), None)
            .await
            .unwrap();
        drop(permit);
        // 2 was skipped ahead of time: 3 is next without waiting.
        let started = std::time::Instant::now();
        drop(ordered_admission(&route, Some(&order(3)), None).await.unwrap());
        assert!(started.elapsed() < std::time::Duration::from_secs(1));
        // A late arrival of a skipped slot is refused, never run out of order.
        assert!(ordered_admission(&route, Some(&order(2)), None).await.is_err());
        // Skipping a dispatched slot is a no-op.
        skip_order(&route, &order(1), None);
        drop(ordered_admission(&route, Some(&order(4)), None).await.unwrap());
    }
    #[tokio::test]
    async fn callee_guard_resolves_rejected_and_canceled_requests() {
        let route = install(&random_id());
        // Rejected before admission: the guard alone resolves slot 0.
        drop(OrderSlot::new(&route, Some(&order(0)), None));
        // Canceled while waiting for its predecessor: slot 2 resolves too.
        let waiting = {
            let route = route.clone();
            tokio::spawn(async move {
                let _slot = OrderSlot::new(&route, Some(&order(2)), None);
                ordered_admission(&route, Some(&order(2)), None).await.map(drop)
            })
        };
        for _ in 0..8 {
            tokio::task::yield_now().await;
        }
        waiting.abort();
        let _ = waiting.await;
        drop(ordered_admission(&route, Some(&order(1)), None).await.unwrap());
        let started = std::time::Instant::now();
        drop(ordered_admission(&route, Some(&order(3)), None).await.unwrap());
        assert!(started.elapsed() < std::time::Duration::from_secs(1));
    }
    #[tokio::test]
    async fn lost_session_fails_its_waiting_lane_now() {
        let route = install(&random_id());
        let live = crate::capability_session::Session::register(
            random_id(),
            "peer".into(),
            "p".repeat(64),
        )
        .unwrap();
        let session = live.id.clone();
        let waiting = {
            let (route, session) = (route.clone(), session.clone());
            tokio::spawn(async move {
                ordered_admission(&route, Some(&order(1)), Some(&session))
                    .await
                    .map(drop)
            })
        };
        for _ in 0..8 {
            tokio::task::yield_now().await;
        }
        let started = std::time::Instant::now();
        live.close();
        let error = waiting.await.unwrap().unwrap_err().to_string();
        assert!(error.contains("capability session disconnected"), "{error}");
        assert!(started.elapsed() < std::time::Duration::from_secs(1));
        // The closed session's lane is gone; its index entry with it.
        assert!(exports().lock().unwrap().get(&route.token).unwrap().lanes.is_empty());
        assert!(!session_lanes().lock().unwrap().contains_key(&session));
        // N-2: a late guard or Skip for that session cannot resurrect it.
        skip_order(&route, &order(2), Some(&session));
        drop(OrderSlot::new(&route, Some(&order(3)), Some(&session)));
        assert!(exports().lock().unwrap().get(&route.token).unwrap().lanes.is_empty());
        assert!(!session_lanes().lock().unwrap().contains_key(&session));
    }
}

#[cfg(test)]
#[path = "../../tests/regressions/OR2-01/native.rs"]
mod session_lane_index_regressions;

#[cfg(test)]
#[path = "../../tests/regressions/OR1-01/native.rs"]
mod same_process_slot_regressions;

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
