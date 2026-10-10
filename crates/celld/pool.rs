// Copyright 2026 Deno Land Inc. Apache-2.0 license.

// Isolate admission and deadlines are in the V8 arm outside the Actor execution
// domain.
#![allow(clippy::disallowed_methods)]

//! The isolate pool: the shell around `celld_logic::isolate`.
//!
//! One multi-threaded tokio runtime owns every socket and timer. Isolates
//! belong to no thread — `v8::Locker` installs the entering thread's
//! per-isolate state, so any worker can take an isolate and run a turn in it.
//! This module owns the isolates and the counters; every choice about which
//! isolate, when to grow, what to shed and what to retire is made by
//! `celld_logic::isolate` and merely performed here.
//!
//! **The gate exists so nothing blocks.** `SharedIsolate::lock()` blocks
//! until its holder releases. Every path here takes the slot's async permit
//! first, so that blocking lock is uncontended by construction. A `lock()`
//! reached without the permit would park a tokio worker on V8, which is the
//! one thing this runtime refuses to do.

use std::sync::atomic::AtomicBool;
use std::sync::atomic::AtomicU64;
use std::sync::atomic::AtomicUsize;
use std::sync::atomic::Ordering;
use std::sync::Arc;
use std::sync::Mutex;
use std::sync::RwLock;

use anyhow::Result;
use celld_logic::isolate::HeapId;
use celld_logic::isolate::IsolateId;
use celld_logic::isolate::IsolateLoad;
use celld_logic::isolate::Placement;
use celld_logic::isolate::PoolLimits;
use celld_logic::isolate::PoolLoad;
use celld_logic::isolate::Refusal;

use crate::js;

pub use crate::engine_api::AdmitError;
pub use crate::engine_api::PoolCensus;

/// Heap identity is process-wide because pressure policy compares cells from
/// every script pool and every draining generation. A counter inside `Pool`
/// would reproduce the collision this identity prevents. The core treats the
/// value as opaque, so its allocation order is not a deterministic decision.
static NEXT_HEAP_ID: AtomicU64 = AtomicU64::new(1);

fn next_heap_id() -> HeapId {
    let value = NEXT_HEAP_ID
        .fetch_update(Ordering::Relaxed, Ordering::Relaxed, |value| {
            value.checked_add(1)
        })
        .expect("V8 heap identity space exhausted");
    HeapId::new(value)
}

/// Bound the producer replies that can wait for one Queue's shared commit and
/// durability proof. Four 64-call groups can overlap, and a stopped bucket
/// still cannot retain an unbounded number of promises or copied bodies.
pub(crate) const MAX_QUEUE_PRODUCER_EVENTS_PER_CELL: usize = 256;

#[derive(Clone, Debug, Eq, Hash, PartialEq)]
enum TurnLane {
    Stateless,
    Cell(String),
}

#[derive(Default)]
struct TurnSchedule {
    current: Option<TurnLane>,
    ready: std::collections::VecDeque<TurnLane>,
    waiting: std::collections::HashMap<
        TurnLane,
        std::collections::VecDeque<tokio::sync::oneshot::Sender<()>>,
    >,
}

#[derive(Default)]
struct TurnScheduler {
    schedule: Mutex<TurnSchedule>,
}

struct TurnPermit<'a>(&'a TurnScheduler);

impl TurnScheduler {
    async fn acquire(&self, lane: TurnLane) -> TurnPermit<'_> {
        let receive = {
            let mut schedule = self.schedule.lock().expect("turn scheduler poisoned");
            if schedule.current.is_none() {
                schedule.current = Some(lane);
                None
            } else {
                let (send, receive) = tokio::sync::oneshot::channel();
                if !schedule.waiting.contains_key(&lane) && schedule.current.as_ref() != Some(&lane)
                {
                    schedule.ready.push_back(lane.clone());
                }
                schedule.waiting.entry(lane).or_default().push_back(send);
                Some(receive)
            }
        };
        if let Some(receive) = receive {
            // Cancellation leaves a closed sender in this lane. `release`
            // skips it, so a waiter dropped before its grant cannot strand
            // the active token; `TurnWaiter` covers one dropped after it.
            let mut waiting = TurnWaiter {
                scheduler: self,
                receive: Some(receive),
            };
            let _ = waiting
                .receive
                .as_mut()
                .expect("a queued turn waits on its grant")
                .await;
            // Granted: the permit below owns the turn from here on, with no
            // suspension point between the two.
            waiting.receive = None;
        }
        TurnPermit(self)
    }

    fn release(&self) {
        let mut schedule = self.schedule.lock().expect("turn scheduler poisoned");
        let current = schedule
            .current
            .take()
            .expect("a released turn scheduler has a current lane");
        if schedule
            .waiting
            .get(&current)
            .is_some_and(|waiters| !waiters.is_empty())
        {
            schedule.ready.push_back(current);
        }
        while let Some(lane) = schedule.ready.pop_front() {
            let (send, keep_lane) = {
                let waiters = schedule
                    .waiting
                    .get_mut(&lane)
                    .expect("a ready turn lane has waiters");
                (waiters.pop_front().unwrap(), !waiters.is_empty())
            };
            if !keep_lane {
                schedule.waiting.remove(&lane);
            }
            if send.send(()).is_ok() {
                schedule.current = Some(lane);
                return;
            }
            if keep_lane {
                schedule.ready.push_back(lane);
            }
        }
    }
}

impl Drop for TurnPermit<'_> {
    fn drop(&mut self) {
        self.0.release();
    }
}

/// A queued turn that has not yet observed its grant.
///
/// `release` makes a lane current when its send succeeds, and that send only
/// needs the receiver to exist. A waiter dropped after the send but before it
/// ran — its task aborted, its op cleared, its select branch lost — held the
/// isolate with nothing left to release it, and every later turn on the
/// isolate queued forever. Workerd's waiter passes the lock on when it goes:
/// `~AsyncLockWaiter` fulfills the next waiter if it was at the front
/// (io/async-lock-scheduler.h:197-224). Closing the receiver first decides the
/// race: a send that lands before the close is a grant this drop releases, and
/// one after it fails, so `release` moves on to the next lane itself.
struct TurnWaiter<'a> {
    scheduler: &'a TurnScheduler,
    receive: Option<tokio::sync::oneshot::Receiver<()>>,
}

