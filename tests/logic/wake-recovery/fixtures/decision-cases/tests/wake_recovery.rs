//! Handwritten finite recovery schedules against the delivered production crate.
//! Store completions, row facts, clock samples and scan ticks are synthetic premises.
//! A receipt is printed only AFTER its production call returns; no I/O or threads.
use celld_logic::wake::{AlarmSnapshot, AlarmSource, PublicationId, WakeCore};
use celld_logic::*;
use std::fmt::Debug;

struct Receipt {
    id: &'static str,
    calls: usize,
}
impl Receipt {
    fn new(id: &'static str) -> Self {
        Self { id, calls: 0 }
    }
    fn completed<T: Debug>(&mut self, label: &str, result: T) -> T {
        self.calls += 1;
        assert!(self.calls <= 100, "finite completed-call ceiling");
        println!(
            "TRANSITION {} {:03} {} => {:?}",
            self.id, self.calls, label, result
        );
        result
    }
    fn done(self) {
        assert!(
            self.calls >= 4,
            "no constructor-only or incomplete trace receipt"
        );
        println!("END {} completed_calls={}; assertions=complete; cleanup=drop owned memory; external_resources=0", self.id, self.calls);
    }
}
macro_rules! obs {
    ($r:ident, $label:literal, $value:expr) => {{
        let result = $value;
        $r.completed($label, result)
    }};
}
fn snap(epoch: u64, sequence: u64, position: u64, at: i64) -> AlarmSnapshot {
    AlarmSnapshot::committed(
        Some(at),
        AlarmSource {
            id: PublicationId { epoch, sequence },
            position,
        },
    )
}
fn config(cap: usize, slots: usize) -> Config {
    Config {
        max_resident: cap,
        max_activations: slots,
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
        pressure: pressure::PressureConfig::default(),
    }
}
struct H {
    r: Receipt,
    s: State,
    cap: usize,
    slots: usize,
    effects: Vec<Effect>,
}
impl H {
    fn new(id: &'static str, cap: usize, slots: usize) -> Self {
        Self::with_deadline(id, cap, slots, 50)
    }
    fn with_deadline(id: &'static str, cap: usize, slots: usize, deadline_ms: u64) -> Self {
        let mut configured = config(cap, slots);
        configured.operation_deadline_ms = Some(deadline_ms);
        Self {
            r: Receipt::new(id),
            s: State::new("fixture", configured),
            cap,
            slots,
            effects: vec![],
        }
    }
    fn step(&mut self, event: Event) -> Vec<Effect> {
        println!("INPUT {} {:?}", self.r.id, event);
        let effects = on_event(&mut self.s, event);
        self.s.validate().expect("production structural invariants");
        assert!(self.s.occupied() <= self.cap);
        assert!(self.s.activating() <= self.slots);
        self.effects.extend(effects.clone());
        self.r
            .completed("on_event returned and State::validate passed", effects)
    }
    fn wake(&mut self, cell: &str, scope: WakeHintScope) -> Vec<Effect> {
        self.step(Event::WakeHintAt {
            cell: cell.into(),
            entry_ms: 0,
            scope,
            now_mono_ms: 100,
        })
    }
    fn read(&mut self, op: u64, record: Option<OwnerRecord>) -> Vec<Effect> {
        self.step(Event::OwnerRead {
            op,
            now_ms: 100,
            result: Ok(record),
        })
    }
    fn cas(&mut self, op: u64) -> Vec<Effect> {
        self.step(Event::OwnerCasCompleted {
            op,
            result: Ok(CasOutcome::Applied),
        })
    }
    fn publish(&mut self, restore: u64, cell: &str, epoch: u64) {
        let e = self.step(Event::RestoreCompleted {
            op: restore,
            result: Ok(RestoreOutcome {
                restored: epoch > 1,
                alarm: None,
            }),
        });
        let e = self.step(Event::RuntimeStarted {
            op: op(&e, "start", cell),
            isolate: None,
            generation: 1,
            result: Ok(()),
        });
        self.step(Event::Published {
            op: op(&e, "publish", cell),
            result: Ok(()),
        });
        assert_eq!(self.s.phase(cell), Some(&Phase::Resident { epoch }));
    }
    fn acquire(&mut self, read: u64, cell: &str) {
        let e = self.read(read, None);
        let e = self.cas(op(&e, "cas", cell));
        self.publish(op(&e, "restore", cell), cell, 1);
    }
    fn done(self) {
        assert_eq!(self.s.activating(), 0);
        assert!(self.s.activation_waiting().is_empty());
        assert!(self.s.waiting().is_empty());
        assert_eq!(self.s.evicting(), 0);
        assert_eq!(self.s.releasing(), 0);
        assert_eq!(self.s.adopting(), 0);
        self.s.validate().unwrap();
        self.r.done();
    }
}
fn kind(e: &Effect, wanted: &str, cell: &str) -> Option<u64> {
    match (wanted, e) {
        ("read", Effect::ReadOwner { op, cell: c })
        | ("lease", Effect::ReadNodeLease { op, cell: c, .. })
        | ("cas", Effect::CasOwner { op, cell: c, .. })
        | ("restore", Effect::Restore { op, cell: c, .. })
        | ("start", Effect::StartRuntime { op, cell: c, .. })
        | ("publish", Effect::Publish { op, cell: c, .. })
        | ("fire", Effect::FireAlarm { op, cell: c, .. })
            if c == cell =>
        {
            Some(*op)
        }
        _ => None,
    }
}
fn op(e: &[Effect], wanted: &str, cell: &str) -> u64 {
    let found: Vec<_> = e.iter().filter_map(|v| kind(v, wanted, cell)).collect();
    assert_eq!(found.len(), 1, "one {wanted} for {cell}: {e:?}");
    found[0]
}
fn none(e: &[Effect], wanted: &str, cell: &str) {
    assert!(
        e.iter().all(|v| kind(v, wanted, cell).is_none()),
        "unexpected {wanted}: {e:?}"
    );
}
fn owner(node: &str, epoch: u64) -> OwnerRecord {
    OwnerRecord {
        node: Some(node.into()),
        epoch,
        etag: format!("owner-{epoch}"),
    }
}
fn alarm_schedule(e: &[Effect]) -> (Timer, u64) {
    let found: Vec<_> = e
        .iter()
        .filter_map(|v| match v {
            Effect::ScheduleTimer {
                timer: t @ Timer::CellAlarm { .. },
                at_mono_ms,
            } => Some((t.clone(), *at_mono_ms)),
            _ => None,
        })
        .collect();
    assert_eq!(found.len(), 1);
    found[0].clone()
}
fn operation_deadline(e: &[Effect], wanted: u64) -> u64 {
    let found: Vec<_> = e
        .iter()
        .filter_map(|v| match v {
            Effect::ScheduleTimer {
                timer: Timer::OperationDeadline { op },
                at_mono_ms,
            } if *op == wanted => Some(*at_mono_ms),
            _ => None,
        })
        .collect();
    assert_eq!(found.len(), 1);
    found[0]
}
fn cron_plan(
    r: &mut Receipt,
    label: &str,
    crons: &[cron::Cron],
    fired: Option<i64>,
    now: i64,
    retry: i64,
    failed: bool,
) -> (Vec<usize>, Option<i64>, bool) {
    let plan = cron::plan(crons, fired, now, retry, failed);
    r.completed(label, (plan.matching, plan.arm_at, plan.arm_is_retry))
}

