//! Hand-authored finite schedules over the production decision core.
//! Samples and effect completions are supplied facts, not real RSS/VM evidence.
use celld_logic::*;
use std::collections::{BTreeMap, BTreeSet};

fn config() -> Config {
    Config {
        max_resident: 4,
        max_activations: 4,
        max_evictions: 2,
        max_releases: 2,
        max_outbound_websockets: 2,
        ownership_on_evict: OwnershipOnEvict::Sticky,
        require_node_lease: false,
        peer_protocol: 1,
        operation_deadline_ms: Some(50),
        owner_log_recovery_backoff_ms: 10,
        owner_log_recovery_attempts: 2,
        alarm_resident_ms: 0,
        idle_evict_ms: None,
        pressure: pressure::PressureConfig {
            high_bytes: Some(100),
            rss_hard_bytes: Some(200),
        },
    }
}
fn load(residents: usize, memory: u64, hard: u64) -> pressure::Load {
    pressure::Load {
        resident_cells: residents,
        rss_bytes: hard,
        in_use_bytes: memory,
        cgroup_working_set_bytes: None,
        cgroup_current_bytes: None,
        container_reserved_bytes: 0,
    }
}
struct H {
    id: &'static str,
    s: State,
    count: usize,
    pending: BTreeSet<u64>,
    completed: BTreeMap<u64, Result<Route, RequestError>>,
    cells: BTreeSet<String>,
}
impl H {
    fn new(id: &'static str) -> Self {
        println!("TRACE_BEGIN {id} native-component source-driven; no process resources");
        Self {
            id,
            s: State::new("fixture", config()),
            count: 0,
            pending: BTreeSet::new(),
            completed: BTreeMap::new(),
            cells: BTreeSet::new(),
        }
    }
    fn step(&mut self, event: Event) -> Vec<Effect> {
        self.count += 1;
        assert!(self.count <= 100, "finite 100-event ceiling");
        if let Event::RequestAt { request, cell, .. } = &event {
            assert!(self.pending.insert(*request));
            assert!(!self.completed.contains_key(request));
            self.cells.insert(cell.clone());
        }
        println!("{} event {:03}: {:?}", self.id, self.count, event);
        let effects = on_event(&mut self.s, event);
        println!("{} effects {:03}: {:?}", self.id, self.count, effects);
        self.s.validate().expect("production structural invariants");
        assert!(self.s.occupied() <= 4);
        assert!(self.s.activating() <= 4);
        assert!(self.s.evicting() <= 2);
        for effect in &effects {
            if let Effect::Complete { request, result } = effect {
                assert!(
                    self.pending.remove(request),
                    "unknown or repeated completion"
                );
                assert!(self.completed.insert(*request, result.clone()).is_none());
            }
        }
        println!("{} state: occupied={} activating={} evicting={} shedding={} reason={:?} headroom={} waiting={:?}", self.id, self.s.occupied(), self.s.activating(), self.s.evicting(), self.s.shedding(), self.s.shed_reason(), self.s.memory_headroom(), self.s.waiting());
        effects
    }
    fn req(&mut self, cell: &str, request: u64) -> Vec<Effect> {
        self.step(Event::RequestAt {
            request,
            cell: cell.into(),
            now_mono_ms: 100,
        })
    }
    fn read_absent(&mut self, read: u64) -> Vec<Effect> {
        self.step(Event::OwnerRead {
            op: read,
            now_ms: 100,
            result: Ok(None),
        })
    }
    fn queue(&mut self, cell: &str, request: u64) -> Vec<Effect> {
        let e = self.req(cell, request);
        let e = self.read_absent(op(&e, "read", cell));
        no_op(&e, "cas", cell);
        assert_eq!(self.s.phase(cell), Some(&Phase::WaitingCapacity));
        assert!(self.pending.contains(&request));
        e
    }
    fn cas_to_local(&mut self, claim: u64, cell: &str, request: u64) {
        let e = self.step(Event::OwnerCasCompleted {
            op: claim,
            result: Ok(CasOutcome::Applied),
        });
        let restore = op(&e, "restore", cell);
        let e = self.step(Event::RestoreCompleted {
            op: restore,
            result: Ok(RestoreOutcome {
                restored: false,
                alarm: None,
            }),
        });
        self.start_to_local(op(&e, "start", cell), cell, Some(request));
    }
    fn start_to_local(&mut self, start: u64, cell: &str, request: Option<u64>) {
        let e = self.step(Event::RuntimeStarted {
            op: start,
            isolate: None,
            generation: 1,
            result: Ok(()),
        });
        let publish = op(&e, "publish", cell);
        self.step(Event::Published {
            op: publish,
            result: Ok(()),
        });
        assert_eq!(self.s.phase(cell), Some(&Phase::Resident { epoch: 1 }));
        if let Some(request) = request {
            self.local(request);
        }
    }
    fn activate(&mut self, cell: &str, request: u64) {
        let e = self.req(cell, request);
        let e = self.read_absent(op(&e, "read", cell));
        self.cas_to_local(op(&e, "cas", cell), cell, request);
    }
    fn idle(&mut self, cell: &str, request: u64) {
        self.activate(cell, request);
        self.finish(request);
    }
    fn idle_on_heap(&mut self, cell: &str, request: u64, heap: u64) {
        let e = self.step(Event::RequestAt {
            request,
            cell: cell.into(),
            now_mono_ms: 97 + request,
        });
        let e = self.read_absent(op(&e, "read", cell));
        let e = self.step(Event::OwnerCasCompleted {
            op: op(&e, "cas", cell),
            result: Ok(CasOutcome::Applied),
        });
        let e = self.step(Event::RestoreCompleted {
            op: op(&e, "restore", cell),
            result: Ok(RestoreOutcome {
                restored: false,
                alarm: None,
            }),
        });
        let e = self.step(Event::RuntimeStarted {
            op: op(&e, "start", cell),
            isolate: Some(isolate::HeapId::new(heap)),
            generation: 1,
            result: Ok(()),
        });
        self.step(Event::Published {
            op: op(&e, "publish", cell),
            result: Ok(()),
        });
        self.local(request);
        self.finish(request);
    }
    fn three_idle(&mut self) {
        self.idle("a", 1);
        self.idle("b", 2);
        self.idle("c", 3);
    }
    fn sample(&mut self, memory: u64, hard: u64) -> Vec<Effect> {
        self.sample_at(load(self.s.occupied(), memory, hard), 100)
    }
    fn sample_at(&mut self, value: pressure::Load, at: u64) -> Vec<Effect> {
        self.step(Event::LoadSampled {
            load: value,
            now_mono_ms: at,
        })
    }
    fn local(&self, request: u64) {
        assert_eq!(self.completed.get(&request), Some(&Ok(Route::Local)));
    }
    fn failed(&self, request: u64, error: RequestError) {
        assert_eq!(self.completed.get(&request), Some(&Err(error)));
    }
    fn finish(&mut self, request: u64) -> Vec<Effect> {
        self.step(Event::ActivityFinished { request })
    }
    fn cut(&mut self, ensure: u64, cell: &str) -> Vec<Effect> {
        let e = self.step(Event::DurabilityChecked {
            op: ensure,
            result: Ok(()),
        });
        let stop = op(&e, "stop", cell);
        assert!(e.iter().any(|v| matches!(
            v,
            Effect::StopRuntime {
                cause: StopCause::Evict { .. },
                ..
            }
        )));
        let e = self.step(Event::RuntimeStopped { op: stop });
        assert_eq!(self.s.phase(cell), Some(&Phase::Dormant { epoch: 1 }));
        e
    }
    fn assert_pressure(&self, reason: Option<&str>, headroom: bool) {
        assert_eq!(self.s.shed_reason(), reason);
        assert_eq!(self.s.shedding(), reason.is_some());
        assert_eq!(self.s.memory_headroom(), headroom);
    }
    fn done(self) {
        assert!(
            self.pending.is_empty(),
            "unsettled callers {:?}",
            self.pending
        );
        assert_eq!(self.s.activating(), 0);
        assert!(self.s.waiting().is_empty());
        assert!(self.s.activation_waiting().is_empty());
        assert_eq!(self.s.evicting(), 0);
        assert_eq!(self.s.releasing(), 0);
        assert_eq!(self.s.adopting(), 0);
        for cell in &self.cells {
            assert!(!self.s.is_active(cell), "active activity on {cell}");
            assert!(matches!(
                self.s.phase(cell),
                Some(
                    Phase::Resident { .. }
                        | Phase::Dormant { .. }
                        | Phase::Remote { .. }
                        | Phase::Inactive
                )
            ));
        }
        self.s.validate().unwrap();
        println!(
            "TRACE_END {} events={} completed={} cleanup=drop-owned-State pending=0",
            self.id,
            self.count,
            self.completed.len()
        );
    }
}
fn kind(e: &Effect, wanted: &str, cell: &str) -> Option<u64> {
    match (wanted, e) {
        ("read", Effect::ReadOwner { op, cell: c })
        | ("cas", Effect::CasOwner { op, cell: c, .. })
        | ("restore", Effect::Restore { op, cell: c, .. })
        | ("start", Effect::StartRuntime { op, cell: c, .. })
        | ("publish", Effect::Publish { op, cell: c, .. })
        | ("ensure", Effect::EnsureDurable { op, cell: c, .. })
        | ("stop", Effect::StopRuntime { op, cell: c, .. })
        | ("release", Effect::ReleaseOwner { op, cell: c, .. })
        | ("adopt", Effect::AdoptReleased { op, cell: c, .. })
            if c == cell =>
        {
            Some(*op)
        }
        _ => None,
    }
}
fn op(e: &[Effect], wanted: &str, cell: &str) -> u64 {
    let found: Vec<_> = e.iter().filter_map(|e| kind(e, wanted, cell)).collect();
    assert_eq!(found.len(), 1, "one {wanted} for {cell}: {e:?}");
    found[0]
}
fn no_op(e: &[Effect], wanted: &str, cell: &str) {
    assert!(
        e.iter().all(|e| kind(e, wanted, cell).is_none()),
        "unexpected {wanted} on {cell}: {e:?}"
    );
}
fn no_ensure(e: &[Effect]) {
    assert!(
        !e.iter().any(|e| matches!(e, Effect::EnsureDurable { .. })),
        "unexpected victim: {e:?}"
    );
}
fn queued_timer(e: &[Effect], cell: &str) -> Timer {
    let found: Vec<_> = e
        .iter()
        .filter_map(|e| match e {
            Effect::ScheduleTimer {
                timer: t @ Timer::QueuedActivation { cell: c, .. },
                at_mono_ms,
            } if c == cell => {
                assert_eq!(*at_mono_ms, 150);
                Some(t.clone())
            }
            _ => None,
        })
        .collect();
    assert_eq!(found.len(), 1);
    found[0].clone()
}

