//! Synthetic, finite, hand-authored schedules over the frozen production State.
//! All mutations enter on_event; emitted operation identities drive completions.
//! No networking, mock decision core, compiler invocation, or runtime process here.
use celld_logic::*;
use std::collections::{BTreeMap, BTreeSet};

fn config(resident: usize, activations: usize, leases: bool) -> Config {
    Config {
        max_resident: resident,
        max_activations: activations,
        max_evictions: 2,
        max_releases: 2,
        max_outbound_websockets: 2,
        ownership_on_evict: OwnershipOnEvict::Sticky,
        require_node_lease: leases,
        peer_protocol: 1,
        operation_deadline_ms: Some(50),
        owner_log_recovery_backoff_ms: 10,
        owner_log_recovery_attempts: 2,
        alarm_resident_ms: 0,
        idle_evict_ms: None,
        pressure: pressure::PressureConfig::default(),
    }
}
struct H {
    s: State,
    now: u64,
    count: usize,
    cap: usize,
    slots: usize,
    pending: BTreeSet<u64>,
    cancelled: BTreeSet<u64>,
    completed: BTreeMap<u64, Result<Route, RequestError>>,
    cells: BTreeSet<String>,
}
impl H {
    fn new(cap: usize, slots: usize) -> Self {
        Self::with_config(config(cap, slots, false))
    }
    fn with_config(c: Config) -> Self {
        Self {
            s: State::new("fixture", c),
            now: 100,
            count: 0,
            cap: c.max_resident,
            slots: c.max_activations,
            pending: BTreeSet::new(),
            cancelled: BTreeSet::new(),
            completed: BTreeMap::new(),
            cells: BTreeSet::new(),
        }
    }
    fn leased(cap: usize, slots: usize) -> Self {
        let mut h = Self::with_config(config(cap, slots, true));
        let e = h.step(Event::StartNodeLease {
            now_ms: 100,
            now_mono_ms: 100,
            spec: NodeLeaseSpec {
                addr: "fixture.invalid:0".into(),
                peer_protocol: 1,
                generation: "self-generation".into(),
                resume_generation: None,
                ttl_ms: 10000,
            },
        });
        let read_op = op(&e, "self-read", "");
        let e = h.step(Event::SelfNodeLeaseRead {
            op: read_op,
            now_ms: 100,
            now_mono_ms: 100,
            result: Ok(None),
        });
        let cas_op = op(&e, "self-cas", "");
        h.step(Event::NodeLeaseCasCompleted {
            op: cas_op,
            now_mono_ms: 100,
            result: Ok(LeaseCasOutcome::Applied {
                etag: "self-lease".into(),
            }),
            stamped_log_state: None,
        });
        h.step(Event::LocalCellsRead { result: Ok(vec![]) });
        assert!(h.s.node_authoritative());
        h
    }
    fn step(&mut self, event: Event) -> Vec<Effect> {
        self.count += 1;
        assert!(self.count <= 120, "finite 120-event ceiling exceeded");
        match &event {
            Event::RequestAt { request, cell, .. }
            | Event::HandoffRequestAt { request, cell, .. }
            | Event::CapacityRequestAt { request, cell, .. } => {
                assert!(!self.completed.contains_key(request) && !self.cancelled.contains(request));
                self.pending.insert(*request);
                self.cells.insert(cell.clone());
            }
            Event::Cancel { request } => {
                self.pending.remove(request);
                self.cancelled.insert(*request);
            }
            _ => {}
        }
        println!("event {:03}: {:?}", self.count, event);
        let effects = on_event(&mut self.s, event);
        println!("effects {:03}: {:?}", self.count, effects);
        self.s
            .validate()
            .expect("production structural invariants at each event");
        assert!(self.s.occupied() <= self.cap);
        assert!(self.s.activating() <= self.slots);
        for effect in &effects {
            if let Effect::Complete { request, result } = effect {
                assert!(
                    !self.cancelled.contains(request),
                    "cancelled caller completed"
                );
                assert!(
                    self.pending.remove(request),
                    "unknown or already settled caller"
                );
                assert!(
                    self.completed.insert(*request, result.clone()).is_none(),
                    "double completion"
                );
            }
        }
        effects
    }
    fn req(&mut self, cell: &str, request: u64) -> Vec<Effect> {
        self.step(Event::RequestAt {
            request,
            cell: cell.into(),
            now_mono_ms: self.now,
        })
    }
    fn handoff(&mut self, cell: &str, request: u64) -> Vec<Effect> {
        self.step(Event::HandoffRequestAt {
            request,
            cell: cell.into(),
            now_ms: self.now,
            now_mono_ms: self.now,
        })
    }
    fn read(&mut self, op: u64, record: Option<OwnerRecord>) -> Vec<Effect> {
        self.step(Event::OwnerRead {
            op,
            now_ms: self.now,
            result: Ok(record),
        })
    }
    fn cas(&mut self, op: u64, result: Result<CasOutcome, Failure>) -> Vec<Effect> {
        self.step(Event::OwnerCasCompleted { op, result })
    }
    fn lease(&mut self, op: u64, record: Option<NodeLeaseRecord>) -> Vec<Effect> {
        self.step(Event::NodeLeaseRead {
            op,
            now_ms: self.now,
            result: Ok(record),
        })
    }
    fn fire(&mut self, timer: Timer, at: u64) -> Vec<Effect> {
        self.now = at;
        self.step(Event::TimerFired {
            timer,
            now_ms: at,
            now_mono_ms: at,
        })
    }
    fn finish(&mut self, request: u64) {
        self.step(Event::ActivityFinished { request });
    }
    fn cancel(&mut self, request: u64) {
        self.step(Event::Cancel { request });
    }
    fn local(&self, request: u64) {
        assert_eq!(self.completed.get(&request), Some(&Ok(Route::Local)));
    }
    fn failed(&self, request: u64, error: RequestError) {
        assert_eq!(self.completed.get(&request), Some(&Err(error)));
    }
    fn remote(&self, request: u64, node: &str, addr: &str, epoch: u64) {
        assert_eq!(
            self.completed.get(&request),
            Some(&Ok(Route::Remote {
                node: node.into(),
                addr: addr.into(),
                epoch,
                peer_protocol: 1
            }))
        );
    }
    fn resident(&mut self, restore: u64, cell: &str, epoch: u64) -> Vec<Effect> {
        let e = self.step(Event::RestoreCompleted {
            op: restore,
            result: Ok(RestoreOutcome {
                restored: epoch > 1,
                alarm: None,
            }),
        });
        let start = op(&e, "start", cell);
        let e = self.step(Event::RuntimeStarted {
            op: start,
            isolate: None,
            generation: 1,
            result: Ok(()),
        });
        let publish = op(&e, "publish", cell);
        let e = self.step(Event::Published {
            op: publish,
            result: Ok(()),
        });
        assert_eq!(self.s.phase(cell), Some(&Phase::Resident { epoch }));
        e
    }
    fn acquired(&mut self, cas: u64, cell: &str, epoch: u64) -> Vec<Effect> {
        let e = self.cas(cas, Ok(CasOutcome::Applied));
        self.resident(op(&e, "restore", cell), cell, epoch)
    }
    fn activate(&mut self, cell: &str, request: u64, prior: Option<OwnerRecord>) -> Vec<Effect> {
        let epoch = prior.as_ref().map_or(1, |p| p.epoch + 1);
        let e = self.req(cell, request);
        let read = op(&e, "read", cell);
        let e = self.read(read, prior);
        let cas = op(&e, "cas", cell);
        assert_claim(&e, cell, epoch);
        let e = self.acquired(cas, cell, epoch);
        self.local(request);
        e
    }
    fn done(self) {
        assert!(
            self.pending.is_empty(),
            "pending caller ledger: {:?}",
            self.pending
        );
        assert_eq!(self.s.activating(), 0, "activation permits leaked");
        assert!(self.s.activation_waiting().is_empty());
        assert!(self.s.waiting().is_empty());
        assert_eq!(self.s.evicting(), 0);
        assert_eq!(self.s.releasing(), 0);
        assert_eq!(self.s.adopting(), 0);
        for cell in &self.cells {
            assert!(!self.s.is_active(cell), "live activity remains on {cell}");
            assert!(
                matches!(
                    self.s.phase(cell),
                    Some(
                        Phase::Resident { .. }
                            | Phase::Dormant { .. }
                            | Phase::Remote { .. }
                            | Phase::Inactive
                    )
                ),
                "nonterminal phase on {cell}"
            );
        }
        self.s.validate().unwrap();
        println!(
            "terminal: {} events, {} completed, {} cancelled, no pending demand",
            self.count,
            self.completed.len(),
            self.cancelled.len()
        );
    }
}
fn record(node: Option<&str>, epoch: u64, tag: &str) -> OwnerRecord {
    OwnerRecord {
        node: node.map(str::to_string),
        epoch,
        etag: tag.into(),
    }
}
fn lease(node: &str, addr: &str, expires: u64, generation: &str) -> NodeLeaseRecord {
    NodeLeaseRecord {
        node: node.into(),
        addr: addr.into(),
        expires_ms: expires,
        peer_protocol: 1,
        generation: generation.into(),
        log_state: None,
        etag: format!("lease-{generation}"),
    }
}
fn peer(node: &str, sample: u64) -> CapacityPeer {
    CapacityPeer {
        node: node.into(),
        addr: format!("{node}.invalid:1"),
        expires_ms: 1000,
        peer_protocol: 1,
        sampled_ms: sample,
        owned_cells: Some(0),
        placement_weight: Some(1),
        bucket_format: Some(1),
        resident_cells: 0,
        host_websockets: 0,
        rss_bytes: 0,
        in_use_bytes: Some(0),
        pressured: false,
        memory_headroom: Some(true),
        restoring: 0,
        paced_handoff: true,
        rebalance_paused: false,
        draining: false,
    }
}
fn kind(effect: &Effect, wanted: &str, cell: &str) -> Option<u64> {
    match (wanted, effect) {
        ("self-read", Effect::ReadSelfNodeLease { op })
        | ("self-cas", Effect::CasNodeLease { op, .. }) => Some(*op),
        ("read", Effect::ReadOwner { op, cell: c })
        | ("lease", Effect::ReadNodeLease { op, cell: c, .. })
        | ("recover", Effect::RecoverNodeLog { op, cell: c, .. })
        | ("capacity", Effect::ReadCapacityPeers { op, cell: c })
        | ("cas", Effect::CasOwner { op, cell: c, .. })
        | ("restore", Effect::Restore { op, cell: c, .. })
        | ("start", Effect::StartRuntime { op, cell: c, .. })
        | ("publish", Effect::Publish { op, cell: c, .. })
        | ("ensure", Effect::EnsureDurable { op, cell: c, .. })
        | ("stop", Effect::StopRuntime { op, cell: c, .. })
        | ("release", Effect::ReleaseOwner { op, cell: c, .. })
            if c == cell =>
        {
            Some(*op)
        }
        _ => None,
    }
}
fn op(e: &[Effect], wanted: &str, cell: &str) -> u64 {
    let ops: Vec<_> = e.iter().filter_map(|v| kind(v, wanted, cell)).collect();
    assert_eq!(ops.len(), 1, "one {wanted} on {cell}: {e:?}");
    ops[0]
}
fn no_op(e: &[Effect], wanted: &str, cell: &str) {
    assert!(
        e.iter().all(|v| kind(v, wanted, cell).is_none()),
        "unexpected {wanted}: {e:?}"
    );
}
fn timer(e: &[Effect], wanted: &str, cell: &str) -> Timer {
    let timers: Vec<_> = e
        .iter()
        .filter_map(|v| match v {
            Effect::ScheduleTimer {
                timer: t @ Timer::QueuedActivation { cell: c, .. },
                ..
            } if wanted == "queue" && c == cell => Some(t.clone()),
            Effect::ScheduleTimer {
                timer: t @ Timer::OwnerLogRecoveryRetry { cell: c, .. },
                ..
            } if wanted == "recovery" && c == cell => Some(t.clone()),
            _ => None,
        })
        .collect();
    assert_eq!(timers.len(), 1);
    timers[0].clone()
}
fn assert_claim(e: &[Effect], cell: &str, epoch: u64) {
    assert!(e.iter().any(
        |v| matches!(v, Effect::CasOwner { cell: c, epoch: n, .. } if c == cell && *n == epoch)
    ));
}
fn restore_spec(e: &[Effect], cell: &str) -> RestoreSpec {
    e.iter()
        .find_map(|v| {
            if let Effect::Restore { cell: c, spec, .. } = v {
                (c == cell).then_some(spec.clone())
            } else {
                None
            }
        })
        .unwrap()
}
fn invalidate(h: &mut H, cell: &str, node: &str, epoch: u64) -> Vec<Effect> {
    h.step(Event::InvalidateRemote {
        cell: cell.into(),
        node: node.into(),
        epoch,
    })
}
fn deadline(e: &[Effect], op: u64) -> Timer {
    e.iter()
        .find_map(|v| match v {
            Effect::ScheduleTimer {
                timer: t @ Timer::OperationDeadline { op: p },
                ..
            } if *p == op => Some(t.clone()),
            _ => None,
        })
        .expect("deadline emitted for the captured operation")
}