#[test]
fn k001_lost_put_reply_retries_identical_immutable_key() {
    let mut r = Receipt::new("K001");
    let mut w = WakeCore::new();
    let a = snap(3, 7, 90, 60_050);
    let first = obs!(
        r,
        "issue PUT; store outcome unknown",
        w.publication("alpha", a)
    )
    .unwrap();
    assert!(!obs!(
        r,
        "unknown PUT is not coverage",
        w.covered("alpha", a)
    ));
    let retry = obs!(r, "retry after lost reply", w.publication("alpha", a)).unwrap();
    assert_eq!(first, retry);
    obs!(r, "synthetic retry PUT success", w.confirm("alpha", a));
    assert!(obs!(r, "completion grants coverage", w.covered("alpha", a)));
    assert!(obs!(
        r,
        "no third PUT after confirmation",
        w.publication("alpha", a)
    )
    .is_none());
    r.done();
}

#[test]
fn k002_old_put_completion_cannot_replace_newest_coverage() {
    let mut r = Receipt::new("K002");
    let mut w = WakeCore::new();
    let old = snap(5, 2, 10, 60_100);
    let new = snap(5, 3, 11, 60_100);
    let p_old = obs!(r, "old PUT pending", w.publication("alpha", old)).unwrap();
    let p_new = obs!(
        r,
        "replacement same minute PUT pending",
        w.publication("alpha", new)
    )
    .unwrap();
    assert_ne!(p_old.key, p_new.key);
    obs!(r, "new PUT completed first", w.confirm("alpha", new));
    obs!(r, "old PUT completed late", w.confirm("alpha", old));
    assert!(obs!(r, "newest remains covered", w.covered("alpha", new)));
    assert!(!obs!(
        r,
        "old completion cannot become current",
        w.covered("alpha", old)
    ));
    assert!(obs!(
        r,
        "new installation stays deduplicated",
        w.publication("alpha", new)
    )
    .is_none());
    r.done();
}

#[test]
fn k003_unrelated_sqlite_write_does_not_require_republication() {
    let mut r = Receipt::new("K003");
    let mut w = WakeCore::new();
    let installed = snap(2, 4, 19, 70_000);
    let later_write = snap(2, 4, 100, 70_000);
    let initial = obs!(r, "initial publication", w.publication("alpha", installed)).unwrap();
    obs!(r, "initial PUT completes", w.confirm("alpha", installed));
    assert!(obs!(
        r,
        "higher position keeps installation identity",
        installed.same_installation(later_write)
    ));
    assert!(obs!(
        r,
        "higher SQLite position is covered",
        w.covered("alpha", later_write)
    ));
    assert!(obs!(
        r,
        "unrelated writes do not churn PUTs",
        w.publication("alpha", later_write)
    )
    .is_none());
    assert_eq!(initial.alarm.source().unwrap().position, 19);
    r.done();
}