#[test]
fn p001_ordinary_hysteresis_queues_cold_but_serves_active_resident() {
    let mut h = H::new("P001");
    h.activate("a", 1);
    no_ensure(&h.sample(100, 150));
    h.assert_pressure(Some("memory"), false);
    h.queue("b", 2);
    h.req("a", 3);
    h.local(3);
    no_op(&h.sample(81, 150), "cas", "b");
    assert!(h.pending.contains(&2));
    let e = h.sample(80, 150);
    h.assert_pressure(None, true);
    h.cas_to_local(op(&e, "cas", "b"), "b", 2);
    h.finish(1);
    h.finish(2);
    h.finish(3);
    h.done();
}

#[test]
fn p002_hard_only_crossing_does_not_arm_ordinary_latch() {
    let mut h = H::new("P002");
    h.sample(90, 200);
    h.assert_pressure(Some("rss-hard"), false);
    h.queue("a", 1);
    no_op(&h.sample(90, 161), "cas", "a");
    let e = h.sample(90, 160);
    h.assert_pressure(None, false);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.sample(80, 160);
    h.assert_pressure(None, true);
    h.finish(1);
    h.done();
}

#[test]
fn p003_ordinary_only_crossing_does_not_arm_hard_latch() {
    let mut h = H::new("P003");
    h.sample(100, 190);
    h.assert_pressure(Some("memory"), false);
    h.queue("a", 1);
    no_op(&h.sample(81, 190), "cas", "a");
    let e = h.sample(80, 190);
    h.assert_pressure(None, false);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.sample(80, 160);
    h.assert_pressure(None, true);
    h.finish(1);
    h.done();
}

