//! Test-only direct production-State lease regression. No wire or live SUT.
//! Compile the unchanged pinned celld_logic library, then link this test file.
use celld_logic::{on_event, CasGuard, Config, Effect, Event, Failure, HaltReason,
    LeaseCasOutcome, NodeLeaseRecord, NodeLeaseSpec, OwnershipOnEvict, State, Timer};

fn config() -> Config {
    Config {
        max_resident: 8,
        max_activations: 4,
        max_evictions: 1,
        max_releases: 1,
        max_outbound_websockets: 4,
        ownership_on_evict: OwnershipOnEvict::Release,
        require_node_lease: true,
        peer_protocol: 1,
        operation_deadline_ms: None,
        owner_log_recovery_backoff_ms: 100,
        owner_log_recovery_attempts: 3,
        alarm_resident_ms: 0,
        idle_evict_ms: None,
        pressure: Default::default(),
    }
}
fn spec() -> NodeLeaseSpec {
    NodeLeaseSpec {
        addr: "127.0.0.1:18081".into(), peer_protocol: 1,
        generation: "owned-process-G".into(), resume_generation: None, ttl_ms: 30_000,
    }
}
fn read_op(effects: &[Effect]) -> u64 {
    let ops: Vec<_> = effects.iter().filter_map(|effect| match effect {
        Effect::ReadSelfNodeLease { op, .. } => Some(*op), _ => None,
    }).collect();
    assert_eq!(ops.len(), 1, "one real ReadSelf effect: {effects:?}"); ops[0]
}
fn cas(effects: &[Effect]) -> (u64, CasGuard, NodeLeaseRecord, Option<u64>) {
    let ops: Vec<_> = effects.iter().filter_map(|effect| match effect {
        Effect::CasNodeLease { op, guard, record, authority_expires_ms } =>
            Some((*op, guard.clone(), record.clone(), *authority_expires_ms)),
        _ => None,
    }).collect();
    assert_eq!(ops.len(), 1, "one real CAS effect: {effects:?}"); ops[0].clone()
}
fn timer(effects: &[Effect], fence: bool) -> (Timer, u64) {
    let timers: Vec<_> = effects.iter().filter_map(|effect| match effect {
        Effect::ScheduleTimer { timer, at_mono_ms }
            if matches!((fence, timer), (true, Timer::NodeLeaseFence { .. })
                | (false, Timer::NodeLeaseRenew { .. })) => Some((timer.clone(), *at_mono_ms)),
        _ => None,
    }).collect();
    assert_eq!(timers.len(), 1, "one requested timer: {effects:?}"); timers[0].clone()
}
fn fire(state: &mut State, timer: Timer, wall: u64, mono: u64) -> Vec<Effect> {
    on_event(state, Event::TimerFired { timer, now_ms: wall, now_mono_ms: mono })
}
fn read(state: &mut State, op: u64, wall: u64, mono: u64,
        result: Result<Option<NodeLeaseRecord>, Failure>) -> Vec<Effect> {
    on_event(state, Event::SelfNodeLeaseRead { op, now_ms: wall, now_mono_ms: mono, result })
}
fn complete(state: &mut State, op: u64, mono: u64,
            result: Result<LeaseCasOutcome, Failure>) -> Vec<Effect> {
    on_event(state, Event::NodeLeaseCasCompleted {
        op, now_mono_ms: mono, result, stamped_log_state: None,
    })
}
fn assert_no_cas(effects: &[Effect]) {
    assert!(!effects.iter().any(|e| matches!(e, Effect::CasNodeLease { .. })),
        "unexpected write: {effects:?}");
}
fn assert_expired_halt(effects: &[Effect]) {
    assert!(effects.iter().any(|e| matches!(e,
        Effect::Halt { code: 3, reason: HaltReason::NodeLeaseExpired })),
        "missing exact expiry fence: {effects:?}");
}