#[test]
fn n001_claim_cohort_survives_initiator_cancel() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let read = op(&e, "read", "a");
    let e = h.req("a", 2);
    no_op(&e, "read", "a");
    h.cancel(1);
    let e = h.read(read, None);
    let cas = op(&e, "cas", "a");
    let e = h.req("a", 3);
    no_op(&e, "cas", "a");
    h.acquired(cas, "a", 1);
    h.local(2);
    h.local(3);
    assert_eq!(h.s.presence_snapshot().activity.acquired, 1);
    h.finish(3);
    h.finish(2);
    h.done();
}

#[test]
fn n002_parallel_claims_complete_in_reverse_order() {
    let mut h = H::new(2, 2);
    let e = h.req("a", 1);
    let a = op(&e, "read", "a");
    let e = h.req("b", 2);
    let b = op(&e, "read", "b");
    assert_ne!(a, b);
    let e = h.read(a, Some(record(None, 8, "a8")));
    let a = op(&e, "cas", "a");
    let e = h.read(b, None);
    let b = op(&e, "cas", "b");
    assert_ne!(a, b);
    h.acquired(b, "b", 1);
    h.local(2);
    assert!(!h.completed.contains_key(&1));
    assert!(matches!(h.s.phase("a"), Some(Phase::Acquiring { .. })));
    h.acquired(a, "a", 9);
    h.local(1);
    h.finish(1);
    h.finish(2);
    h.done();
}