#[test]
fn k004_elected_waker_handoff_keeps_self_and_dead_owner_work() {
    let mut r = Receipt::new("K004");
    assert!(!obs!(
        r,
        "other node still holds global role",
        wake::waker_may_claim(false, 500, 499)
    ));
    assert!(!obs!(
        r,
        "live remote owner needs no elected activation",
        wake::elected_hint_needed(Some("remote"), "fixture", true)
    ));
    assert!(obs!(
        r,
        "exactly expired role becomes claimable",
        wake::waker_may_claim(false, 500, 500)
    ));
    // Subsequent role CAS success and liveness facts are explicit external premises.
    assert!(obs!(
        r,
        "new elected node must include own dormant cells",
        wake::elected_hint_needed(Some("fixture"), "fixture", true)
    ));
    assert!(obs!(
        r,
        "owner disappears during later scan",
        wake::elected_hint_needed(Some("remote"), "fixture", false)
    ));
    assert!(obs!(
        r,
        "released cell stays discoverable",
        wake::elected_hint_needed(None, "fixture", false)
    ));
    assert!(!obs!(
        r,
        "healed remote owner removes redundant probe",
        wake::elected_hint_needed(Some("remote"), "fixture", true)
    ));
    r.done();
}

#[test]
fn k005_local_cache_loss_requires_republish_only_for_forgotten_cell() {
    let mut r = Receipt::new("K005");
    let mut w = WakeCore::new();
    let a = snap(2, 6, 8, 70_000);
    let key = obs!(
        r,
        "capture stable key before local loss",
        w.publication("alpha", a)
    )
    .unwrap()
    .key;
    obs!(r, "alpha PUT completed", w.confirm("alpha", a));
    obs!(r, "beta PUT completed", w.confirm("beta", a));
    obs!(
        r,
        "alpha cache discarded on local recovery",
        w.forget("alpha")
    );
    assert!(!obs!(
        r,
        "alpha coverage must be re-established",
        w.covered("alpha", a)
    ));
    assert!(obs!(r, "beta coverage remains", w.covered("beta", a)));
    assert_eq!(
        obs!(
            r,
            "recovery uses same source identity",
            w.publication("alpha", a)
        )
        .unwrap()
        .key,
        key
    );
    obs!(r, "recovery PUT completes", w.confirm("alpha", a));
    assert!(obs!(r, "alpha covered again", w.covered("alpha", a)));
    r.done();
}

#[test]
fn k006_equal_identity_on_two_cells_does_not_share_publication_credit() {
    let mut r = Receipt::new("K006");
    let mut w = WakeCore::new();
    let a = snap(1, 1, 1, 60_000);
    let pa = obs!(r, "alpha publication", w.publication("alpha", a)).unwrap();
    let pb = obs!(r, "beta publication", w.publication("beta", a)).unwrap();
    assert_ne!(pa.key, pb.key);
    obs!(
        r,
        "beta PUT succeeds while alpha stalls",
        w.confirm("beta", a)
    );
    assert!(!obs!(r, "beta cannot cover alpha", w.covered("alpha", a)));
    assert!(obs!(r, "alpha still owes PUT", w.publication("alpha", a)).is_some());
    obs!(r, "alpha eventually completes", w.confirm("alpha", a));
    assert!(obs!(
        r,
        "alpha coverage finally exists",
        w.covered("alpha", a)
    ));
    r.done();
}

#[test]
fn k007_owned_foreign_scan_does_not_allocate_or_consume_activation_slot() {
    let mut h = H::new("K007", 1, 1);
    assert!(h.wake("foreign-a", WakeHintScope::Owned).is_empty());
    assert!(h.wake("foreign-b", WakeHintScope::Owned).is_empty());
    assert_eq!(h.s.phase("foreign-a"), None);
    assert_eq!(h.s.phase("foreign-b"), None);
    let e = h.wake("local", WakeHintScope::Fleet);
    let read = op(&e, "read", "local");
    assert!(h.wake("foreign-c", WakeHintScope::Owned).is_empty());
    assert!(h.s.activation_waiting().is_empty());
    assert_eq!(h.s.phase("foreign-c"), None);
    h.acquire(read, "local");
    assert!(!h.s.is_active("local"));
    h.done();
}