struct Held {
    state: State, prior: NodeLeaseRecord, renew: Timer, fence: Timer,
}
fn held() -> Held {
    let mut state = State::new("owned-node", config());
    let effects = on_event(&mut state, Event::StartNodeLease {
        now_ms: 0, now_mono_ms: 0, spec: spec(),
    });
    let op = read_op(&effects);
    let effects = read(&mut state, op, 0, 0, Ok(None));
    let (op, guard, mut prior, authority) = cas(&effects);
    assert_eq!(guard, CasGuard::Absent); assert_eq!(authority, None);
    assert_eq!(prior.expires_ms, 30_000);
    prior.etag = "E0".into();
    let effects = complete(&mut state, op, 1,
        Ok(LeaseCasOutcome::Applied { etag: prior.etag.clone() }));
    let (renew, renew_at) = timer(&effects, false);
    let (fence, fence_at) = timer(&effects, true);
    assert_eq!((renew_at, fence_at), (10_000, 30_000));
    let effects = on_event(&mut state, Event::LocalCellsRead { result: Ok(Vec::new()) });
    assert_no_cas(&effects); assert!(state.node_authoritative());
    Held { state, prior, renew, fence }
}
struct FirstRenewal {
    held: Held, cas_op: u64, desired: NodeLeaseRecord,
}
fn first_writing() -> FirstRenewal {
    let mut held = held();
    let effects = fire(&mut held.state, held.renew.clone(), 10_000, 10_000);
    let (cas_op, guard, mut desired, authority) = cas(&effects);
    assert_eq!(guard, CasGuard::Match("E0".into()));
    assert_eq!(authority, Some(30_000)); assert_eq!(desired.expires_ms, 40_000);
    desired.etag = "E1".into();
    FirstRenewal { held, cas_op, desired }
}
fn first_reading() -> (FirstRenewal, u64) {
    let mut scenario = first_writing();
    let effects = complete(&mut scenario.held.state, scenario.cas_op, 12_500,
        Err(Failure::Ambiguous));
    let op = read_op(&effects); assert_no_cas(&effects);
    (scenario, op)
}
struct Intermediate {
    first: FirstRenewal, read_op: u64, stale_read_op: u64, current_desired: NodeLeaseRecord,
}
fn intermediate_reading() -> Intermediate {
    let (mut first, stale_read_op) = first_reading();
    let effects = read(&mut first.held.state, stale_read_op, 15_000, 15_000,
        Err(Failure::Definite));
    assert_no_cas(&effects);
    let (renew, at) = timer(&effects, false); assert_eq!(at, 18_750);
    assert!(!effects.iter().any(|e| matches!(e, Effect::ScheduleTimer {
        timer: Timer::NodeLeaseFence { .. }, .. })), "read error extended fence");
    let effects = fire(&mut first.held.state, renew, at, at);
    let (op, guard, current_desired, authority) = cas(&effects);
    assert_eq!(guard, CasGuard::Match("E0".into()));
    assert_eq!(authority, Some(30_000)); assert_eq!(current_desired.expires_ms, 48_750);
    assert_ne!(op, first.cas_op);
    let effects = complete(&mut first.held.state, op, 20_000, Ok(LeaseCasOutcome::Rejected));
    let read_op = read_op(&effects); assert_no_cas(&effects);
    assert_ne!(read_op, stale_read_op);
    Intermediate { first, read_op, stale_read_op, current_desired }
}
fn intermediate_boundary(at: u64, fence_first: bool) {
    let mut s = intermediate_reading();
    assert_ne!(s.first.desired.expires_ms, s.current_desired.expires_ms);
    assert_ne!(s.first.desired.etag, s.first.held.prior.etag);
    if fence_first {
        let effects = fire(&mut s.first.held.state, s.first.held.fence.clone(), at, at);
        assert_expired_halt(&effects); assert!(s.first.held.state.is_fenced());
    }
    let effects = read(&mut s.first.held.state, s.read_op, at, at, Ok(Some(s.first.desired)));
    let authoritative_after_read = s.first.held.state.node_authoritative();
    let subsequent = fire(&mut s.first.held.state, s.first.held.fence.clone(), at, at);
    let authoritative_after_old_fence = s.first.held.state.node_authoritative();
    eprintln!("boundary={at} fence_first={fence_first} authority_after_read={authoritative_after_read} authority_after_old_fence={authoritative_after_old_fence} read_effects={effects:?} old_fence_effects={subsequent:?}");
    assert!(!authoritative_after_read, "late intermediate record reacquired authority");
    assert!(!authoritative_after_old_fence, "old expiry timer lost its authority barrier");
    assert!(s.first.held.state.is_fenced()); assert_no_cas(&effects); assert_no_cas(&subsequent);
    if !fence_first { assert_expired_halt(&effects); }
}