#[test]
fn n003_rejected_claim_routes_whole_cohort_to_winner() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let cas = op(&e, "cas", "a");
    h.req("a", 2);
    let e = h.cas(cas, Ok(CasOutcome::Rejected));
    let reread = op(&e, "read", "a");
    let e = h.read(reread, Some(record(Some("peer"), 4, "won4")));
    let e = h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "peer.invalid:1", 500, "p1")),
    );
    no_op(&e, "restore", "a");
    h.remote(1, "peer", "peer.invalid:1", 4);
    h.remote(2, "peer", "peer.invalid:1", 4);
    assert_eq!(h.s.occupied(), 0);
    h.done();
}

#[test]
fn n004_conflict_restarts_from_new_released_epoch() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(None, 2, "r2")));
    let old = op(&e, "cas", "a");
    assert_claim(&e, "a", 3);
    let e = h.cas(old, Ok(CasOutcome::Rejected));
    let e = h.read(op(&e, "read", "a"), Some(record(None, 7, "r7")));
    let new = op(&e, "cas", "a");
    assert_claim(&e, "a", 8);
    assert!(h.cas(old, Ok(CasOutcome::Applied)).is_empty());
    assert!(
        matches!(h.s.phase("a"), Some(Phase::Acquiring { op, claim, .. }) if *op == new && claim.guard == CasGuard::Match("r7".into()))
    );
    h.acquired(new, "a", 8);
    h.local(1);
    h.finish(1);
    h.done();
}

#[test]
fn n005_ambiguous_takeover_readback_preserves_displaced_owner() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 6, "dead6")));
    let e = h.lease(op(&e, "lease", "a"), None);
    let cas = op(&e, "cas", "a");
    let e = h.cas(cas, Err(Failure::Ambiguous));
    let reread = op(&e, "read", "a");
    let e = h.read(reread, Some(record(Some("fixture"), 7, "landed7")));
    no_op(&e, "cas", "a");
    let spec = restore_spec(&e, "a");
    assert_eq!(spec.prior.as_deref(), Some("dead"));
    assert!(spec.took_over);
    assert!(!spec.fresh);
    assert_eq!(spec.epoch, 7);
    h.resident(op(&e, "restore", "a"), "a", 7);
    h.local(1);
    assert!(h.cas(cas, Ok(CasOutcome::Applied)).is_empty());
    h.finish(1);
    h.done();
}