#[test]
fn k008_elected_hint_reprobes_cached_remote_but_owned_hint_does_not() {
    let mut h = H::new("K008", 1, 1);
    let e = h.wake("alpha", WakeHintScope::Fleet);
    let e = h.read(op(&e, "read", "alpha"), Some(owner("peer", 4)));
    h.step(Event::NodeLeaseRead {
        op: op(&e, "lease", "alpha"),
        now_ms: 100,
        result: Ok(Some(NodeLeaseRecord {
            node: "peer".into(),
            addr: "peer.invalid:1".into(),
            expires_ms: 1000,
            peer_protocol: 1,
            generation: "peer-live".into(),
            log_state: None,
            etag: "lease".into(),
        })),
    });
    assert!(matches!(h.s.phase("alpha"), Some(Phase::Remote { .. })));
    assert!(h.wake("alpha", WakeHintScope::Owned).is_empty());
    let e = h.wake("alpha", WakeHintScope::Fleet);
    let read = op(&e, "read", "alpha");
    // Synthetic later owner read says released; scan hints are not durable truth.
    let e = h.read(
        read,
        Some(OwnerRecord {
            node: None,
            epoch: 4,
            etag: "released".into(),
        }),
    );
    assert!(e
        .iter()
        .any(|e| matches!(e, Effect::CasOwner { epoch: 5, .. })));
    let e = h.cas(op(&e, "cas", "alpha"));
    h.publish(op(&e, "restore", "alpha"), "alpha", 5);
    assert!(!h.s.is_active("alpha"));
    h.done();
}

#[test]
fn k009_cancelled_last_caller_preserves_queued_alarm_wake_demand() {
    let mut h = H::new("K009", 2, 1);
    let e = h.wake("busy", WakeHintScope::Fleet);
    let busy_read = op(&e, "read", "busy");
    h.step(Event::RequestAt {
        request: 7,
        cell: "alarm".into(),
        now_mono_ms: 100,
    });
    h.wake("alarm", WakeHintScope::Fleet);
    h.step(Event::Cancel { request: 7 });
    assert_eq!(h.s.activation_waiting(), vec!["alarm".to_string()]);
    let e = h.step(Event::OwnerRead {
        op: busy_read,
        now_ms: 100,
        result: Err(Failure::Definite),
    });
    let read = op(&e, "read", "alarm");
    h.acquire(read, "alarm");
    assert!(h
        .effects
        .iter()
        .all(|e| !matches!(e, Effect::Complete { request: 7, .. })));
    assert!(!h.s.is_active("alarm"));
    h.done();
}

#[test]
fn k010_repeated_fleet_ticks_coalesce_through_every_cold_start_phase() {
    let mut h = H::new("K010", 1, 1);
    let e = h.wake("alpha", WakeHintScope::Fleet);
    let read = op(&e, "read", "alpha");
    none(&h.wake("alpha", WakeHintScope::Fleet), "read", "alpha");
    let e = h.read(read, None);
    let cas = op(&e, "cas", "alpha");
    none(&h.wake("alpha", WakeHintScope::Fleet), "cas", "alpha");
    let e = h.cas(cas);
    let restore = op(&e, "restore", "alpha");
    none(&h.wake("alpha", WakeHintScope::Fleet), "restore", "alpha");
    let e = h.step(Event::RestoreCompleted {
        op: restore,
        result: Ok(RestoreOutcome {
            restored: false,
            alarm: None,
        }),
    });
    let start = op(&e, "start", "alpha");
    none(&h.wake("alpha", WakeHintScope::Fleet), "start", "alpha");
    let e = h.step(Event::RuntimeStarted {
        op: start,
        isolate: None,
        generation: 1,
        result: Ok(()),
    });
    let publish = op(&e, "publish", "alpha");
    none(&h.wake("alpha", WakeHintScope::Fleet), "publish", "alpha");
    h.step(Event::Published {
        op: publish,
        result: Ok(()),
    });
    assert_eq!(h.s.presence_snapshot().activity.acquired, 1);
    assert_eq!(
        h.effects
            .iter()
            .filter(|e| kind(e, "start", "alpha").is_some())
            .count(),
        1
    );
    assert!(!h.s.is_active("alpha"));
    h.done();
}

#[test]
fn k011_failed_background_probe_needs_a_later_scan_tick_to_retry() {
    let mut h = H::new("K011", 1, 1);
    let e = h.wake("alpha", WakeHintScope::Fleet);
    let read = op(&e, "read", "alpha");
    let e = h.step(Event::OwnerRead {
        op: read,
        now_ms: 100,
        result: Err(Failure::Definite),
    });
    none(&e, "read", "alpha");
    assert_eq!(h.s.phase("alpha"), Some(&Phase::Inactive));
    assert_eq!(h.s.activating(), 0);
    assert!(h.s.activation_waiting().is_empty());
    // A later explicit scanner tick is the liveness premise, not spontaneous retry.
    let e = h.wake("alpha", WakeHintScope::Fleet);
    h.acquire(op(&e, "read", "alpha"), "alpha");
    assert_eq!(
        h.effects
            .iter()
            .filter(|e| kind(e, "read", "alpha").is_some())
            .count(),
        2
    );
    assert!(!h.s.is_active("alpha"));
    h.done();
}