impl Drop for TurnWaiter<'_> {
    fn drop(&mut self) {
        let Some(mut receive) = self.receive.take() else {
            return;
        };
        receive.close();
        if receive.try_recv().is_ok() {
            self.scheduler.release();
        }
    }
}

pub(crate) struct QueueProducerPermit {
    slot: Arc<Slot>,
    scope: String,
}

impl Drop for QueueProducerPermit {
    fn drop(&mut self) {
        self.slot.release_queue_producer(&self.scope);
    }
}

/// One isolate, and everything the decision core needs to know about it.
pub struct Slot {
    /// The index used only inside this pool's placement snapshot and slot
    /// vector. Distinct pools can use the same value.
    pub id: IsolateId,
    /// This slot, for an op of one of its turns to reach it: a facet of the
    /// script's own class runs in the isolate of the object that holds it.
    me: std::sync::Weak<Slot>,
    /// The identity reported to node-wide Actor and pressure policy.
    heap_id: HeapId,
    /// The async gate, holding the isolate it guards. Locking this is what
    /// makes the V8 `Locker` beneath it uncontended.
    ///
    /// `None` once the isolate has been retired and freed. Retirement only
    /// frees a slot that is drained — no turns, no affiliations — and a
    /// retiring slot is filtered out of every placement decision. Existing
    /// capability continuations acquire an affiliation under this same lock;
    /// entering after the worker has been freed would be a bug.
    worker: tokio::sync::Mutex<Option<js::Worker>>,
    turn_scheduler: TurnScheduler,
    queue_producers: Mutex<std::collections::HashMap<String, usize>>,
    turns: AtomicUsize,
    requests: AtomicUsize,
    /// Live capabilities this stateless heap exported (`capability::export`).
    /// They keep the heap from being freed, as a workerd session keeps its
    /// Worker until no capability crosses it, without counting as admitted
    /// requests.
    export_pins: AtomicUsize,
    /// The pool's admission bell, cloned into every slot so an
    /// `Affiliation` drop can ring it without holding the pool.
    freed: Arc<tokio::sync::Notify>,
    /// The pool's reclaim bell, rung when a retiring isolate may have
    /// drained. `None` for a standalone slot: nothing frees or replaces it,
    /// so [`Slot::condemn`] cannot apply to it.
    reclaim: Option<Arc<tokio::sync::Notify>>,
    /// The slot holds a Worker Loader's Worker, so the facets it runs belong
    /// to the root that started them rather than to this isolate.
    loaded_worker: bool,
    /// Cells whose realm lives in this isolate. Not a count of live work: a
    /// cell stays until it is evicted or handed to another node, which is
    /// why `retire` refuses an isolate holding any.
    cells: AtomicUsize,
    // Reservations can adopt out of order; only completed adoptions count
    // toward the collection boundary. Residency drop retires both counts.
    adopted_cells: AtomicUsize,
    retiring: AtomicBool,
    // Ordinary shrink stops placement while existing requests drain. Fatal
    // condemnation and generation shutdown also forbid capability continuation.
    capabilities_closed: AtomicBool,
    /// Serializes the two lifecycle transitions that touch `retiring` and
    /// `capabilities_closed` together: closing (generation retirement,
    /// condemnation) and an export returning a drained heap to service.
    /// Closing is final; with this lock an export can never observe "open",
    /// lose the race to a close, and then clear `retiring` (Opus review 2, N-4).
    lifecycle: Mutex<()>,
    #[cfg(celld_internal_tests)]
    turn_observations: Mutex<Vec<String>>,
}

thread_local! {
    static CURRENT_SLOT: std::cell::RefCell<Option<std::sync::Weak<Slot>>> =
        const { std::cell::RefCell::new(None) };
}

/// The slot whose turn this thread runs, for an op that must reach its own
/// isolate again after the turn.
pub(crate) fn current_slot() -> Option<Arc<Slot>> {
    CURRENT_SLOT.with_borrow(|slot| slot.as_ref().and_then(std::sync::Weak::upgrade))
}

impl Slot {
    fn observe(&self) -> IsolateLoad {
        IsolateLoad {
            turns: self.turns.load(Ordering::Relaxed),
            requests: self.requests.load(Ordering::Relaxed),
            cells: self.cells.load(Ordering::Relaxed),
            exports: self.export_pins.load(Ordering::Relaxed),
            retiring: self.retiring.load(Ordering::Relaxed),
        }
    }

    /// Enter the isolate for one turn and run `f` inside it.
    ///
    /// Only the gate is awaited; `f` is synchronous by type, so holding the
    /// isolate across an await is unwritable rather than a rule a comment
    /// asks callers to remember.
    pub async fn turn<T>(&self, f: impl FnOnce(&mut js::Worker) -> T) -> T {
        self.turn_in(TurnLane::Stateless, f).await
    }

    /// Enter one cell turn through a round-robin lane for that cell. A hot
    /// cell can retain its next place, but it cannot take the next place from
    /// another cell that already waits on the same isolate.
    pub async fn turn_cell<T>(&self, scope: &str, f: impl FnOnce(&mut js::Worker) -> T) -> T {
        self.turn_in(TurnLane::Cell(scope.to_string()), f).await
    }