#[test]
fn n006_ambiguous_claim_different_self_epoch_requires_new_cas() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let e = h.cas(op(&e, "cas", "a"), Err(Failure::Ambiguous));
    let e = h.read(
        op(&e, "read", "a"),
        Some(record(Some("fixture"), 11, "self11")),
    );
    no_op(&e, "restore", "a");
    assert_claim(&e, "a", 12);
    assert!(
        matches!(h.s.phase("a"), Some(Phase::Acquiring { claim, .. }) if claim.reconciles == 1)
    );
    h.acquired(op(&e, "cas", "a"), "a", 12);
    h.local(1);
    h.finish(1);
    h.done();
}

#[test]
fn n007_persistent_ambiguous_store_is_bounded_and_recoverable() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let e = h.cas(op(&e, "cas", "a"), Err(Failure::Ambiguous));
    let e = h.read(op(&e, "read", "a"), None);
    assert!(
        matches!(h.s.phase("a"), Some(Phase::Acquiring { claim, .. }) if claim.reconciles == 1)
    );
    let e = h.cas(op(&e, "cas", "a"), Err(Failure::Ambiguous));
    let e = h.read(op(&e, "read", "a"), None);
    assert!(
        matches!(h.s.phase("a"), Some(Phase::Acquiring { claim, .. }) if claim.reconciles == 2)
    );
    let e = h.cas(op(&e, "cas", "a"), Err(Failure::Ambiguous));
    let e = h.read(op(&e, "read", "a"), None);
    assert_eq!(MAX_ACQUIRE_RECONCILES, 3);
    assert!(
        matches!(h.s.phase("a"), Some(Phase::Acquiring { claim, .. }) if claim.reconciles == 3)
    );
    let e = h.cas(op(&e, "cas", "a"), Err(Failure::Ambiguous));
    no_op(&e, "read", "a");
    h.failed(1, RequestError::AcquireFailed);
    assert_eq!(h.s.phase("a"), Some(&Phase::Inactive));
    assert_eq!(h.s.activating(), 0);
    h.activate("a", 2, Some(record(Some("fixture"), 1, "uncertain-landed")));
    h.finish(2);
    h.done();
}

#[test]
fn n008_definite_acquire_failure_returns_permit_to_next_cell() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let cas = op(&e, "cas", "a");
    h.req("b", 2);
    assert_eq!(h.s.phase("b"), Some(&Phase::WaitingActivation));
    let e = h.cas(cas, Err(Failure::Definite));
    h.failed(1, RequestError::AcquireFailed);
    let e = h.read(op(&e, "read", "b"), None);
    h.acquired(op(&e, "cas", "b"), "b", 1);
    h.local(2);
    h.finish(2);
    h.done();
}

#[test]
fn n009_owner_read_timeout_cannot_complete_replacement_attempt() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let old = op(&e, "read", "a");
    let t = deadline(&e, old);
    h.fire(t, 150);
    h.failed(1, RequestError::ResolveFailed);
    let e = h.req("a", 2);
    let new = op(&e, "read", "a");
    assert_ne!(old, new);
    assert!(h
        .read(old, Some(record(Some("peer"), 99, "late")))
        .is_empty());
    assert_eq!(h.s.phase("a"), Some(&Phase::ReadingOwner { op: new }));
    let e = h.read(new, None);
    h.acquired(op(&e, "cas", "a"), "a", 1);
    h.local(2);
    h.finish(2);
    h.done();
}

#[test]
fn n010_reconciliation_read_timeout_unblocks_unrelated_activation() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let e = h.cas(op(&e, "cas", "a"), Err(Failure::Ambiguous));
    let read = op(&e, "read", "a");
    let t = deadline(&e, read);
    h.req("b", 2);
    let e = h.fire(t, 150);
    h.failed(1, RequestError::ResolveFailed);
    let b = op(&e, "read", "b");
    assert!(h
        .read(read, Some(record(Some("fixture"), 1, "late-landed")))
        .is_empty());
    let e = h.read(b, None);
    h.acquired(op(&e, "cas", "b"), "b", 1);
    h.local(2);
    h.finish(2);
    h.done();
}

#[test]
fn n011_cancelled_queue_generation_cannot_expire_rejoined_cell() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let a = op(&e, "read", "a");
    let e = h.req("b", 2);
    let old = timer(&e, "queue", "b");
    h.cancel(2);
    let e = h.req("b", 3);
    let new = timer(&e, "queue", "b");
    assert_ne!(old, new);
    assert!(h.fire(old, 150).is_empty());
    assert_eq!(h.s.phase("b"), Some(&Phase::WaitingActivation));
    let e = h.step(Event::OwnerRead {
        op: a,
        now_ms: 150,
        result: Err(Failure::Definite),
    });
    h.failed(1, RequestError::ResolveFailed);
    let e = h.read(op(&e, "read", "b"), None);
    h.acquired(op(&e, "cas", "b"), "b", 1);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn n012_partial_queue_cancellation_preserves_surviving_demand() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let a = op(&e, "read", "a");
    h.req("b", 2);
    let e = h.req("b", 3);
    no_op(&e, "read", "b");
    h.cancel(2);
    assert_eq!(h.s.activation_waiting(), vec!["b".to_string()]);
    let e = h.read(a, None);
    let e = h.acquired(op(&e, "cas", "a"), "a", 1);
    h.local(1);
    let e = h.read(op(&e, "read", "b"), None);
    h.acquired(op(&e, "cas", "b"), "b", 1);
    h.local(3);
    h.finish(1);
    h.finish(3);
    h.done();
}