#[test]
fn k012_due_alarm_defers_during_runtime_start_and_route_publication() {
    let mut h = H::with_deadline("K012", 1, 1, 500);
    let e = h.wake("alpha", WakeHintScope::Fleet);
    let e = h.read(op(&e, "read", "alpha"), Some(owner("fixture", 1)));
    let e = h.cas(op(&e, "cas", "alpha"));
    assert!(e.iter().any(|effect| matches!(effect,
        Effect::Restore { cell, spec, .. } if cell == "alpha" && !spec.fresh && spec.epoch == 2
    )));
    let e = h.step(Event::RestoreCompleted {
        op: op(&e, "restore", "alpha"),
        result: Ok(RestoreOutcome {
            restored: true,
            alarm: Some(RestoredAlarm {
                at_ms: 100,
                covered: false,
            }),
        }),
    });
    let start = op(&e, "start", "alpha");
    // This one fixture permits two honest 100ms deferrals before its 500ms operation budget.
    let start_deadline = operation_deadline(&e, start);
    assert_eq!(start_deadline, 600);
    let (timer, first_due) = alarm_schedule(&e);
    assert_eq!(first_due, 100);
    let e = h.step(Event::TimerFired {
        timer: timer.clone(),
        now_ms: first_due,
        now_mono_ms: first_due,
    });
    none(&e, "fire", "alpha");
    let (second_timer, second_due) = alarm_schedule(&e);
    assert_eq!(second_timer, timer);
    assert_eq!(second_due, 200);
    assert!(first_due < start_deadline);
    let e = h.step(Event::RuntimeStarted {
        op: start,
        isolate: None,
        generation: 1,
        result: Ok(()),
    });
    let publish = op(&e, "publish", "alpha");
    let publish_deadline = operation_deadline(&e, publish);
    assert_eq!(publish_deadline, 600);
    let e = h.step(Event::TimerFired {
        timer: second_timer,
        now_ms: second_due,
        now_mono_ms: second_due,
    });
    none(&e, "fire", "alpha");
    let (third_timer, third_due) = alarm_schedule(&e);
    assert_eq!(third_timer, timer);
    assert_eq!(third_due, 300);
    assert!(second_due < publish_deadline);
    h.step(Event::Published {
        op: publish,
        result: Ok(()),
    });
    let e = h.step(Event::TimerFired {
        timer: third_timer,
        now_ms: third_due,
        now_mono_ms: third_due,
    });
    let fire = op(&e, "fire", "alpha");
    let settled = h.step(Event::AlarmFinished {
        op: fire,
        cell: "alpha".into(),
        epoch: 2,
        now_ms: third_due,
        now_mono_ms: third_due,
        result: Ok((AlarmSnapshot::without_wake(None), false, None)),
    });
    let reconciled: Vec<_> = settled
        .iter()
        .filter_map(|effect| match effect {
            Effect::ReconcileWakeEntry { cell, alarm } => Some((cell.as_str(), *alarm)),
            _ => None,
        })
        .collect();
    assert_eq!(
        reconciled,
        vec![("alpha", AlarmSnapshot::without_wake(None))]
    );
    none(&settled, "fire", "alpha");
    assert!(settled
        .iter()
        .all(|effect| !matches!(effect, Effect::AwaitDurable { .. })));
    assert_eq!(
        h.effects
            .iter()
            .filter(|e| kind(e, "fire", "alpha").is_some())
            .count(),
        1
    );
    assert!(!h.s.is_active("alpha"));
    h.done();
}

#[test]
fn k013_failed_restore_leaves_owned_hint_eligible_for_fresh_claim() {
    let mut h = H::new("K013", 1, 1);
    let e = h.wake("alpha", WakeHintScope::Fleet);
    let e = h.read(op(&e, "read", "alpha"), None);
    let e = h.cas(op(&e, "cas", "alpha"));
    h.step(Event::RestoreCompleted {
        op: op(&e, "restore", "alpha"),
        result: Err(Failure::Definite),
    });
    assert_eq!(h.s.phase("alpha"), Some(&Phase::Dormant { epoch: 1 }));
    assert_eq!(h.s.activating(), 0);
    let e = h.wake("alpha", WakeHintScope::Owned);
    let e = h.read(op(&e, "read", "alpha"), Some(owner("fixture", 1)));
    assert!(e
        .iter()
        .any(|e| matches!(e, Effect::CasOwner { epoch: 2, .. })));
    let e = h.cas(op(&e, "cas", "alpha"));
    h.publish(op(&e, "restore", "alpha"), "alpha", 2);
    assert!(!h.s.is_active("alpha"));
    h.done();
}