    async fn turn_in<T>(&self, lane: TurnLane, f: impl FnOnce(&mut js::Worker) -> T) -> T {
        struct Counted<'a>(&'a Slot);
        impl Drop for Counted<'_> {
            fn drop(&mut self) {
                self.0.turns.fetch_sub(1, Ordering::Relaxed);
            }
        }
        self.turns.fetch_add(1, Ordering::Relaxed);
        let _turn = Counted(self);
        let _scheduled = self.turn_scheduler.acquire(lane.clone()).await;
        let mut worker = self.worker.lock().await;
        let worker = match worker.as_mut() {
            Some(worker) => worker,
            None => panic!("entered isolate {} after it was freed", self.id),
        };
        #[cfg(celld_internal_tests)]
        self.turn_observations.lock().unwrap().push(match lane {
            TurnLane::Stateless => "stateless".to_string(),
            TurnLane::Cell(scope) => scope,
        });
        let previous = CURRENT_SLOT.replace(Some(self.me.clone()));
        let result = f(worker);
        CURRENT_SLOT.set(previous);
        result
    }

    /// Reserve one event through its complete lifetime, including the reply
    /// gate. Releasing at the gate would let stalled storage retain unbounded
    /// promises and copied bodies. Cell turn fairness is enforced separately.
    pub(crate) fn queue_producer(self: &Arc<Self>, scope: &str) -> Option<QueueProducerPermit> {
        let mut producers = self
            .queue_producers
            .lock()
            .expect("Queue producer admission poisoned");
        let outstanding = producers.entry(scope.to_string()).or_default();
        if *outstanding >= MAX_QUEUE_PRODUCER_EVENTS_PER_CELL {
            return None;
        }
        *outstanding += 1;
        Some(QueueProducerPermit {
            slot: self.clone(),
            scope: scope.to_string(),
        })
    }

    fn release_queue_producer(&self, scope: &str) {
        let mut producers = self
            .queue_producers
            .lock()
            .expect("Queue producer admission poisoned");
        let outstanding = producers
            .get_mut(scope)
            .expect("a Queue producer permit has an admission");
        *outstanding -= 1;
        if *outstanding == 0 {
            producers.remove(scope);
        }
    }

    /// Continue an existing exported capability on its exact live heap. Normal
    /// pool shrink stops new placement, but a WebSocket or suspended request may
    /// still own this draining heap. Share the free-retired lock so this never
    /// revives a freed heap. Generation shutdown and condemnation remain closed.
    pub(crate) async fn try_affiliate_capability(self: &Arc<Self>) -> Option<Affiliation> {
        let worker = self.worker.lock().await;
        if self.capabilities_closed() || worker.is_none() {
            return None;
        }
        Some(self.affiliate())
    }

    pub(crate) fn capabilities_closed(&self) -> bool {
        self.capabilities_closed.load(Ordering::Acquire)
    }

    /// Mark a request as living in this isolate. Held for the request's whole
    /// life, including while it is suspended, because its promise stays in
    /// this heap and every later turn must come back here.
    pub fn affiliate(self: &Arc<Self>) -> Affiliation {
        self.requests.fetch_add(1, Ordering::Relaxed);
        Affiliation(self.clone())
    }

    /// Keep this heap from being freed while an exported capability lives.
    ///
    /// A request still draining an ordinarily retired heap may export a
    /// capability (workerd: an export keeps its IoContext, and the Worker
    /// keeps serving, until the holder's context ends; api/worker-rpc.c++
    /// ~JsRpcStub). Such a heap returns to service rather than staying
    /// retiring and unfreeable. Generation retirement and condemnation close
    /// capabilities first and are never reversed.
    /// Returns `None` once capabilities are closed: generation retirement and
    /// condemnation are final, and a pin would only keep the old heap from
    /// being freed while every call on the export is refused (N-3).
    pub(crate) fn pin_export(self: &Arc<Self>) -> Option<ExportPin> {
        let _lifecycle = self.lifecycle.lock().unwrap();
        if self.capabilities_closed() {
            return None;
        }
        self.export_pins.fetch_add(1, Ordering::Relaxed);
        if self.reclaim.is_some() && self.retiring.swap(false, Ordering::Relaxed) {
            tracing::info!(isolate = %self.heap_id, slot = self.id, "isolate returned to service: a draining request exported a capability");
        }
        Some(ExportPin(self.clone()))
    }

    /// Close capabilities and retire, as one transition. Returns whether the
    /// slot was already retiring.
    fn close_capabilities(&self) -> bool {
        let _lifecycle = self.lifecycle.lock().unwrap();
        self.capabilities_closed.store(true, Ordering::Release);
        self.retiring.swap(true, Ordering::Relaxed)
    }

    fn may_free(&self) -> bool {
        celld_logic::isolate::may_free(&self.observe())
    }

    /// A slot holding a Worker Loader's Worker.
    pub(crate) fn loaded_worker(worker: js::Worker) -> Arc<Self> {
        Self::outside_pool(worker, true)
    }

    /// A slot holding a Worker outside a placement pool.
    ///
    /// A dynamic Worker owns exactly one isolate, so it needs no
    /// admission, growth, or retirement policy.
    fn outside_pool(worker: js::Worker, loaded_worker: bool) -> Arc<Self> {
        Arc::new_cyclic(|me| Slot {
            me: me.clone(),
            id: 0,
            heap_id: next_heap_id(),
            worker: tokio::sync::Mutex::new(Some(worker)),
            turn_scheduler: TurnScheduler::default(),
            queue_producers: Mutex::new(std::collections::HashMap::new()),
            turns: AtomicUsize::new(0),
            requests: AtomicUsize::new(0),
            export_pins: AtomicUsize::new(0),
            freed: Arc::new(tokio::sync::Notify::new()),
            reclaim: None,
            loaded_worker,
            cells: AtomicUsize::new(0),
            adopted_cells: AtomicUsize::new(0),
            retiring: AtomicBool::new(false),
            capabilities_closed: AtomicBool::new(false),
            lifecycle: Mutex::new(()),
            #[cfg(celld_internal_tests)]
            turn_observations: Mutex::new(Vec::new()),
        })
    }

    /// Whether this slot holds a Worker Loader's Worker.
    pub(crate) fn is_loaded_worker(&self) -> bool {
        self.loaded_worker
    }

    #[cfg(celld_internal_tests)]
    pub fn for_test(worker: js::Worker) -> Arc<Self> {
        Self::outside_pool(worker, false)
    }

    #[cfg(all(test, celld_internal_tests))]
    pub(crate) fn vacant_for_request_cancellation_test() -> Arc<Self> {
        Arc::new_cyclic(|me| Slot {
            me: me.clone(),
            id: 0,
            heap_id: HeapId::new(0),
            worker: tokio::sync::Mutex::new(None),
            turn_scheduler: TurnScheduler::default(),
            queue_producers: Mutex::new(std::collections::HashMap::new()),
            turns: AtomicUsize::new(0),
            requests: AtomicUsize::new(0),
            export_pins: AtomicUsize::new(0),
            freed: Arc::new(tokio::sync::Notify::new()),
            reclaim: None,
            loaded_worker: false,
            cells: AtomicUsize::new(0),
            adopted_cells: AtomicUsize::new(0),
            retiring: AtomicBool::new(false),
            capabilities_closed: AtomicBool::new(false),
            lifecycle: Mutex::new(()),
            turn_observations: Mutex::new(Vec::new()),
        })
    }

    #[cfg(celld_internal_tests)]
    #[doc(hidden)]
    pub async fn hold_turn_for_test(&self) -> impl Drop + '_ {
        self.worker.lock().await
    }

    #[cfg(celld_internal_tests)]
    #[doc(hidden)]
    pub fn queued_turns_for_test(&self) -> usize {
        self.turns.load(Ordering::Relaxed)
    }

    #[cfg(celld_internal_tests)]
    #[doc(hidden)]
    pub fn reset_turn_observations_for_test(&self) {
        self.turn_observations.lock().unwrap().clear();
    }

    #[cfg(celld_internal_tests)]
    #[doc(hidden)]
    pub fn turn_observations_for_test(&self) -> Vec<String> {
        self.turn_observations.lock().unwrap().clone()
    }

    /// Give this isolate a cell's realm. Held for as long as the cell lives
    /// here, which is what stops the isolate being retired underneath it.
    fn house(self: &Arc<Self>, max_cells: usize) -> Residency {
        let cells = self.cells.fetch_add(1, Ordering::Relaxed) + 1;
        debug_assert!(cells <= max_cells);
        Residency {
            slot: self.clone(),
            max_cells,
            adopted: false,
        }
    }

    pub fn is_retiring(&self) -> bool {
        self.retiring.load(Ordering::Relaxed)
    }

    /// Retire this isolate because its guest can no longer run in it, and
    /// ask the pool to free it once it drains. Returns whether the slot
    /// belongs to a pool that can do both.
    ///
    /// Placement already skips a retiring slot, so the next request grows a
    /// fresh isolate instead. Leaving the dead isolate to placement is the
    /// failure this prevents: it fails each request in about a millisecond,
    /// so it carries the fewest turns and `place` hands it nearly every
    /// request. [`reap`](Self::reap) does not know it is dead, and on a
    /// four-isolate node it retired the three healthy isolates first, one
    /// per 30 s pass, so one fatal Python error failed that node's traffic
    /// for 94 s.
    ///
    /// The bell, not the 30 s reap, frees the heap: a guest that fails on
    /// every start would otherwise hold one dead heap per failure until the
    /// next tick, and a Python heap is tens of megabytes.
    ///
    /// A cell pool has no task on the bell. A condemned cell isolate still
    /// takes no new cell, and frees when its cells leave, as retirement
    /// always has; Python Workers cannot declare cells.
    pub(crate) fn condemn(&self, reason: &str) -> bool {
        let Some(reclaim) = &self.reclaim else {
            return false;
        };
        let was_retiring = self.close_capabilities();
        crate::capability::drop_closed_exports();
        if !was_retiring {
            tracing::warn!(isolate = %self.heap_id, slot = self.id, reason, "isolate condemned");
        }
        reclaim.notify_one();
        true
    }

    /// The node-wide identity of this slot's currently installed V8 heap.
    pub fn heap_id(&self) -> HeapId {
        self.heap_id
    }

    fn is_reusable(&self) -> bool {
        let load = self.observe();
        if !self.may_free() || load.cells != 0 {
            return false;
        }
        self.worker.try_lock().is_ok_and(|worker| worker.is_none())
    }
}