#[test]
fn p004_dual_crossing_requires_both_independent_resume_lines() {
    let mut h = H::new("P004");
    h.sample(100, 200);
    h.assert_pressure(Some("rss-hard"), false);
    h.queue("a", 1);
    no_op(&h.sample(90, 180), "cas", "a");
    h.assert_pressure(Some("rss-hard"), false);
    // Ordinary90 cannot rearm: memory reason after hard relief proves retention.
    no_op(&h.sample(90, 160), "cas", "a");
    h.assert_pressure(Some("memory"), false);
    let e = h.sample(80, 160);
    h.assert_pressure(None, true);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.finish(1);
    h.done();
}

#[test]
fn p005_active_kernel_working_set_closes_admission_until_released() {
    let mut h = H::new("P005");
    let mut s = load(0, 40, 50);
    s.cgroup_working_set_bytes = Some(110);
    s.cgroup_current_bytes = Some(150);
    h.sample_at(s, 100);
    h.assert_pressure(Some("memory"), false);
    h.queue("a", 1);
    s.cgroup_working_set_bytes = Some(91);
    no_op(&h.sample_at(s, 101), "cas", "a");
    s.cgroup_working_set_bytes = Some(90);
    let e = h.sample_at(s, 102);
    h.assert_pressure(None, true);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.finish(1);
    h.done();
}