#[test]
fn k014_cron_retry_owes_original_occurrence_and_success_resumes_schedule() {
    let mut r = Receipt::new("K014");
    let crons = [cron::parse("0 * * * *").unwrap()];
    assert_eq!(
        cron_plan(&mut r, "initial arm", &crons, None, -1, 0, false),
        (vec![], Some(0), false)
    );
    assert_eq!(
        cron_plan(&mut r, "first failure", &crons, Some(0), 1000, 0, true),
        (vec![0], Some(3000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry still owes minute zero",
            &crons,
            Some(0),
            3000,
            1,
            true
        ),
        (vec![0], Some(7000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "successful retry resumes hourly schedule",
            &crons,
            Some(0),
            7000,
            2,
            false
        ),
        (vec![0], Some(3_600_000), false)
    );
    assert!(!obs!(
        r,
        "retry timestamp itself is not the cron occurrence",
        cron::matches(&crons[0], 60_000)
    ));
    r.done();
}

#[test]
fn k015_next_cron_occurrence_wins_retry_tie_and_long_backoff() {
    let mut r = Receipt::new("K015");
    let crons = [cron::parse("* * * * *").unwrap()];
    assert_eq!(
        cron_plan(&mut r, "initial occurrence", &crons, None, -1, 0, false),
        (vec![], Some(0), false)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "failure backoff ties next occurrence",
            &crons,
            Some(0),
            58_000,
            0,
            true
        ),
        (vec![0], Some(60_000), false)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "new occurrence resets retry counter",
            &crons,
            Some(60_000),
            61_000,
            0,
            true
        ),
        (vec![0], Some(63_000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "first retry fails at its deadline",
            &crons,
            Some(60_000),
            63_000,
            1,
            true
        ),
        (vec![0], Some(67_000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "second retry fails at its deadline",
            &crons,
            Some(60_000),
            67_000,
            2,
            true
        ),
        (vec![0], Some(75_000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "third retry fails at its deadline",
            &crons,
            Some(60_000),
            75_000,
            3,
            true
        ),
        (vec![0], Some(91_000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "next occurrence beats32000ms backoff",
            &crons,
            Some(60_000),
            91_000,
            4,
            true
        ),
        (vec![0], Some(120_000), false)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "next run succeeds",
            &crons,
            Some(120_000),
            120_000,
            0,
            false
        ),
        (vec![0], Some(180_000), false)
    );
    r.done();
}

#[test]
fn k016_cron_retry_plan_reports_all_matches_not_failed_subset() {
    let mut r = Receipt::new("K016");
    let crons = [
        cron::parse("*/5 * * * *").unwrap(),
        cron::parse("0 * * * *").unwrap(),
        cron::parse("0 * * * *").unwrap(),
    ];
    assert_eq!(
        cron_plan(
            &mut r,
            "three expressions share one alarm",
            &crons,
            None,
            -1,
            0,
            false
        ),
        (vec![], Some(0), false)
    );
    // Only one expression failed; Plan has no failed-index input and returns all matching indices.
    assert_eq!(
        cron_plan(
            &mut r,
            "coincident occurrence leaves one expression owed",
            &crons,
            Some(0),
            0,
            0,
            true
        ),
        (vec![0, 1, 2], Some(2000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "only failed subset is retried by caller",
            &crons,
            Some(0),
            2000,
            1,
            true
        ),
        (vec![0, 1, 2], Some(6000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "owed retry succeeds",
            &crons,
            Some(0),
            6000,
            2,
            false
        ),
        (vec![0, 1, 2], Some(300_000), false)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "next ordinary occurrence has one match",
            &crons,
            Some(300_000),
            300_000,
            0,
            false
        ),
        (vec![0], Some(600_000), false)
    );
    r.done();
}

#[test]
fn k017_restart_gap_schedules_future_without_inventing_missed_occurrences() {
    let mut r = Receipt::new("K017");
    let crons = [cron::parse("0 0 * * *").unwrap()];
    assert_eq!(
        cron_plan(&mut r, "original midnight arm", &crons, None, -1, 0, false),
        (vec![], Some(0), false)
    );
    let recovered = cron_plan(
        &mut r,
        "resume after two days of downtime",
        &crons,
        Some(0),
        172_800_123,
        0,
        false,
    );
    assert_eq!(recovered, (vec![0], Some(259_200_000), false));
    assert_eq!(
        obs!(
            r,
            "rearm uses recovery time",
            cron::next_across(&crons, 172_800_123)
        ),
        Some(259_200_000)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "next resumed occurrence advances strictly",
            &crons,
            Some(259_200_000),
            259_200_000,
            0,
            false
        ),
        (vec![0], Some(345_600_000), false)
    );
    r.done();
}

#[test]
fn k018_sparse_calendar_gap_does_not_silently_lose_future_wake() {
    let mut r = Receipt::new("K018");
    let leap = cron::parse("0 0 29 2 *").unwrap();
    let fifth = cron::parse("0 0 * 2 SUN#5").unwrap();
    assert!(obs!(
        r,
        "last pre-century leap occurrence",
        cron::matches(&leap, 3_981_312_000_000)
    ));
    assert_eq!(
        obs!(
            r,
            "eight-year leap gap",
            cron::next_after(&leap, 3_981_312_000_000)
        ),
        Some(4_233_686_400_000)
    );
    assert!(obs!(
        r,
        "next leap occurrence is valid",
        cron::matches(&leap, 4_233_686_400_000)
    ));
    assert_eq!(
        obs!(
            r,
            "twenty-eight-year fifth-Sunday gap",
            cron::next_after(&fifth, 1_078_012_800_000)
        ),
        Some(1_961_625_600_000)
    );
    let p = cron_plan(
        &mut r,
        "cold cell retains sparse future schedule",
        &[fifth],
        Some(1_078_012_800_000),
        1_078_012_800_000,
        0,
        false,
    );
    assert_eq!(p, (vec![0], Some(1_961_625_600_000), false));
    r.done();
}

#[test]
fn k019_unsatisfiable_schedule_cannot_hide_viable_sibling_or_spin_retry() {
    let mut r = Receipt::new("K019");
    let impossible = cron::parse("0 0 31 2 *").unwrap();
    let minute = cron::parse("* * * * *").unwrap();
    assert_eq!(
        obs!(
            r,
            "finite full Gregorian scan finds no day",
            cron::next_after(&impossible, 0)
        ),
        None
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "viable sibling still schedules",
            &[impossible.clone(), minute],
            None,
            0,
            0,
            false
        ),
        (vec![], Some(60_000), false)
    );
    // Synthetic replacement removed the old expression; the caller still owes its failed occurrence0.
    assert_eq!(
        cron_plan(
            &mut r,
            "first old-work failure",
            &[impossible.clone()],
            Some(0),
            0,
            0,
            true
        ),
        (vec![], Some(2000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry1 fails at2000",
            &[impossible.clone()],
            Some(0),
            2000,
            1,
            true
        ),
        (vec![], Some(6000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry2 fails at6000",
            &[impossible.clone()],
            Some(0),
            6000,
            2,
            true
        ),
        (vec![], Some(14000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry3 fails at14000",
            &[impossible.clone()],
            Some(0),
            14000,
            3,
            true
        ),
        (vec![], Some(30000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry4 fails at30000",
            &[impossible.clone()],
            Some(0),
            30000,
            4,
            true
        ),
        (vec![], Some(62000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry5 fails at62000",
            &[impossible.clone()],
            Some(0),
            62000,
            5,
            true
        ),
        (vec![], Some(126000), true)
    );
    assert_eq!(
        cron_plan(
            &mut r,
            "retry6 exhausts at126000",
            &[impossible],
            Some(0),
            126000,
            6,
            true
        ),
        (vec![], None, false)
    );
    r.done();
}

#[test]
fn k020_queue_recovery_merges_overdue_batch_visibility_lease_and_sweep() {
    let mut r = Receipt::new("K020");
    assert_eq!(
        obs!(
            r,
            "cold row deadlines include overdue batch",
            queue::rearm(100, Some(20), Some(200), Some(150), Some(300))
        ),
        Some(100)
    );
    assert_eq!(
        obs!(
            r,
            "batch handled; expired consumer is next",
            queue::rearm(100, None, Some(200), Some(150), Some(300))
        ),
        Some(150)
    );
    let expired = obs!(
        r,
        "synthetic persisted lease expiry",
        queue::expire_lease(151, 0, 3, Some(2), false)
    );
    assert_eq!(expired.action, queue::ExpiredLeaseAction::RetryAt(2151));
    assert_eq!(
        obs!(
            r,
            "independent visible row beats failed consumer retry",
            queue::rearm(151, None, Some(200), None, Some(300))
        ),
        Some(200)
    );
    assert_eq!(
        obs!(
            r,
            "after visible row settles sweep precedes retry",
            queue::rearm(200, None, Some(2151), None, Some(300))
        ),
        Some(300)
    );
    r.done();
}

#[test]
fn k021_queue_batch_skips_live_and_delayed_rows_then_reclaims_after_expiry() {
    let mut r = Receipt::new("K021");
    let live = queue::BatchRow {
        seq: 1,
        visible_at: 0,
        lease_generation: 2,
        leased_until: Some(200),
        purge_on_settle: false,
    };
    let delayed = queue::BatchRow {
        seq: 2,
        visible_at: 150,
        lease_generation: 0,
        leased_until: None,
        purge_on_settle: false,
    };
    let ready = queue::BatchRow {
        seq: 3,
        visible_at: 0,
        lease_generation: 0,
        leased_until: None,
        purge_on_settle: false,
    };
    let first = obs!(
        r,
        "head blockers do not hide ready tail",
        queue::batch_plan(100, &[live, delayed, ready], 2)
    )
    .unwrap();
    assert_eq!(
        first.leases,
        vec![queue::PlannedLease {
            seq: 3,
            generation: 1,
            reclaimed: false
        }]
    );
    assert_eq!(
        obs!(
            r,
            "delayed row sets next alarm",
            queue::rearm(100, None, Some(150), Some(200), None)
        ),
        Some(150)
    );
    let second = obs!(
        r,
        "ready row synthetically settled; delayed becomes visible",
        queue::batch_plan(150, &[live, delayed], 2)
    )
    .unwrap();
    assert_eq!(
        second.leases,
        vec![queue::PlannedLease {
            seq: 2,
            generation: 1,
            reclaimed: false
        }]
    );
    let third = obs!(
        r,
        "persisted live lease finally expires",
        queue::batch_plan(200, &[live], 2)
    )
    .unwrap();
    assert_eq!(
        third.leases,
        vec![queue::PlannedLease {
            seq: 1,
            generation: 3,
            reclaimed: true
        }]
    );
    r.done();
}

#[test]
fn k022_handler_return_does_not_release_persisted_batch_concurrency_slot() {
    let mut r = Receipt::new("K022");
    assert!(!obs!(
        r,
        "two durable leases occupy both slots",
        queue::can_install_lease(2, 2)
    ));
    // A handler returned but its settlement write has not committed: active remains 2.
    assert!(!obs!(
        r,
        "uncommitted settlement cannot create capacity",
        queue::can_install_lease(2, 2)
    ));
    assert_eq!(
        obs!(
            r,
            "wait on earliest persisted lease expiry",
            queue::rearm(100, None, None, Some(250), None)
        ),
        Some(250)
    );
    assert_eq!(
        obs!(
            r,
            "expiry schedules fixed retry",
            queue::expire_lease(250, 0, 3, Some(1), false)
        )
        .action,
        queue::ExpiredLeaseAction::RetryAt(1250)
    );
    assert!(obs!(
        r,
        "synthetic expiry transaction removes exactly one lease",
        queue::can_install_lease(1, 2)
    ));
    assert_eq!(
        obs!(
            r,
            "retry is visible later; capacity does not erase delay",
            queue::rearm(250, None, Some(1250), None, None)
        ),
        Some(1250)
    );
    r.done();
}

#[test]
fn k023_queue_missing_settlement_uses_fixed_backoff_and_finite_failure_budget() {
    let mut r = Receipt::new("K023");
    let first = obs!(
        r,
        "first lost settlement expires",
        queue::expire_lease(100, 0, 3, Some(3), false)
    );
    assert_eq!(
        first,
        queue::ExpiredLease {
            attempt: 1,
            action: queue::ExpiredLeaseAction::RetryAt(3100)
        }
    );
    let second = obs!(
        r,
        "second lost settlement uses same delay",
        queue::expire_lease(3200, 1, 3, Some(3), false)
    );
    assert_eq!(
        second,
        queue::ExpiredLease {
            attempt: 2,
            action: queue::ExpiredLeaseAction::RetryAt(6200)
        }
    );
    assert_eq!(
        obs!(
            r,
            "explicit zero delay overrides default on live settlement",
            queue::retry_at(6200, Some(0), Some(3))
        ),
        6200
    );
    let third = obs!(
        r,
        "third expiry still has one retry",
        queue::expire_lease(6300, 2, 3, Some(3), false)
    );
    assert_eq!(third.action, queue::ExpiredLeaseAction::RetryAt(9300));
    let last = obs!(
        r,
        "fourth failed delivery exhausts budget",
        queue::expire_lease(9400, 3, 3, Some(3), false)
    );
    assert_eq!(
        last,
        queue::ExpiredLease {
            attempt: 4,
            action: queue::ExpiredLeaseAction::Exhausted
        }
    );
    assert_eq!(
        obs!(
            r,
            "no remaining row facts means no alarm",
            queue::rearm(9400, None, None, None, None)
        ),
        None
    );
    r.done();
}

#[test]
fn k024_sweep_row_bound_is_callers_input_bound_not_batch_output_limit() {
    let mut r = Receipt::new("K024");
    // One finite 257-row frontier schedule. No case multiplication by row count.
    let mut rows: Vec<_> = (0..sweep::BATCH_ROWS)
        .map(|i| queue::BatchRow {
            seq: i as i64,
            visible_at: 1000,
            lease_generation: 0,
            leased_until: None,
            purge_on_settle: false,
        })
        .collect();
    rows.push(queue::BatchRow {
        seq: 256,
        visible_at: 0,
        lease_generation: 0,
        leased_until: None,
        purge_on_settle: false,
    });
    assert_eq!(rows.len(), 257);
    assert!(obs!(
        r,
        "bounded first scan page has no visible rows",
        queue::batch_plan(100, &rows[..sweep::BATCH_ROWS], 1)
    )
    .unwrap()
    .leases
    .is_empty());
    let unbounded_input = obs!(
        r,
        "batch output cap does not cap examined rows",
        queue::batch_plan(100, &rows, 1)
    )
    .unwrap();
    assert_eq!(
        unbounded_input.leases,
        vec![queue::PlannedLease {
            seq: 256,
            generation: 1,
            reclaimed: false
        }]
    );
    assert_eq!(
        obs!(
            r,
            "full scan page requests prompt next turn",
            queue::rearm(100, None, None, None, Some(100))
        ),
        Some(100)
    );
    let next_page = obs!(
        r,
        "explicit next scan page reaches ready frontier",
        queue::batch_plan(100, &rows[sweep::BATCH_ROWS..], 1)
    )
    .unwrap();
    assert_eq!(next_page.leases, unbounded_input.leases);
    r.done();
}