#[test]
fn n013_expired_middle_waiter_does_not_strand_next_route() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let a = op(&e, "read", "a");
    let e = h.req("b", 2);
    let bt = timer(&e, "queue", "b");
    h.req("c", 3);
    h.fire(bt, 150);
    h.failed(2, RequestError::CapacityExhausted);
    assert_eq!(h.s.activation_waiting(), vec!["c".to_string()]);
    h.cancel(1);
    let e = h.read(a, None);
    no_op(&e, "cas", "a");
    let e = h.read(op(&e, "read", "c"), None);
    h.acquired(op(&e, "cas", "c"), "c", 1);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn n014_cancelled_capacity_claim_yields_freed_slot_to_survivor() {
    let mut h = H::new(1, 3);
    h.activate("a", 1, None);
    let e = h.req("b", 2);
    let e = h.read(op(&e, "read", "b"), None);
    no_op(&e, "cas", "b");
    let e = h.req("c", 3);
    h.read(op(&e, "read", "c"), None);
    assert_eq!(h.s.waiting(), vec!["b".to_string(), "c".to_string()]);
    h.cancel(2);
    assert_eq!(h.s.phase("b"), Some(&Phase::Inactive));
    let e = h.step(Event::ActivityFinished { request: 1 });
    let ensure = op(&e, "ensure", "a");
    let e = h.step(Event::DurabilityChecked {
        op: ensure,
        result: Ok(()),
    });
    let e = h.step(Event::RuntimeStopped {
        op: op(&e, "stop", "a"),
    });
    no_op(&e, "cas", "b");
    h.acquired(op(&e, "cas", "c"), "c", 1);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn n015_cancelled_queued_restore_keeps_acquired_epoch_dormant() {
    let mut h = H::new(1, 2);
    h.activate("a", 1, None);
    let e = h.handoff("b", 2);
    let e = h.read(op(&e, "read", "b"), Some(record(None, 4, "b4")));
    let cas = op(&e, "cas", "b");
    h.req("b", 3);
    let e = h.cas(cas, Ok(CasOutcome::Applied));
    no_op(&e, "restore", "b");
    assert_eq!(h.s.phase("b"), Some(&Phase::WaitingCapacity));
    h.cancel(2);
    h.cancel(3);
    assert_eq!(h.s.phase("b"), Some(&Phase::Dormant { epoch: 5 }));
    assert_eq!(h.s.accepted_epoch("b"), Some(5));
    let e = h.req("a", 4);
    no_op(&e, "read", "a");
    h.local(4);
    h.finish(4);
    h.finish(1);
    h.done();
}

#[test]
fn n016_ownership_only_handoff_admits_above_residency_cap() {
    let mut h = H::new(1, 2);
    h.activate("a", 1, None);
    let e = h.handoff("b", 2);
    let e = h.read(op(&e, "read", "b"), Some(record(None, 9, "b9")));
    assert!(matches!(
        h.s.phase("b"),
        Some(Phase::Acquiring { dormant: true, .. })
    ));
    assert_eq!(h.s.occupied(), 1);
    let e = h.cas(op(&e, "cas", "b"), Ok(CasOutcome::Applied));
    no_op(&e, "restore", "b");
    no_op(&e, "ensure", "a");
    assert_eq!(h.s.accepted_epoch("b"), Some(10));
    assert!(!h.completed.contains_key(&2));
    h.cancel(2);
    h.req("a", 3);
    h.local(3);
    h.finish(3);
    h.finish(1);
    h.done();
}

#[test]
fn n017_live_join_of_dormant_claim_waits_for_actual_capacity_release() {
    let mut h = H::new(1, 2);
    h.activate("a", 1, None);
    let e = h.handoff("b", 2);
    let e = h.read(op(&e, "read", "b"), None);
    let cas = op(&e, "cas", "b");
    h.req("b", 3);
    let e = h.cas(cas, Ok(CasOutcome::Applied));
    no_op(&e, "restore", "b");
    assert_eq!(h.s.phase("b"), Some(&Phase::WaitingCapacity));
    h.cancel(2);
    let e = h.step(Event::ActivityFinished { request: 1 });
    let e = h.step(Event::DurabilityChecked {
        op: op(&e, "ensure", "a"),
        result: Ok(()),
    });
    assert_eq!(h.s.occupied(), 1);
    assert!(!h.completed.contains_key(&3));
    let e = h.step(Event::RuntimeStopped {
        op: op(&e, "stop", "a"),
    });
    no_op(&e, "cas", "b");
    assert_eq!(restore_spec(&e, "b").epoch, 1);
    h.resident(op(&e, "restore", "b"), "b", 1);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn n018_cancelled_live_join_restores_ownership_only_landing() {
    let mut h = H::new(1, 1);
    let e = h.handoff("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(None, 4, "a4")));
    let cas = op(&e, "cas", "a");
    h.req("a", 2);
    h.cancel(2);
    let e = h.cas(cas, Ok(CasOutcome::Applied));
    no_op(&e, "restore", "a");
    assert_eq!(h.s.phase("a"), Some(&Phase::Dormant { epoch: 5 }));
    h.cancel(1);
    h.activate("a", 3, Some(record(Some("fixture"), 5, "a5")));
    assert_eq!(h.s.accepted_epoch("a"), Some(6));
    h.finish(3);
    h.done();
}

#[test]
fn n019_foreign_lease_error_fails_cohort_without_stealing_owner() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 3, "p3")));
    let e = h.step(Event::NodeLeaseRead {
        op: op(&e, "lease", "a"),
        now_ms: 100,
        result: Err(Failure::Ambiguous),
    });
    no_op(&e, "cas", "a");
    h.failed(1, RequestError::ResolveFailed);
    h.failed(2, RequestError::ResolveFailed);
    let e = h.req("a", 3);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 3, "p3")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "peer.invalid:1", 500, "p2")),
    );
    h.remote(3, "peer", "peer.invalid:1", 3);
    h.done();
}