/// A request's claim on the isolate that ran its first turn.
pub struct Affiliation(Arc<Slot>);

impl Affiliation {
    pub fn slot(&self) -> &Arc<Slot> {
        &self.0
    }
}

impl Drop for Affiliation {
    fn drop(&mut self) {
        self.0.requests.fetch_sub(1, Ordering::Relaxed);
        // Exactly one admission waiter per freed slot: `notify_one` hands
        // the capacity to a single parked request, where waking them all
        // would stampede `admit` on every release.
        self.0.freed.notify_one();
        // The last request out of a retiring isolate is what lets it free.
        // Freeing here would drop a V8 isolate inside whatever turn dropped
        // this affiliation, so the pool's maintenance task does it.
        if self.0.is_retiring() {
            if let Some(reclaim) = &self.0.reclaim {
                reclaim.notify_one();
            }
        }
    }
}

/// An exported capability's claim on a stateless heap; see
/// [`Slot::pin_export`].
pub(crate) struct ExportPin(Arc<Slot>);

impl Drop for ExportPin {
    fn drop(&mut self) {
        self.0.export_pins.fetch_sub(1, Ordering::Relaxed);
        if self.0.is_retiring() {
            if let Some(reclaim) = &self.0.reclaim {
                reclaim.notify_one();
            }
        }
    }
}

/// A cell's claim on the isolate that holds its realm.
///
/// The counterpart of [`Affiliation`], and the difference between them is
/// the whole reason both exist: an affiliation lasts one request, a
/// residency lasts until the cell is evicted or moves node.
pub struct Residency {
    slot: Arc<Slot>,
    max_cells: usize,
    adopted: bool,
}

impl Residency {
    pub fn slot(&self) -> &Arc<Slot> {
        &self.slot
    }