#[test]
fn p006_allocator_slack_relief_reopens_despite_retained_rss_and_cache() {
    let mut h = H::new("P006");
    let mut s = load(0, 110, 150);
    s.cgroup_working_set_bytes = Some(150);
    s.cgroup_current_bytes = Some(180);
    h.sample_at(s, 100);
    h.queue("a", 1);
    s.in_use_bytes = 80;
    let e = h.sample_at(s, 101);
    assert_eq!(s.rss_bytes, 150);
    assert_eq!(s.cgroup_working_set_bytes, Some(150));
    h.assert_pressure(None, false);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.finish(1);
    h.done();
}

#[test]
fn p007_container_commitment_release_drives_both_latches() {
    let mut h = H::new("P007");
    let mut s = load(0, 60, 100);
    s.container_reserved_bytes = 100;
    h.sample_at(s, 100);
    h.assert_pressure(Some("rss-hard"), false);
    h.queue("a", 1);
    s.container_reserved_bytes = 60;
    no_op(&h.sample_at(s, 101), "cas", "a");
    h.assert_pressure(Some("memory"), false);
    s.container_reserved_bytes = 20;
    let e = h.sample_at(s, 102);
    h.assert_pressure(None, true);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.finish(1);
    h.done();
}

#[test]
fn p008_unlatched_warm_band_admits_but_does_not_claim_headroom() {
    let mut h = H::new("P008");
    h.sample(90, 150);
    h.assert_pressure(None, false);
    h.activate("a", 1);
    h.sample(100, 150);
    h.queue("b", 2);
    no_op(&h.sample(90, 150), "cas", "b");
    h.assert_pressure(Some("memory"), false);
    let e = h.sample(80, 150);
    h.cas_to_local(op(&e, "cas", "b"), "b", 2);
    h.finish(1);
    h.finish(2);
    h.done();
}