#[test]
fn n020_delayed_live_snapshot_routes_once_then_refreshes_generation() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 3, "p3")));
    let read = op(&e, "lease", "a");
    // This snapshot was live at invocation 100; transport returns after its expiry 150.
    h.now = 200;
    h.req("a", 2);
    let e = h.lease(
        read,
        Some(lease("peer", "old.invalid:1", 150, "old-generation")),
    );
    no_op(&e, "cas", "a");
    h.remote(1, "peer", "old.invalid:1", 3);
    h.remote(2, "peer", "old.invalid:1", 3);
    let e = h.req("a", 3);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 3, "p3")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "new.invalid:2", 600, "new-generation")),
    );
    h.remote(3, "peer", "new.invalid:2", 3);
    assert_eq!(h.s.presence_snapshot().activity.remote_route_refreshes, 1);
    h.done();
}

#[test]
fn n021_old_epoch_invalidation_cannot_retire_newer_cached_owner() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 3, "p3")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "peer.invalid:1", 500, "g1")),
    );
    invalidate(&mut h, "a", "peer", 3);
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 4, "p4")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "peer.invalid:2", 500, "g2")),
    );
    invalidate(&mut h, "a", "peer", 3);
    let e = h.req("a", 3);
    no_op(&e, "read", "a");
    h.remote(3, "peer", "peer.invalid:2", 4);
    h.remote(1, "peer", "peer.invalid:1", 3);
    h.remote(2, "peer", "peer.invalid:2", 4);
    h.done();
}

#[test]
fn n022_old_node_invalidation_cannot_retire_same_epoch_capacity_route() {
    let mut h = H::leased(1, 1);
    h.activate("hot", 1, None);
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), None);
    h.step(Event::CapacityPeersRead {
        op: op(&e, "capacity", "a"),
        now_ms: 100,
        result: Ok(vec![peer("x", 10), peer("y", 10)]),
    });
    h.remote(2, "x", "x.invalid:1", 0);
    invalidate(&mut h, "a", "x", 0);
    let e = h.req("a", 3);
    let e = h.read(op(&e, "read", "a"), None);
    h.step(Event::CapacityPeersRead {
        op: op(&e, "capacity", "a"),
        now_ms: 100,
        result: Ok(vec![peer("x", 10), peer("y", 10)]),
    });
    h.remote(3, "y", "y.invalid:1", 0);
    invalidate(&mut h, "a", "x", 0);
    let e = h.req("a", 4);
    no_op(&e, "read", "a");
    h.remote(4, "y", "y.invalid:1", 0);
    h.finish(1);
    h.done();
}

#[test]
fn n023_cross_cell_lease_cache_is_cleared_by_exact_route_failure() {
    let mut h = H::new(1, 2);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 3, "a3")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "old.invalid:1", 500, "g1")),
    );
    let e = h.req("b", 2);
    let e = h.read(op(&e, "read", "b"), Some(record(Some("peer"), 8, "b8")));
    no_op(&e, "lease", "b");
    h.remote(2, "peer", "old.invalid:1", 8);
    invalidate(&mut h, "a", "peer", 3);
    let e = h.req("c", 3);
    let e = h.read(op(&e, "read", "c"), Some(record(Some("peer"), 12, "c12")));
    h.lease(
        op(&e, "lease", "c"),
        Some(lease("peer", "new.invalid:2", 500, "g2")),
    );
    h.remote(3, "peer", "new.invalid:2", 12);
    let e = h.req("b", 4);
    no_op(&e, "read", "b");
    h.remote(4, "peer", "old.invalid:1", 8);
    h.done();
}

#[test]
fn n024_monotonic_expiry_defeats_rolled_back_wall_sample() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 2, "p2")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "old.invalid:1", 130, "g1")),
    );
    // The old route's monotonic deadline is 130 even when later wall samples are 90.
    h.now = 135;
    let e = h.req("a", 2);
    let read = op(&e, "read", "a");
    let e = h.step(Event::OwnerRead {
        op: read,
        now_ms: 90,
        result: Ok(Some(record(Some("peer"), 3, "p3"))),
    });
    let e = h.step(Event::NodeLeaseRead {
        op: op(&e, "lease", "a"),
        now_ms: 90,
        result: Ok(Some(lease("peer", "new.invalid:2", 300, "g2"))),
    });
    no_op(&e, "cas", "a");
    h.remote(2, "peer", "new.invalid:2", 3);
    assert_eq!(h.s.presence_snapshot().activity.remote_route_refreshes, 1);
    h.done();
}

#[test]
fn n025_live_incompatible_owner_blocks_takeover_until_fresh_compatible_read() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 4, "p4")));
    let mut incompatible = lease("peer", "peer.invalid:1", 500, "g1");
    incompatible.peer_protocol = 2;
    let e = h.lease(op(&e, "lease", "a"), Some(incompatible));
    no_op(&e, "cas", "a");
    h.failed(1, RequestError::PeerIncompatible);
    assert_eq!(h.s.occupied(), 0);
    // A later request crosses the incompatible observation's actual deadline.
    h.now = 501;
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("peer"), 4, "p4")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("peer", "peer.invalid:2", 900, "g2")),
    );
    h.remote(2, "peer", "peer.invalid:2", 4);
    h.done();
}
fn open_dead_lease() -> NodeLeaseRecord {
    let mut l = lease("dead", "dead.invalid:1", 99, "dead-generation");
    l.log_state = Some(log_tier::LogState::Open);
    l
}