    /// Open a reserved cell's storage and return its residency with its alarm snapshot.
    /// Collection follows the last completed adoption, because reservation
    /// order can differ from the order in which activation futures resume.
    pub(crate) async fn adopt(
        mut self,
        cell: &str,
        storage: js::CellStorage<'_>,
    ) -> Result<(Self, celld_logic::wake::AlarmSnapshot)> {
        anyhow::ensure!(!self.adopted, "cell residency already adopted");
        let slot = self.slot.clone();
        let alarm = slot
            .turn(|worker| -> Result<celld_logic::wake::AlarmSnapshot> {
                let alarm = worker.own_cell(cell, Some(storage))?;
                // There is no await between adoption and accounting. Cancellation
                // before this turn drops only the reservation; afterward the
                // residency owns both counters, including on an error unwind.
                self.adopted = true;
                let adopted = slot.adopted_cells.fetch_add(1, Ordering::Relaxed) + 1;
                debug_assert!(adopted <= self.max_cells);
                if adopted == self.max_cells {
                    worker.settle_heap();
                }
                Ok(alarm)
            })
            .await?;
        Ok((self, alarm))
    }
}

impl Drop for Residency {
    fn drop(&mut self) {
        if self.adopted {
            self.slot.adopted_cells.fetch_sub(1, Ordering::Relaxed);
        }
        self.slot.cells.fetch_sub(1, Ordering::Relaxed);
    }
}

type Build = Box<dyn Fn() -> Result<js::Worker> + Send + Sync>;

pub struct Pool {
    slots: RwLock<Vec<Arc<Slot>>>,
    limits: PoolLimits,
    build: Build,
    freed: Arc<tokio::sync::Notify>,
    /// Rung by a condemnation and by the last request out of a retiring
    /// isolate. See [`Pool::reclaim_bell`].
    reclaim: Arc<tokio::sync::Notify>,
    admission_wait: std::time::Duration,
    /// The whole pool belongs to a superseded generation. An isolate grown
    /// after this is set starts out retiring: a placement that snapshotted
    /// the old generation just before the flip can still land, but nothing
    /// it builds outlives the work it was built for.
    retired: AtomicBool,
    /// Keeps admission and cell placement from racing isolate retirement.
    /// Stateless admission takes a shared guard, while maintenance and cell
    /// placement take the exclusive guard.
    maintenance: RwLock<()>,
}

impl Pool {
    pub fn new(limits: PoolLimits, admission_wait: std::time::Duration, build: Build) -> Self {
        Pool {
            slots: RwLock::new(Vec::new()),
            limits,
            build,
            freed: Arc::new(tokio::sync::Notify::new()),
            reclaim: Arc::new(tokio::sync::Notify::new()),
            admission_wait,
            retired: AtomicBool::new(false),
            maintenance: RwLock::new(()),
        }
    }

    fn load(&self) -> PoolLoad {
        let slots = self.slots.read().expect("pool poisoned");
        PoolLoad {
            isolates: slots.iter().map(|s| s.observe()).collect(),
            limits: self.limits,
        }
    }

    pub fn len(&self) -> usize {
        self.slots.read().expect("pool poisoned").len()
    }

    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    fn get(&self, id: IsolateId) -> Arc<Slot> {
        self.slots.read().expect("pool poisoned")[id].clone()
    }

    /// Build an isolate and admit it to the pool.
    ///
    /// The isolate is constructed before the lock is taken: loading a script
    /// runs JS and can take milliseconds, and holding the pool lock across it
    /// would stall every other placement on the node.
    /// Build an isolate, unless a capped pool reached `cap` while this one
    /// was being built. Cell placement passes no cap because node memory is
    /// bounded before placement and its per-isolate limit must remain exact.
    ///
    /// `cap` is re-checked under the write lock because admission decides
    /// against a snapshot it does not hold. Without the re-check every
    /// request that saw the same pre-growth snapshot grows, so a cap of two
    /// produced sixteen isolates under load — the breach scaled with offered
    /// concurrency, and the configured limit was met only when serialised.
    fn grow(&self, cap: Option<usize>) -> Result<Arc<Slot>> {
        let worker = (self.build)()?;
        let mut slots = self.slots.write().expect("pool poisoned");
        let live = slots.iter().filter(|slot| !slot.is_retiring()).count();
        if cap.is_some_and(|cap| live >= cap) {
            if let Some(slot) = slots.iter().find(|slot| !slot.is_retiring()) {
                return Ok(slot.clone());
            }
        }
        // A freed slot has no worker, work, affiliations, or cells. Reuse its
        // stable index so placement scans scale with the current pool rather
        // than with every isolate created during the process lifetime.
        let reusable = slots.iter().position(|slot| slot.is_reusable());
        let id = reusable.unwrap_or(slots.len());
        let heap_id = next_heap_id();
        let slot = Arc::new_cyclic(|me| Slot {
            me: me.clone(),
            id,
            heap_id,
            worker: tokio::sync::Mutex::new(Some(worker)),
            turn_scheduler: TurnScheduler::default(),
            queue_producers: Mutex::new(std::collections::HashMap::new()),
            turns: AtomicUsize::new(0),
            requests: AtomicUsize::new(0),
            export_pins: AtomicUsize::new(0),
            freed: self.freed.clone(),
            reclaim: Some(self.reclaim.clone()),
            loaded_worker: false,
            cells: AtomicUsize::new(0),
            adopted_cells: AtomicUsize::new(0),
            retiring: AtomicBool::new(self.retired.load(Ordering::Relaxed)),
            capabilities_closed: AtomicBool::new(self.retired.load(Ordering::Relaxed)),
            lifecycle: Mutex::new(()),
            #[cfg(celld_internal_tests)]
            turn_observations: Mutex::new(Vec::new()),
        });
        if let Some(id) = reusable {
            slots[id] = slot.clone();
        } else {
            slots.push(slot.clone());
        }
        tracing::info!(isolate = %heap_id, slot = id, total = slots.len(), "isolate started");
        Ok(slot)
    }

    fn resolve(&self, placement: Placement, cap: Option<usize>) -> Result<Arc<Slot>> {
        match placement {
            Placement::Existing(id) => Ok(self.get(id)),
            Placement::Grow => self.grow(cap),
        }
    }