#[test]
fn p009_missing_sample_horizon_expires_waiter_then_fresh_sample_recovers() {
    let mut h = H::new("P009");
    h.sample(100, 150);
    let e = h.queue("a", 1);
    let timer = queued_timer(&e, "a");
    // No failed-sample Event exists: the omission is explicitly bounded at 150ms.
    h.step(Event::TimerFired {
        timer,
        now_ms: 150,
        now_mono_ms: 150,
    });
    h.failed(1, RequestError::CapacityExhausted);
    h.assert_pressure(Some("memory"), false);
    assert_eq!(h.s.phase("a"), Some(&Phase::Inactive));
    h.sample_at(load(0, 80, 150), 151);
    h.activate("a", 2);
    h.finish(2);
    h.done();
}

#[test]
fn p010_late_sample_is_folded_without_freshness_rejection() {
    let mut h = H::new("P010");
    h.sample_at(load(0, 100, 150), 120);
    h.queue("a", 1);
    // Source characterization: timestamp rollback does not reject load payload.
    let e = h.sample_at(load(0, 80, 150), 110);
    h.assert_pressure(None, true);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.finish(1);
    h.done();
}

#[test]
fn p011_crossing_between_owner_read_and_claim_parks_acquisition() {
    let mut h = H::new("P011");
    let e = h.req("a", 1);
    let read = op(&e, "read", "a");
    h.sample(100, 150);
    let e = h.read_absent(read);
    no_op(&e, "cas", "a");
    assert_eq!(h.s.occupied(), 0);
    assert_eq!(h.s.phase("a"), Some(&Phase::WaitingCapacity));
    let e = h.sample(80, 150);
    h.cas_to_local(op(&e, "cas", "a"), "a", 1);
    h.finish(1);
    h.done();
}

#[test]
fn p012_crossing_after_claim_issue_does_not_abandon_acquired_owner() {
    let mut h = H::new("P012");
    let e = h.req("a", 1);
    let e = h.read_absent(op(&e, "read", "a"));
    let claim = op(&e, "cas", "a");
    h.sample(100, 150);
    h.cas_to_local(claim, "a", 1);
    h.assert_pressure(Some("memory"), false);
    h.queue("b", 2);
    let e = h.sample(80, 150);
    h.cas_to_local(op(&e, "cas", "b"), "b", 2);
    h.finish(1);
    h.finish(2);
    h.done();
}

#[test]
fn p013_busy_pressure_cut_waits_for_later_sample_after_activity_finishes() {
    let mut h = H::new("P013");
    h.activate("a", 1);
    h.activate("b", 2);
    no_ensure(&h.sample(120, 150));
    no_ensure(&h.finish(1));
    let e = h.sample(120, 150);
    no_op(&e, "ensure", "b");
    let ensure = op(&e, "ensure", "a");
    h.sample(80, 150);
    h.cut(ensure, "a");
    assert!(h.s.is_active("b"));
    h.finish(2);
    h.done();
}

#[test]
fn p014_repeated_samples_count_pending_cut_once() {
    let mut h = H::new("P014");
    h.three_idle();
    let e = h.sample(120, 150);
    let ensure = op(&e, "ensure", "a");
    assert_eq!(h.s.evicting(), 1);
    no_ensure(&h.sample(120, 150));
    assert_eq!(h.s.evicting(), 1);
    no_ensure(&h.cut(ensure, "a"));
    assert_eq!(h.s.occupied(), 2);
    h.sample(80, 150);
    h.done();
}