#[test]
fn n026_recovery_backoff_yields_activation_then_rechecks_changed_owner() {
    let mut h = H::new(2, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 4, "dead4")));
    let e = h.lease(op(&e, "lease", "a"), Some(open_dead_lease()));
    let old = op(&e, "recover", "a");
    h.req("b", 2);
    let e = h.step(Event::NodeLogRecovered {
        op: old,
        result: Err(Failure::Ambiguous),
    });
    let retry = timer(&e, "recovery", "a");
    let e = h.read(op(&e, "read", "b"), None);
    h.acquired(op(&e, "cas", "b"), "b", 1);
    h.local(2);
    h.finish(2);
    assert!(!h.completed.contains_key(&1));
    let e = h.fire(retry, 110);
    let e = h.read(
        op(&e, "read", "a"),
        Some(record(Some("successor"), 8, "s8")),
    );
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("successor", "s.invalid:1", 500, "s1")),
    );
    h.remote(1, "successor", "s.invalid:1", 8);
    assert!(h
        .step(Event::NodeLogRecovered {
            op: old,
            result: Ok(())
        })
        .is_empty());
    h.done();
}

#[test]
fn n027_recovery_completion_retains_old_guard_when_ownership_moves() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 4, "dead4")));
    let e = h.lease(op(&e, "lease", "a"), Some(open_dead_lease()));
    let recovery = op(&e, "recover", "a");
    h.req("a", 2);
    let e = h.step(Event::NodeLogRecovered {
        op: recovery,
        result: Ok(()),
    });
    assert!(e.iter().any(|v| matches!(v, Effect::CasOwner { guard, epoch: 5, takeover: true, .. } if guard == &CasGuard::Match("dead4".into()))));
    let e = h.cas(op(&e, "cas", "a"), Ok(CasOutcome::Rejected));
    let e = h.read(op(&e, "read", "a"), Some(record(Some("winner"), 9, "w9")));
    h.lease(
        op(&e, "lease", "a"),
        Some(lease("winner", "winner.invalid:1", 500, "w1")),
    );
    h.remote(1, "winner", "winner.invalid:1", 9);
    h.remote(2, "winner", "winner.invalid:1", 9);
    h.done();
}

#[test]
fn n028_recovery_budget_exhausts_without_poisoning_next_request() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 4, "dead4")));
    let e = h.lease(op(&e, "lease", "a"), Some(open_dead_lease()));
    let e = h.step(Event::NodeLogRecovered {
        op: op(&e, "recover", "a"),
        result: Err(Failure::Definite),
    });
    let e = h.fire(timer(&e, "recovery", "a"), 110);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 4, "dead4")));
    let e = h.lease(op(&e, "lease", "a"), Some(open_dead_lease()));
    let e = h.step(Event::NodeLogRecovered {
        op: op(&e, "recover", "a"),
        result: Err(Failure::Definite),
    });
    no_op(&e, "cas", "a");
    h.failed(1, RequestError::ResolveFailed);
    assert_eq!(h.s.activating(), 0);
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 4, "dead4")));
    let mut sealed = open_dead_lease();
    sealed.log_state = Some(log_tier::LogState::Sealed);
    let e = h.lease(op(&e, "lease", "a"), Some(sealed));
    no_op(&e, "recover", "a");
    h.acquired(op(&e, "cas", "a"), "a", 5);
    h.local(2);
    h.finish(2);
    h.done();
}

#[test]
fn n029_cancelled_recovery_backoff_does_not_resurrect_demand() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), Some(record(Some("dead"), 4, "dead4")));
    let e = h.lease(op(&e, "lease", "a"), Some(open_dead_lease()));
    let recover = op(&e, "recover", "a");
    let e = h.step(Event::NodeLogRecovered {
        op: recover,
        result: Err(Failure::Ambiguous),
    });
    let retry = timer(&e, "recovery", "a");
    h.cancel(1);
    h.activate("b", 2, None);
    h.finish(2);
    let e = h.fire(retry.clone(), 110);
    no_op(&e, "read", "a");
    assert_eq!(h.s.phase("a"), Some(&Phase::Inactive));
    assert!(h
        .step(Event::NodeLogRecovered {
            op: recover,
            result: Ok(())
        })
        .is_empty());
    assert!(h.fire(retry, 120).is_empty());
    h.done();
}

#[test]
fn n030_late_runtime_start_owns_slot_after_callers_timeout() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let e = h.cas(op(&e, "cas", "a"), Ok(CasOutcome::Applied));
    let e = h.step(Event::RestoreCompleted {
        op: op(&e, "restore", "a"),
        result: Ok(RestoreOutcome {
            restored: false,
            alarm: None,
        }),
    });
    let start = op(&e, "start", "a");
    let t = deadline(&e, start);
    h.fire(t, 150);
    h.failed(1, RequestError::RuntimeFailed);
    let e = h.req("a", 2);
    h.failed(2, RequestError::RuntimeFailed);
    no_op(&e, "read", "a");
    no_op(&e, "start", "a");
    assert_eq!(h.s.activating(), 1);
    assert_eq!(h.s.occupied(), 1);
    let e = h.step(Event::RuntimeStarted {
        op: start,
        isolate: None,
        generation: 1,
        result: Ok(()),
    });
    h.step(Event::Published {
        op: op(&e, "publish", "a"),
        result: Ok(()),
    });
    h.req("a", 3);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn n031_publish_failure_keeps_joiners_until_cleanup_then_allows_reacquire() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let e = h.read(op(&e, "read", "a"), None);
    let e = h.cas(op(&e, "cas", "a"), Ok(CasOutcome::Applied));
    let e = h.step(Event::RestoreCompleted {
        op: op(&e, "restore", "a"),
        result: Ok(RestoreOutcome {
            restored: false,
            alarm: None,
        }),
    });
    let e = h.step(Event::RuntimeStarted {
        op: op(&e, "start", "a"),
        isolate: None,
        generation: 1,
        result: Ok(()),
    });
    let e = h.step(Event::Published {
        op: op(&e, "publish", "a"),
        result: Err(Failure::Ambiguous),
    });
    let stop = op(&e, "stop", "a");
    h.req("a", 2);
    assert!(!h.completed.contains_key(&1) && !h.completed.contains_key(&2));
    h.step(Event::RuntimeStopped { op: stop });
    h.failed(1, RequestError::PublishFailed);
    h.failed(2, RequestError::PublishFailed);
    assert_eq!(h.s.phase("a"), Some(&Phase::Dormant { epoch: 1 }));
    h.activate("a", 3, Some(record(Some("fixture"), 1, "self1")));
    h.finish(3);
    h.done();
}