    /// Build one isolate up front.
    ///
    /// The pool is otherwise lazy, and an idle node holding no isolates is the
    /// point. But the first isolate is built at startup for two reasons that
    /// laziness cannot serve: a node whose script does not load must fail
    /// *then*, not once per request forever after; and compiling the script
    /// inside the first request adds its whole cost to that request's latency,
    /// which a startup probe reads as a node that never came up.
    pub fn warm(&self) -> Result<()> {
        self.grow(Some(self.limits.max_stateless))?;
        Ok(())
    }

    /// Take a stateless request, or refuse it.
    ///
    /// One call against one snapshot: admission and placement are the same
    /// decision, so the node cannot admit a request it then fails to place.
    pub fn admit(&self, shedding: bool) -> Result<Affiliation, AdmitError> {
        // A configured request ceiling must remain exact under concurrent
        // admission, so serialize the check and reservation only in that
        // mode. The default unbounded path keeps concurrent shared access.
        if self.limits.max_requests.is_some() {
            let _maintenance = self.maintenance.write().expect("pool poisoned");
            self.admit_locked(shedding)
        } else {
            let _maintenance = self.maintenance.read().expect("pool poisoned");
            self.admit_locked(shedding)
        }
    }

    fn admit_locked(&self, shedding: bool) -> Result<Affiliation, AdmitError> {
        let placement = celld_logic::isolate::admit(&self.load(), shedding)?;
        self.resolve(placement, Some(self.limits.max_stateless))
            .map(|slot| slot.affiliate())
            .map_err(AdmitError::Build)
    }

    /// [`admit`](Self::admit), except a request that finds the node full
    /// waits — bounded — for a slot instead of being refused at once.
    ///
    /// The wait is the middle gear between "admit" and "refuse". At
    /// overload the parse-and-503 path costs about half a served request,
    /// so a node refusing 200k times a second spends its cores saying no.
    /// A parked waiter costs nothing until an `Affiliation` drop hands it
    /// the slot, and the excess load queues in kernel socket buffers
    /// behind connections nobody is reading. `NodePressured` still
    /// refuses at once: pressure means give resources back, not hold
    /// callers.
    pub async fn admit_or_wait(&self, shedding: bool) -> Result<Affiliation, AdmitError> {
        let deadline_ms =
            crate::asyncrt::mono_ms().saturating_add(self.admission_wait.as_millis() as u64);
        loop {
            // Armed before the check: a slot freed between a failed admit
            // and the park would otherwise be a lost wakeup.
            let freed = self.freed.notified();
            match self.admit(shedding) {
                Err(AdmitError::Refused(Refusal::NodeFull)) => {
                    tokio::pin!(freed);
                    // A freed slot before the deadline: both arms end the
                    // wait, so declaring the order costs nothing and makes
                    // the branch replayable. Priority to the wakeup, because
                    // a slot that freed in the same instant the deadline
                    // expired is a slot the caller can have.
                    crate::asyncrt::select_biased! {
                        "a slot freed in the same instant as the deadline goes to the caller";
                        _ = &mut freed => {},
                        _ = crate::asyncrt::sleep_until(deadline_ms) => {
                            return Err(AdmitError::Refused(Refusal::NodeFull));
                        }
                    }
                }
                other => return other,
            }
        }
    }

    /// Give a cell a home, building an isolate if every one is full.
    ///
    /// The counterpart of [`admit`](Self::admit) and deliberately the same
    /// shape: one call against one snapshot. It cannot refuse — by the time
    /// a cell needs a realm, ownership has already agreed the node serves
    /// it, so `celld_logic::isolate::place_cell` always answers.
    pub fn place_cell(&self) -> Result<Residency> {
        let _maintenance = self.maintenance.write().expect("pool poisoned");
        let placement = celld_logic::isolate::place_cell(&self.load());
        // Cell isolates have no arbitrary total cap. The resident-cell and
        // RSS limits bound node memory before placement. The lock keeps this
        // reservation exact and prevents maintenance from retiring the slot.
        Ok(self.resolve(placement, None)?.house(self.limits.max_cells))
    }

    /// One maintenance pass: give back an isolate the pool no longer needs,
    /// and free whatever has finished draining.
    ///
    /// Without this the pool only grows. A burst takes it to `max_stateless`
    /// and every one of those V8 heaps is held for the life of the process,
    /// which is the whole reason `celld_logic::isolate::retire` exists —
    /// and, until this existed, the reason it was dead code hiding a leak.
    ///
    /// Retire at most one isolate. Stateless pools use this paced maintenance
    /// so a quiet interval does not discard every warm compiled Worker.
    pub fn reap(&self) {
        // Maintenance runs on a Tokio worker. Skip this pass when a blocking
        // cell start is compiling an isolate instead of blocking the worker.
        let Ok(_maintenance) = self.maintenance.try_write() else {
            return;
        };
        self.retire_one();
        self.free_retired();
    }

    /// The bell a maintenance task awaits to call
    /// [`free_drained`](Self::free_drained) between reap ticks.
    pub(crate) fn reclaim_bell(&self) -> Arc<tokio::sync::Notify> {
        self.reclaim.clone()
    }

    /// Free every retiring isolate that has drained, and retire nothing.
    /// Returns `false` when admission or cell placement holds the pool, so
    /// the caller retries rather than let the heap wait for the next reap.
    ///
    /// The guard is the one `reap` takes, for the same race: an admission
    /// that snapshotted this slot before it began retiring can still
    /// affiliate to it, and `may_free` only sees that request once the
    /// admission has released the guard.
    pub(crate) fn free_drained(&self) -> bool {
        let Ok(_maintenance) = self.maintenance.try_write() else {
            return false;
        };
        self.free_retired();
        true
    }

    /// Retire every empty isolate. Cell pools use this after eviction because
    /// an empty cell heap carries no warm request capacity worth preserving.
    pub fn reap_empty(&self) {
        let Ok(_maintenance) = self.maintenance.try_write() else {
            tracing::debug!(
                event = "isolate_reap_skipped",
                "a cell start holds the pool; empty isolates wait for the next pass"
            );
            return;
        };
        while self.retire_one() {}
        self.free_retired();
    }