#[test]
fn p015_flat_yield_stops_cutting_but_keeps_admission_closed() {
    let mut h = H::new("P015");
    h.three_idle();
    let e = h.sample(120, 150);
    h.cut(op(&e, "ensure", "a"), "a");
    no_ensure(&h.sample(120, 150));
    h.assert_pressure(Some("memory"), false);
    assert_eq!(h.s.occupied(), 2);
    h.queue("d", 4);
    let e = h.sample(80, 150);
    h.cas_to_local(op(&e, "cas", "d"), "d", 4);
    h.finish(4);
    h.done();
}

#[test]
fn p016_rising_sample_rearms_a_previously_futile_walk() {
    let mut h = H::new("P016");
    h.three_idle();
    let e = h.sample(120, 150);
    h.cut(op(&e, "ensure", "a"), "a");
    no_ensure(&h.sample(120, 150));
    let e = h.sample(122, 150);
    let ensure = op(&e, "ensure", "b");
    h.cut(ensure, "b");
    assert_eq!(h.s.occupied(), 1);
    h.sample(80, 150);
    h.done();
}

#[test]
fn p017_delayed_yield_uses_original_cut_baseline_to_resume() {
    let mut h = H::new("P017");
    h.three_idle();
    let e = h.sample(120, 150);
    h.cut(op(&e, "ensure", "a"), "a");
    no_ensure(&h.sample(118, 150));
    // Retained120 projects78; replacing only its bytes with118 projects82.
    let e = h.sample(106, 150);
    let ensure = op(&e, "ensure", "b");
    h.cut(ensure, "b");
    assert_eq!(h.s.occupied(), 1);
    h.sample(80, 150);
    h.done();
}

#[test]
fn p018_metric_switch_discards_incomparable_futility_baseline() {
    let mut h = H::new("P018");
    h.three_idle();
    let e = h.sample(240, 240);
    h.cut(op(&e, "ensure", "a"), "a");
    no_ensure(&h.sample(240, 240));
    // Equal240 metric values ensure growth cannot mask a missing metric reset.
    let e = h.sample(80, 240);
    h.assert_pressure(Some("rss-hard"), false);
    h.cut(op(&e, "ensure", "b"), "b");
    h.sample(80, 160);
    h.assert_pressure(None, true);
    h.done();
}

#[test]
fn p019_failed_durability_preserves_owner_and_rotates_victim() {
    let mut h = H::new("P019");
    h.three_idle();
    let e = h.sample(120, 150);
    let failed = op(&e, "ensure", "a");
    let e = h.step(Event::DurabilityChecked {
        op: failed,
        result: Err(Failure::Definite),
    });
    no_op(&e, "stop", "a");
    assert_eq!(h.s.phase("a"), Some(&Phase::Resident { epoch: 1 }));
    assert_eq!(h.s.evicting(), 0);
    let e = h.sample(120, 150);
    let ensure = op(&e, "ensure", "b");
    no_op(&e, "ensure", "a");
    h.sample(80, 150);
    h.cut(ensure, "b");
    h.req("a", 4);
    h.local(4);
    h.finish(4);
    h.done();
}

#[test]
fn p020_failed_bounded_stop_restarts_same_epoch_and_serves_again() {
    let mut h = H::new("P020");
    h.idle("a", 1);
    let e = h.sample(120, 150);
    let ensure = op(&e, "ensure", "a");
    let e = h.step(Event::DurabilityChecked {
        op: ensure,
        result: Ok(()),
    });
    let stop = op(&e, "stop", "a");
    assert!(e.iter().any(|e| matches!(
        e,
        Effect::StopRuntime {
            bounded: true,
            epoch: 1,
            ..
        }
    )));
    let e = h.step(Event::RuntimeStopFailed { op: stop });
    no_op(&e, "cas", "a");
    no_op(&e, "restore", "a");
    let start = op(&e, "start", "a");
    assert!(e.iter().any(|effect| matches!(effect, Effect::StartRuntime { op, cell, epoch: 1 } if *op == start && cell == "a")));
    h.sample(80, 150);
    h.start_to_local(start, "a", None);
    h.req("a", 2);
    h.local(2);
    h.finish(2);
    h.done();
}