#[test]
fn n032_last_owner_read_waiter_cancel_prevents_unneeded_claim() {
    let mut h = H::new(1, 1);
    let e = h.req("a", 1);
    let old = op(&e, "read", "a");
    h.req("a", 2);
    h.cancel(2);
    h.cancel(1);
    let e = h.read(old, None);
    no_op(&e, "cas", "a");
    assert_eq!(h.s.phase("a"), Some(&Phase::Inactive));
    assert_eq!(h.s.occupied(), 0);
    h.activate("a", 3, None);
    h.finish(3);
    h.done();
}

#[test]
fn n033_same_capacity_sample_reservations_compose_across_reverse_completions() {
    let mut h = H::leased(1, 2);
    h.activate("hot", 1, None);
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), None);
    let a = op(&e, "capacity", "a");
    let e = h.req("b", 3);
    let e = h.read(op(&e, "read", "b"), None);
    let b = op(&e, "capacity", "b");
    h.step(Event::CapacityPeersRead {
        op: b,
        now_ms: 100,
        result: Ok(vec![peer("x", 10), peer("y", 10)]),
    });
    h.remote(3, "x", "x.invalid:1", 0);
    h.step(Event::CapacityPeersRead {
        op: a,
        now_ms: 100,
        result: Ok(vec![peer("x", 10), peer("y", 10)]),
    });
    h.remote(2, "y", "y.invalid:1", 0);
    assert_eq!(h.s.accepted_epoch("a"), None);
    assert_eq!(h.s.accepted_epoch("b"), None);
    assert_eq!(h.s.occupied(), 1);
    h.finish(1);
    h.done();
}

#[test]
fn n034_capacity_refusal_sticks_to_sample_until_newer_observation() {
    let mut h = H::leased(1, 2);
    h.activate("hot", 1, None);
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), None);
    h.step(Event::CapacityPeersRead {
        op: op(&e, "capacity", "a"),
        now_ms: 100,
        result: Ok(vec![peer("x", 10), peer("y", 10)]),
    });
    h.remote(2, "x", "x.invalid:1", 0);
    invalidate(&mut h, "a", "x", 0);
    let e = h.req("a", 3);
    let e = h.read(op(&e, "read", "a"), None);
    h.step(Event::CapacityPeersRead {
        op: op(&e, "capacity", "a"),
        now_ms: 100,
        result: Ok(vec![peer("x", 10), peer("y", 10)]),
    });
    h.remote(3, "y", "y.invalid:1", 0);
    invalidate(&mut h, "a", "y", 0);
    let e = h.req("b", 4);
    let e = h.read(op(&e, "read", "b"), None);
    h.step(Event::CapacityPeersRead {
        op: op(&e, "capacity", "b"),
        now_ms: 100,
        result: Ok(vec![peer("x", 11), peer("y", 11)]),
    });
    h.remote(4, "x", "x.invalid:1", 0);
    h.finish(1);
    h.done();
}

#[test]
fn n035_unknown_capacity_preserves_idle_resident_until_waiter_deadline() {
    let mut h = H::leased(1, 1);
    h.activate("hot", 1, None);
    h.finish(1);
    let e = h.req("a", 2);
    let e = h.read(op(&e, "read", "a"), None);
    let lookup = op(&e, "capacity", "a");
    let e = h.step(Event::CapacityPeersRead {
        op: lookup,
        now_ms: 100,
        result: Err(Failure::Definite),
    });
    no_op(&e, "ensure", "hot");
    no_op(&e, "cas", "a");
    assert_eq!(h.s.phase("hot"), Some(&Phase::Resident { epoch: 1 }));
    assert_eq!(h.s.phase("a"), Some(&Phase::WaitingCapacity));
    h.fire(timer(&e, "queue", "a"), 150);
    h.failed(2, RequestError::CapacityExhausted);
    assert!(h
        .step(Event::CapacityPeersRead {
            op: lookup,
            now_ms: 150,
            result: Ok(vec![peer("x", 12)])
        })
        .is_empty());
    h.req("hot", 3);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn n036_stale_capacity_handoff_refuses_only_its_caller() {
    let mut h = H::leased(1, 1);
    h.activate("hot", 1, None);
    let e = h.step(Event::CapacityRequestAt {
        request: 2,
        cell: "a".into(),
        now_mono_ms: 100,
    });
    let read = op(&e, "read", "a");
    h.req("a", 3);
    let e = h.read(read, None);
    h.failed(2, RequestError::CapacityExhausted);
    assert!(!h.completed.contains_key(&3));
    no_op(&e, "cas", "a");
    h.step(Event::CapacityPeersRead {
        op: op(&e, "capacity", "a"),
        now_ms: 100,
        result: Ok(vec![peer("x", 10)]),
    });
    h.remote(3, "x", "x.invalid:1", 0);
    h.finish(1);
    h.done();
}