    /// Retire every isolate, housed or not: the pool belongs to a superseded
    /// application generation and must take no new work. Stateless slots
    /// free as their affiliations drop; a slot hosting cells frees once the
    /// last of them has moved to a newer generation, which `may_free`
    /// enforces by refusing a housed isolate.
    pub fn retire_all(&self) {
        let _maintenance = self.maintenance.write().expect("pool poisoned");
        self.retired.store(true, Ordering::Relaxed);
        for slot in self.slots.read().expect("pool poisoned").iter() {
            if !slot.close_capabilities() {
                tracing::info!(isolate = %slot.heap_id, slot = slot.id, "isolate retiring");
            }
        }
        // A closed heap dispatches no capability again, so its exports and
        // their pins go before the drained heaps are freed.
        crate::capability::drop_closed_exports();
        self.free_retired();
    }

    /// Whether every isolate this pool ever built has been freed. True for a
    /// pool that never grew, so a generation whose scripts took no traffic
    /// drains at once.
    pub fn is_drained(&self) -> bool {
        self.slots
            .read()
            .expect("pool poisoned")
            .iter()
            .all(|slot| slot.worker.try_lock().is_ok_and(|worker| worker.is_none()))
    }

    fn retire_one(&self) -> bool {
        let Some(id) = celld_logic::isolate::retire(&self.load()) else {
            return false;
        };
        let slot = self.get(id);
        if !slot.retiring.swap(true, Ordering::Relaxed) {
            tracing::info!(isolate = %slot.heap_id, slot = id, "isolate retiring");
        }
        true
    }

    fn free_retired(&self) {
        // A retiring isolate takes no new work, so once its counters reach
        // zero nothing can enter it again and its heap can go. `try_lock`
        // rather than blocking: if a turn holds it, it is not drained and
        // this pass has nothing to do.
        for slot in self.slots.read().expect("pool poisoned").iter() {
            if !slot.may_free() {
                continue;
            }
            let Ok(mut worker) = slot.worker.try_lock() else {
                continue;
            };
            // A live-capability admission can affiliate under this same
            // lock after the first snapshot. Never free that admitted heap.
            if !slot.may_free() {
                continue;
            }
            if worker.take().is_some() {
                tracing::info!(isolate = %slot.heap_id, slot = slot.id, "isolate freed");
            }
        }
    }

    /// Return the current live-isolate count.
    pub fn live(&self) -> usize {
        self.slots
            .read()
            .expect("pool poisoned")
            .iter()
            .filter(|slot| !slot.is_retiring())
            .count()
    }

    /// What the pool holds right now, for `/state`.
    ///
    /// The count an operator of a hibernation-heavy node needs and could
    /// not get: a dormant cell keeps about 160 KB more than its own records
    /// explain (GCE, 2026-09-03), and the one O(cells) structure
    /// that fits is the isolate. `live_empty` is what `reap_empty` retires
    /// on its next pass and `retiring` is what `may_free` still refuses, so
    /// either staying positive across passes names the leak.
    pub fn census(&self) -> PoolCensus {
        let mut census = PoolCensus::default();
        for slot in self.slots.read().expect("pool poisoned").iter() {
            let load = slot.observe();
            census.cells += load.cells;
            census.requests += load.requests;
            census.turns += load.turns;
            census.exports += load.exports;
            // A heap is gone once its worker was taken. A worker a turn
            // holds right now is installed, so a failed `try_lock` counts
            // as a heap and never as freed; its size is unknown this pass.
            // Holding the guard is the permit a turn holds, which is what
            // makes the V8 lock inside `heap_bytes` uncontended.
            match slot.worker.try_lock() {
                Ok(worker) if worker.is_none() => {
                    census.freed += 1;
                    continue;
                }
                Ok(worker) => {
                    if let Some(heap) = worker.as_ref().and_then(js::Worker::heap_bytes) {
                        census.heap_bytes += heap.physical;
                        census.external_bytes += heap.external;
                    }
                }
                Err(_) => {}
            }
            if load.retiring {
                census.retiring += 1;
            } else {
                census.live += 1;
                if load.cells == 0 {
                    census.live_empty += 1;
                }
            }
        }
        census
    }
}

/// The property the whole design rests on: an isolate and everything hanging
/// off it can be reached from any tokio worker. This is what `v8::Locker` and
/// `Send` Globals buy (denoland/rusty_v8#2044, #2045); without them
/// `js::Worker` would not be `Send` and the pool could not exist.
///
/// A compile-time check rather than a comment, because losing it would show
/// up as a confusing error somewhere far away.
const _: fn() = || {
    fn assert_send_sync<T: Send + Sync>() {}
    assert_send_sync::<Pool>();
    assert_send_sync::<Slot>();
    assert_send_sync::<Affiliation>();
};

#[cfg(test)]
#[path = "../../tests/regressions/OR1-02/native.rs"]
mod or1_02;

#[cfg(test)]
#[path = "../../tests/regressions/OR2-02/native.rs"]
mod or2_02;

#[cfg(test)]
mod capability_drain_tests {
    use super::*;

    pub(super) fn pool() -> Pool {
        js::Engine::init();
        Pool::new(
            PoolLimits {
                grow_at: 2,
                shrink_under: 1,
                max_stateless: 4,
                max_requests: None,
                max_cells: 8,
            },
            std::time::Duration::from_secs(1),
            Box::new(|| {
                js::Worker::load_config(Arc::new(js::WorkerConfig::new(js::WorkerConfigOptions {
                    src: "export default {fetch(){return new Response('ok')}}".into(),
                    script_name: "capability-drain-test".into(),
                    do_classes: vec![],
                    bindings: vec![],
                    r2_bindings: vec![],
                    d1_bindings: vec![],
                    kv_bindings: vec![],
                    queue_bindings: vec![],
                    queue_consumers: vec![],
                    workflow_bindings: vec![],
                    vars: vec![],
                    node: String::new(),
                    modules: vec![],
                    compat: Default::default(),
                })))
            }),
        )
    }