#[test]
fn p021_relief_during_proof_does_not_revoke_already_nominated_cut() {
    let mut h = H::new("P021");
    h.idle("a", 1);
    h.idle("b", 2);
    let e = h.sample(120, 150);
    let ensure = op(&e, "ensure", "a");
    no_ensure(&h.sample(80, 150));
    assert_eq!(
        h.s.phase("a"),
        Some(&Phase::EnsuringDurability {
            op: ensure,
            epoch: 1
        })
    );
    no_ensure(&h.cut(ensure, "a"));
    h.req("b", 3);
    h.local(3);
    h.finish(3);
    h.done();
}

#[test]
fn p022_cut_empties_smallest_heap_ahead_of_older_scattered_cells() {
    let mut h = H::new("P022");
    h.idle_on_heap("b", 1, 20);
    h.idle_on_heap("c", 2, 20);
    h.idle_on_heap("a", 3, 10);
    let e = h.sample(120, 150);
    no_op(&e, "ensure", "b");
    no_op(&e, "ensure", "c");
    h.cut(op(&e, "ensure", "a"), "a");
    assert_eq!(
        h.s.resident_isolates(),
        vec![isolate::HeapId::new(20), isolate::HeapId::new(20)]
    );
    no_ensure(&h.sample(120, 150));
    h.sample(80, 150);
    h.req("b", 4);
    h.local(4);
    h.finish(4);
    h.done();
}

#[test]
fn p023_drain_before_relief_refuses_parked_unowned_claim() {
    let mut h = H::new("P023");
    h.sample(120, 150);
    h.queue("a", 1);
    h.step(Event::ReleaseAll);
    assert!(h.s.draining());
    let e = h.sample(80, 150);
    no_op(&e, "cas", "a");
    h.failed(1, RequestError::NodeUnavailable);
    h.req("b", 2);
    h.failed(2, RequestError::NodeUnavailable);
    assert_eq!(h.s.occupied(), 0);
    h.done();
}

#[test]
fn p024_drain_releases_futile_pressure_survivor_without_reopening_admission() {
    let mut h = H::new("P024");
    h.idle("a", 1);
    h.idle("b", 2);
    let e = h.sample(120, 150);
    h.cut(op(&e, "ensure", "a"), "a");
    no_ensure(&h.sample(120, 150));
    assert_eq!(h.s.occupied(), 1);
    let e = h.step(Event::ReleaseAll);
    let ensure_b = op(&e, "ensure", "b");
    let release_a = op(&e, "release", "a");
    let e = h.step(Event::DurabilityChecked {
        op: ensure_b,
        result: Ok(()),
    });
    assert!(e.iter().any(|e| matches!(
        e,
        Effect::StopRuntime {
            bounded: false,
            cause: StopCause::Evict { rebalance: true },
            ..
        }
    )));
    let e = h.step(Event::RuntimeStopped {
        op: op(&e, "stop", "b"),
    });
    let release_b = op(&e, "release", "b");
    let e = h.step(Event::OwnerReleased {
        op: release_a,
        result: Ok(CasOutcome::Applied),
    });
    let adopt_a = op(&e, "adopt", "a");
    let e = h.step(Event::OwnerReleased {
        op: release_b,
        result: Ok(CasOutcome::Applied),
    });
    let adopt_b = op(&e, "adopt", "b");
    h.step(Event::SuccessorAdopted {
        op: adopt_b,
        result: Ok(AdoptedCell {
            node: "next".into(),
            addr: "next.invalid:1".into(),
            epoch: 2,
            peer_protocol: 1,
        }),
    });
    h.step(Event::SuccessorAdopted {
        op: adopt_a,
        result: Ok(AdoptedCell {
            node: "next".into(),
            addr: "next.invalid:1".into(),
            epoch: 2,
            peer_protocol: 1,
        }),
    });
    assert_eq!(h.s.owned_cells(), 0);
    assert_eq!(h.s.handed_off(), 2);
    h.assert_pressure(Some("memory"), false);
    h.req("c", 3);
    h.failed(3, RequestError::NodeUnavailable);
    h.done();
}