#[test] fn intermediate_at_expiry_completion_first_must_fence() { intermediate_boundary(30_000, false); }
#[test] fn intermediate_after_expiry_completion_first_must_fence() { intermediate_boundary(30_001, false); }
#[test] fn intermediate_at_expiry_timer_first_stays_fenced() { intermediate_boundary(30_000, true); }
#[test] fn intermediate_after_expiry_timer_first_stays_fenced() { intermediate_boundary(30_001, true); }
#[test] fn intermediate_before_expiry_retains_valid_proof() {
    let mut s = intermediate_reading();
    let effects = read(&mut s.first.held.state, s.read_op, 29_999, 29_999, Ok(Some(s.first.desired)));
    assert!(s.first.held.state.node_authoritative()); assert!(!s.first.held.state.is_fenced());
    let (fence, at) = timer(&effects, true); assert_eq!(at, 40_000);
    let (renew, at) = timer(&effects, false); assert_eq!(at, 30_000);
    assert_no_cas(&effects);
    let effects = fire(&mut s.first.held.state, renew, at, at);
    let (_, guard, _, authority) = cas(&effects);
    assert_eq!(guard, CasGuard::Match("E1".into())); assert_eq!(authority, Some(40_000));
    let effects = fire(&mut s.first.held.state, fence, 40_000, 40_000);
    assert_expired_halt(&effects); assert!(!s.first.held.state.node_authoritative());
}
#[test] fn exact_desired_before_expiry_is_accepted() {
    let (mut s, op) = first_reading();
    let effects = read(&mut s.held.state, op, 29_999, 29_999, Ok(Some(s.desired)));
    assert!(s.held.state.node_authoritative()); assert_eq!(timer(&effects, true).1, 40_000);
}
#[test] fn exact_desired_at_and_after_expiry_fences() {
    for at in [30_000, 30_001] {
        let (mut s, op) = first_reading();
        let effects = read(&mut s.held.state, op, at, at, Ok(Some(s.desired)));
        assert_expired_halt(&effects); assert!(s.held.state.is_fenced());
        assert!(!s.held.state.node_authoritative()); assert_no_cas(&effects);
    }
}
#[test] fn applied_before_expiry_is_accepted() {
    let mut s = first_writing();
    let effects = complete(&mut s.held.state, s.cas_op, 29_999,
        Ok(LeaseCasOutcome::Applied { etag: "E1".into() }));
    assert!(s.held.state.node_authoritative()); assert_eq!(timer(&effects, true).1, 40_000);
}
#[test] fn applied_at_and_after_expiry_fences() {
    for at in [30_000, 30_001] {
        let mut s = first_writing();
        let effects = complete(&mut s.held.state, s.cas_op, at,
            Ok(LeaseCasOutcome::Applied { etag: "E1".into() }));
        assert_expired_halt(&effects); assert!(s.held.state.is_fenced());
        assert!(!s.held.state.node_authoritative()); assert_no_cas(&effects);
    }
}
#[test] fn prior_and_error_reads_do_not_extend_expired_authority() {
    for fail in [false, true] {
        let (mut s, op) = first_reading();
        let result = if fail { Err(Failure::Definite) } else { Ok(Some(s.held.prior.clone())) };
        let effects = read(&mut s.held.state, op, 30_001, 30_001, result);
        assert!(!s.held.state.node_authoritative()); assert_no_cas(&effects);
        assert!(!effects.iter().any(|e| matches!(e, Effect::ScheduleTimer {
            timer: Timer::NodeLeaseFence { .. }, .. })));
        let effects = fire(&mut s.held.state, s.held.fence, 30_001, 30_001);
        assert!(s.held.state.is_fenced()); assert!(!s.held.state.node_authoritative());
        // A future guard can fence on the read itself; the already-fenced timer is then inert.
        assert_no_cas(&effects);
    }
}
#[test] fn ordinary_missing_or_different_generation_cannot_restore_authority() {
    for missing in [false, true] {
        let (mut s, op) = first_reading();
        let mut other = s.desired;
        other.generation = "ordinary-successor-process".into(); other.etag = "successor-E".into();
        let effects = read(&mut s.held.state, op, 30_001, 30_001,
            Ok(if missing { None } else { Some(other) }));
        assert!(s.held.state.is_fenced()); assert!(!s.held.state.node_authoritative());
        assert_no_cas(&effects);
    }
}
#[test] fn stale_read_cannot_install_its_record() {
    let mut s = intermediate_reading();
    let effects = read(&mut s.first.held.state, s.stale_read_op, 29_000, 29_000,
        Ok(Some(s.first.desired.clone())));
    assert!(effects.is_empty()); assert!(s.first.held.state.node_authoritative());
    // A stale timestamp may advance high-water clocks, but cannot install proof.
    let effects = read(&mut s.first.held.state, s.stale_read_op, 30_001, 30_001,
        Ok(Some(s.first.desired.clone())));
    assert!(effects.is_empty()); assert!(!s.first.held.state.node_authoritative());
    let effects = fire(&mut s.first.held.state, s.first.held.fence, 30_001, 30_001);
    assert_expired_halt(&effects); assert!(s.first.held.state.is_fenced());
}
#[test] fn late_read_and_applied_after_terminal_fence_are_inert() {
    let (mut s, op) = first_reading();
    let effects = fire(&mut s.held.state, s.held.fence, 30_000, 30_000);
    assert_expired_halt(&effects);
    assert!(read(&mut s.held.state, op, 30_001, 30_001, Ok(Some(s.desired))).is_empty());
    assert!(complete(&mut s.held.state, s.cas_op, 30_002,
        Ok(LeaseCasOutcome::Applied { etag: "E1".into() })).is_empty());
    assert!(s.held.state.is_fenced()); assert!(!s.held.state.node_authoritative());
}
fn initial_readback(completed: u64) -> (State, Vec<Effect>) {
    let mut state = State::new("owned-node", config());
    let effects = on_event(&mut state, Event::StartNodeLease {
        now_ms: 50_000, now_mono_ms: 50_000, spec: spec(),
    });
    let op = read_op(&effects);
    let effects = read(&mut state, op, 50_000, 50_000, Ok(None));
    let (op, _, mut desired, authority) = cas(&effects); assert_eq!(authority, None);
    assert_eq!(desired.expires_ms, 80_000); desired.etag = "initial-E".into();
    let effects = complete(&mut state, op, 51_000, Err(Failure::Ambiguous));
    let op = read_op(&effects);
    let effects = read(&mut state, op, completed, completed, Ok(Some(desired)));
    (state, effects)
}
#[test] fn initial_no_prior_valid_readback_is_exempt() {
    let (state, effects) = initial_readback(79_999);
    assert!(state.node_authoritative()); assert!(!state.is_fenced());
    assert_eq!(timer(&effects, true).1, 80_000);
}
#[test] fn initial_expired_candidate_never_gets_authority() {
    for at in [80_000, 80_001] {
        let (state, effects) = initial_readback(at);
        assert!(!state.node_authoritative()); assert!(!state.is_fenced());
        assert_no_cas(&effects); assert_eq!(timer(&effects, false).1, at + 10_000);
    }
}