    #[test]
    fn capability_continuations_drain_without_reopening_invalidated_heaps() {
        tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap()
            .block_on(async {
                let pool = pool();
                let slot = pool.grow(None).unwrap();
                let request = slot.affiliate();
                let export = |token: &str| -> crate::capability::Route {
                    serde_json::from_str(
                        &crate::capability::export(slot.clone(), token.into(), None, None, None)
                            .unwrap(),
                    )
                    .unwrap()
                };
                // C6-01: a heap that exports a live capability is never chosen
                // for retirement; once the holder releases it, it may be.
                // (OR1-02: an export taken while draining returns it to service.)
                let pinned = export("pinned-target");
                pool.reap();
                assert!(!slot.is_retiring(), "an exporting heap stays live");
                assert_eq!(pool.live(), 1);
                slot.turn(|_| crate::capability::revoke(&pinned))
                    .await
                    .unwrap();
                pool.reap();
                assert!(slot.is_retiring());
                // OR1-02: a request still draining the heap exports. The heap
                // returns to service instead of staying retiring and pinned.
                let route = export("test-target");
                assert!(!slot.is_retiring(), "an export during drain un-retires the heap");
                assert_eq!(pool.live(), 1);
                pool.reap();
                assert!(!slot.is_retiring(), "it is not retired again while exporting");
                slot.turn(|_| crate::capability::revoke(&route))
                    .await
                    .unwrap();
                pool.reap();
                assert!(slot.is_retiring());
                assert_eq!(pool.live(), 0, "draining heap is excluded from placement");
                let continuation = slot
                    .try_affiliate_capability()
                    .await
                    .expect("live request may receive its callback");
                drop(request);
                pool.free_drained();
                assert!(
                    slot.worker.lock().await.is_some(),
                    "continuation holds its heap during dispatch"
                );
                drop(continuation);
                pool.free_drained();
                assert!(slot.worker.lock().await.is_none());
                assert!(
                    slot.try_affiliate_capability().await.is_none(),
                    "freed heap cannot be revived"
                );

                let condemned = pool.grow(None).unwrap();
                let live = condemned.affiliate();
                assert!(condemned.condemn("test fatal guest failure"));
                assert!(condemned.worker.lock().await.is_some());
                assert!(condemned.try_affiliate_capability().await.is_none());
                drop(live);
                pool.free_drained();

                let draining = pool.grow(None).unwrap();
                let live = draining.affiliate();
                let route: crate::capability::Route = serde_json::from_str(
                    &crate::capability::export(
                        draining.clone(),
                        "pending-target".into(),
                        None,
                        None,
                        None,
                    )
                    .unwrap(),
                )
                .unwrap();
                let admitted = draining.try_affiliate_capability().await.unwrap();
                pool.retire_all();
                assert!(draining.try_affiliate_capability().await.is_none());
                let rejected = draining
                    .turn(|_| crate::capability::validate(&route))
                    .await
                    .unwrap_err();
                assert!(rejected.to_string().contains("invalidated"), "{rejected}");
                drop(admitted);
                drop(live);
                pool.free_drained();
                let late = pool.grow(None).unwrap();
                assert!(late.is_retiring());
                assert!(
                    late.try_affiliate_capability().await.is_none(),
                    "a late placement in a retired pool stays invalidated"
                );
                pool.free_drained();
            });
    }
}

#[cfg(test)]
mod turn_scheduler_tests {
    use super::*;
    use std::future::Future;
    use std::task::Context;
    use std::task::Poll;

    fn poll_once<F: Future>(future: std::pin::Pin<&mut F>) -> Poll<F::Output> {
        future.poll(&mut Context::from_waker(std::task::Waker::noop()))
    }

    /// A queued turn granted and then dropped before it ran — an aborted
    /// capability drive, a cleared op — must hand the isolate on, as
    /// workerd's `~AsyncLockWaiter` does. Before, the grant made its lane
    /// current with no permit to release it, and the next turn on the
    /// isolate waited forever (Tunez Celld 4: planet-2 froze with 134
    /// queued turns and no thread in JavaScript).
    #[test]
    fn a_granted_waiter_dropped_before_it_runs_passes_the_turn_on() {
        tokio::runtime::Builder::new_current_thread()
            .enable_time()
            .build()
            .unwrap()
            .block_on(async {
                let scheduler = TurnScheduler::default();
                let holder = scheduler.acquire(TurnLane::Stateless).await;
                let mut granted = Box::pin(scheduler.acquire(TurnLane::Cell("cell".into())));
                assert!(
                    poll_once(granted.as_mut()).is_pending(),
                    "queued behind the holder"
                );
                // The holder leaves: `release` sends the grant to the queued
                // waiter, which has not been polled since.
                drop(holder);
                drop(granted);
                let next = tokio::time::timeout(
                    std::time::Duration::from_secs(1),
                    scheduler.acquire(TurnLane::Stateless),
                )
                .await
                .expect("a dropped grant strands the isolate");
                drop(next);
            });
    }

    /// The same for a waiter dropped before its grant: `release` skips its
    /// closed sender and grants the next lane.
    #[test]
    fn a_waiter_dropped_before_its_grant_is_skipped() {
        tokio::runtime::Builder::new_current_thread()
            .enable_time()
            .build()
            .unwrap()
            .block_on(async {
                let scheduler = TurnScheduler::default();
                let holder = scheduler.acquire(TurnLane::Stateless).await;
                let mut dropped = Box::pin(scheduler.acquire(TurnLane::Cell("a".into())));
                assert!(poll_once(dropped.as_mut()).is_pending());
                let mut waiting = Box::pin(scheduler.acquire(TurnLane::Cell("b".into())));
                assert!(poll_once(waiting.as_mut()).is_pending());
                drop(dropped);
                drop(holder);
                tokio::time::timeout(std::time::Duration::from_secs(1), waiting)
                    .await
                    .expect("the next lane is granted");
            });
    }
}