fn peer(node: &str, headroom: bool, restoring: u64, expiry: u64) -> CapacityPeer {
    CapacityPeer {
        node: node.into(),
        addr: format!("{node}.invalid:1"),
        expires_ms: expiry,
        peer_protocol: 1,
        sampled_ms: 100,
        owned_cells: Some(1),
        placement_weight: Some(1),
        bucket_format: Some(1),
        resident_cells: 1,
        host_websockets: 0,
        rss_bytes: 80,
        in_use_bytes: Some(80),
        pressured: false,
        memory_headroom: Some(headroom),
        restoring,
        paced_handoff: true,
        rebalance_paused: false,
        draining: false,
    }
}
fn fleet(
    step: &str,
    token: Option<&drain::DrainToken>,
    now: u64,
    peers: &[CapacityPeer],
) -> Result<(), drain::FleetUnsettled> {
    let result = drain::fleet_status(token, "join", now, peers, 2);
    println!("DRAIN_TRACE {step} token={token:?} now={now} peers={peers:?} result={result:?}");
    result
}

#[test]
fn p025_token_expiry_memory_relief_and_restore_recovery_are_separate_gates() {
    use drain::{DrainToken, FleetUnsettled, RestorationBaseline};
    let token = DrainToken {
        node: "donor".into(),
        expires_ms: 110,
        restoration_baseline: vec![RestorationBaseline {
            node: "old".into(),
            restoring: 3,
        }],
    };
    let mut peers = vec![peer("join", true, 0, 1000), peer("old", false, 6, 1000)];
    assert_eq!(
        fleet("P025 held token", Some(&token), 109, &peers),
        Err(FleetUnsettled::Drain)
    );
    assert_eq!(
        fleet("P025 token expires", Some(&token), 110, &peers),
        Err(FleetUnsettled::MemoryHeadroom { node: "old".into() })
    );
    peers[1].memory_headroom = Some(true);
    assert_eq!(
        fleet("P025 memory relieved", Some(&token), 111, &peers),
        Err(FleetUnsettled::Restoration {
            current: 6,
            maximum: 5
        })
    );
    peers[1].restoring = 5;
    assert_eq!(
        fleet("P025 backlog settled", Some(&token), 112, &peers),
        Ok(())
    );
    println!("TRACE_END P025 cleanup=drop-owned-inputs calls=4");
}

#[test]
fn p026_expired_pressure_peer_cannot_hold_readiness_but_renewed_peer_can() {
    use drain::FleetUnsettled;
    let mut peers = vec![peer("join", true, 0, 1000), peer("old", false, 0, 110)];
    peers[1].pressured = true;
    assert_eq!(
        fleet("P026 live pressured peer", None, 109, &peers),
        Err(FleetUnsettled::MemoryHeadroom { node: "old".into() })
    );
    assert_eq!(fleet("P026 peer expires", None, 110, &peers), Ok(()));
    peers[1].expires_ms = 1000;
    assert_eq!(
        fleet("P026 renewed but pressured", None, 111, &peers),
        Err(FleetUnsettled::MemoryHeadroom { node: "old".into() })
    );
    peers[1].pressured = false;
    assert_eq!(
        fleet("P026 latch cleared without reserve", None, 112, &peers),
        Err(FleetUnsettled::MemoryHeadroom { node: "old".into() })
    );
    peers[1].memory_headroom = Some(true);
    assert_eq!(
        fleet("P026 renewed and recovered", None, 113, &peers),
        Ok(())
    );
    println!("TRACE_END P026 cleanup=drop-owned-inputs calls=5");
}
